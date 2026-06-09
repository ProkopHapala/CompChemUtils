#!/usr/bin/env python3
"""
Export SiCH small-molecule vibration data for external classical force-field fitting.

Self-contained SiCH_small_export/: README, JSON metadata, NPZ, CSV. No repo scripts required after export.
"""

import json
import csv
import shutil
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from ase.io import write
from ase.neighborlist import natural_cutoffs, NeighborList
from ase.units import Hartree, Bohr, invcm

from vib_store import load_method, discover_methods
from vib_match import match_modes, geometry_rmsd
from vib_utils import _modes_from_hessian_ase

SICH_MOLECULES = ('CH4', 'C2H6', 'SiH4', 'Si2H6')
REF_METHOD = 'pyscf_b3lyp_cc-pVDZ'
EXPORT_VERSION = '1.0'
HA_BOHR2_TO_EV_ANG2 = float(Hartree / Bohr ** 2)

METHOD_INFO = {
    'pyscf_b3lyp_cc-pVDZ': {
        'family': 'ab_initio', 'program': 'PySCF', 'theory': 'DFT', 'functional': 'B3LYP', 'basis': 'cc-pVDZ',
        'hessian': 'analytical', 'geometry_source': 'independent_BFGS_relaxation',
        'hessian_native_units': 'Hartree/Bohr^2', 'hessian_export_units': 'eV/Angstrom^2',
        'recommended_reference': True,
    },
    'dftb_mio-1-1': {
        'family': 'tight_binding', 'program': 'DFTB+', 'sk_set': 'mio-1-1',
        'hessian': 'finite_difference_ase', 'geometry_source': 'independent_BFGS_relaxation',
        'hessian_native_units': 'eV/Angstrom^2', 'hessian_export_units': 'eV/Angstrom^2',
        'recommended_reference': False, 'elements': 'C,H',
    },
    'dftb_3ob-3-1': {
        'family': 'tight_binding', 'program': 'DFTB+', 'sk_set': '3ob-3-1',
        'hessian': 'finite_difference_ase', 'geometry_source': 'independent_BFGS_relaxation',
        'hessian_native_units': 'eV/Angstrom^2', 'hessian_export_units': 'eV/Angstrom^2',
        'recommended_reference': False, 'elements': 'C,H',
    },
    'dftb_matsci-0-3': {
        'family': 'tight_binding', 'program': 'DFTB+', 'sk_set': 'matsci-0-3',
        'hessian': 'finite_difference_ase', 'geometry_source': 'independent_BFGS_relaxation',
        'hessian_native_units': 'eV/Angstrom^2', 'hessian_export_units': 'eV/Angstrom^2',
        'recommended_reference': False, 'elements': 'Si,H',
    },
    'dftb_pbc-0-3': {
        'family': 'tight_binding', 'program': 'DFTB+', 'sk_set': 'pbc-0-3',
        'hessian': 'finite_difference_ase', 'geometry_source': 'independent_BFGS_relaxation',
        'hessian_native_units': 'eV/Angstrom^2', 'hessian_export_units': 'eV/Angstrom^2',
        'recommended_reference': False, 'elements': 'Si,H',
    },
}


def hessian_to_3n(hessian):
    h = np.asarray(hessian)
    if h.ndim == 4:
        return h.reshape(3 * h.shape[0], 3 * h.shape[0])
    if h.ndim == 2:
        return h.copy()
    raise ValueError(f'Unsupported Hessian shape {h.shape}')


def hessian_to_ev_ang2(hessian, method_tag):
    h3 = hessian_to_3n(hessian)
    native = METHOD_INFO.get(method_tag, {}).get('hessian_native_units', 'eV/Angstrom^2')
    if 'Hartree' in native or 'Bohr' in native:
        return h3 * HA_BOHR2_TO_EV_ANG2
    return h3


def freqs_cm1_from_hessian(hessian_ev_ang2, atoms):
    """Cross-check: rebuild frequencies from exported Hessian (eV/Ang^2)."""
    energies, _ = _modes_from_hessian_ase(atoms, hessian_ev_ang2)
    return np.array([float(e.real / invcm) if e.imag == 0 and e.real > 0 else np.nan for e in energies])


def detect_connectivity(atoms, mult=1.15):
    """Bonds and angles from natural covalent cutoffs (for spring topology)."""
    cut = natural_cutoffs(atoms, mult=mult)
    nl = NeighborList(cut, self_interaction=False, bothways=True)
    nl.update(atoms)
    pos = atoms.get_positions()
    bonds, seen_b = [], set()
    for i in range(len(atoms)):
        indices, offsets = nl.get_neighbors(i)
        for j in indices:
            if i >= j:
                continue
            key = (i, j)
            if key in seen_b:
                continue
            seen_b.add(key)
            r0 = float(np.linalg.norm(pos[j] - pos[i]))
            bonds.append({'i': int(i), 'j': int(j), 'r0_A': r0,
                          'symbols': f'{atoms[i].symbol}-{atoms[j].symbol}'})
    # angles i-j-k where j is central
    nbrs = {i: set(nl.get_neighbors(i)[0]) for i in range(len(atoms))}
    angles, seen_a = [], set()
    for j in range(len(atoms)):
        for i in nbrs[j]:
            for k in nbrs[j]:
                if i >= k:
                    continue
                key = (i, j, k)
                if key in seen_a:
                    continue
                seen_a.add(key)
                v1, v2 = pos[i] - pos[j], pos[k] - pos[j]
                c = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-12)
                theta0 = float(np.degrees(np.arccos(np.clip(c, -1, 1))))
                angles.append({'i': int(i), 'j': int(j), 'k': int(k), 'theta0_deg': theta0})
    return bonds, angles


def _write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as fp:
        json.dump(obj, fp, indent=2)


def _export_method_npz(path, atoms, rec, method_tag):
    """Single NPZ with all arrays + README keys documented in manifest."""
    h_ev = hessian_to_ev_ang2(rec['hessian'], method_tag)
    modes = np.asarray(rec['modes'])  # (n_vib, N, 3)
    freqs = np.asarray(rec['mode_freqs'], dtype=float)
    pos = atoms.get_positions()
    masses = atoms.get_masses()
    symbols = np.array(atoms.get_chemical_symbols())
    np.savez_compressed(
        path,
        positions_A=pos,
        masses_amu=masses,
        symbols=symbols,
        frequencies_cm1=freqs,
        modes_cartesian=modes,
        hessian_3N_eV_Ang2=h_ev,
        n_atoms=len(atoms),
        n_vibrational_modes=len(freqs),
    )


def _export_frequencies_csv(path, freqs, modes):
    with open(path, 'w', newline='') as fp:
        w = csv.writer(fp)
        w.writerow(['mode_index', 'frequency_cm1', 'max_displacement_atom', 'max_displacement_A'])
        for i, f in enumerate(freqs):
            disp = np.linalg.norm(modes[i], axis=1)
            jmax = int(np.argmax(disp))
            w.writerow([i, f'{f:.6f}', jmax, f'{disp[jmax]:.6f}'])


def _export_modes_xyz(path, atoms, freqs, modes):
    syms = atoms.get_chemical_symbols()
    pos = atoms.get_positions()
    with open(path, 'w') as fp:
        for i, (f, mode) in enumerate(zip(freqs, modes)):
            fp.write(f'{len(atoms)}\n')
            fp.write(f'frequency_cm1={f:.4f} mode_index={i}\n')
            for j, s in enumerate(syms):
                x, y, z = pos[j]
                dx, dy, dz = mode[j]
                fp.write(f'{s:2s} {x:14.8f} {y:14.8f} {z:14.8f} {dx:14.8f} {dy:14.8f} {dz:14.8f}\n')


def export_molecule(mol_name, workdir, out_root, ref_tag=REF_METHOD):
    """Export one molecule into out_root/<mol_name>/."""
    mol_out = out_root / mol_name
    mol_out.mkdir(parents=True, exist_ok=True)
    methods = discover_methods(mol_name, workdir)
    if ref_tag not in methods:
        raise FileNotFoundError(f'Reference method {ref_tag} missing for {mol_name}')
    ref = load_method(mol_name, ref_tag, workdir=workdir)
    ref_atoms = ref['atoms']
    bonds, angles = detect_connectivity(ref_atoms)
    write(str(mol_out / 'equilibrium_reference.xyz'), ref_atoms)
    mol_meta = {
        'molecule': mol_name,
        'formula': ref_atoms.get_chemical_formula(),
        'n_atoms': len(ref_atoms),
        'reference_method': ref_tag,
        'reference_geometry_note': (
            'equilibrium_reference.xyz is the PySCF B3LYP/cc-pVDZ relaxed structure. '
            'Each QM method also has its own relaxed.xyz in methods/<tag>/ (RMSD typically <0.03 A). '
            'For strict force-field fitting at one geometry, use equilibrium_reference.xyz and '
            'optionally recompute target Hessians there.'
        ),
        'symbols': ref_atoms.get_chemical_symbols(),
        'masses_amu': ref_atoms.get_masses().tolist(),
        'positions_reference_A': ref_atoms.get_positions().tolist(),
        'connectivity': {'bonds': bonds, 'angles': angles},
        'methods_available': methods,
    }
    _write_json(mol_out / 'molecule.json', mol_meta)
    summary_rows = []
    for tag in methods:
        rec = load_method(mol_name, tag, workdir=workdir)
        atoms = rec['atoms']
        mdir = mol_out / 'methods' / tag
        mdir.mkdir(parents=True, exist_ok=True)
        write(str(mdir / 'relaxed.xyz'), atoms)
        h_ev = hessian_to_ev_ang2(rec['hessian'], tag)
        check_freqs = freqs_cm1_from_hessian(h_ev, atoms)
        meta = {
            'molecule': mol_name, 'method_tag': tag, **METHOD_INFO.get(tag, {}),
            'geometry_rmsd_vs_reference_A': geometry_rmsd(ref_atoms.get_positions(), atoms.get_positions()),
            'n_vibrational_modes': len(rec['mode_freqs']),
            'frequency_unit': 'cm^-1',
            'mode_vector_unit': 'Angstrom (Cartesian displacement, not mass-weighted)',
            'hessian_shape': list(h_ev.shape),
            'hessian_unit': 'eV/Angstrom^2',
            'npz_file': 'vibrations.npz',
            'npz_arrays': {
                'positions_A': '(N,3) geometry at which Hessian was computed',
                'masses_amu': '(N,) atomic masses',
                'symbols': '(N,) element symbols',
                'frequencies_cm1': '(n_vib,) harmonic frequencies',
                'modes_cartesian': '(n_vib,N,3) normal mode displacement vectors',
                'hessian_3N_eV_Ang2': '(3N,3N) Cartesian Hessian d2E/dx2',
            },
            'fitting_notes': (
                'Build molecular Hessian from bond/angle springs at positions_A, compare eigenvalues '
                'to frequencies_cm1 or full matrix to hessian_3N_eV_Ang2. '
                'modes_cartesian are eigenvectors of mass-weighted Hessian (ASE convention).'
            ),
        }
        _write_json(mdir / 'meta.json', meta)
        _export_method_npz(mdir / 'vibrations.npz', atoms, rec, tag)
        _export_frequencies_csv(mdir / 'frequencies.csv', rec['mode_freqs'], rec['modes'])
        _export_modes_xyz(mdir / 'modes.xyz', atoms, rec['mode_freqs'], rec['modes'])
        for i, f in enumerate(rec['mode_freqs']):
            summary_rows.append({
                'molecule': mol_name, 'method': tag, 'mode_index': i,
                'frequency_cm1': float(f), 'is_reference_method': tag == ref_tag,
            })
    # mode matching: reference vs each other method
    match_out = mol_out / 'matching'
    match_out.mkdir(parents=True, exist_ok=True)
    ref_pos = ref_atoms.get_positions()
    masses = ref_atoms.get_masses()
    for tag in methods:
        if tag == ref_tag:
            continue
        tgt = load_method(mol_name, tag, workdir=workdir)
        matches = match_modes(
            ref['mode_freqs'], ref['modes'], tgt['mode_freqs'], tgt['modes'], masses,
            ref_pos=ref_pos, tgt_pos=tgt['atoms'].get_positions(), align=True,
        )
        stem = f'{ref_tag}_vs_{tag}'
        _write_json(match_out / f'{stem}.json', {
            'reference_method': ref_tag, 'target_method': tag,
            'geometry_rmsd_A': geometry_rmsd(ref_pos, tgt['atoms'].get_positions()),
            'assignment': 'Hungarian on mass-weighted cosine similarity',
            'pairs': matches,
        })
        with open(match_out / f'{stem}.csv', 'w', newline='') as fp:
            w = csv.DictWriter(fp, fieldnames=['ref_idx', 'tgt_idx', 'ref_freq', 'tgt_freq', 'delta_freq', 'cosine', 'rmse'])
            w.writeheader()
            w.writerows(matches)
    return summary_rows, mol_meta


def _write_readme(out_root):
    text = f"""# SiCH Small Molecule Vibration Export (v{EXPORT_VERSION})

Self-contained reference data for fitting classical molecular force fields (bond/angle springs)
to reproduce harmonic vibrations of CH4, C2H6, SiH4, Si2H6.

**No access to CompChemUtils scripts is required** — all arrays, units, and topology are in this folder.

## Folder layout

```
SiCH_small_export/
  manifest.json           # global metadata
  README.md               # this file
  SCHEMA.md               # array / JSON field definitions
  summary_all_modes.csv   # all molecules, all methods, all frequencies
  CH4/
    molecule.json         # topology, reference geometry, connectivity
    equilibrium_reference.xyz
    methods/
      pyscf_b3lyp_cc-pVDZ/
        meta.json         # method-specific metadata
        vibrations.npz    # machine-readable arrays
        frequencies.csv   # human-readable frequency table
        modes.xyz         # human-readable eigenvectors (multi-frame XYZ)
        relaxed.xyz       # geometry used for this method's Hessian
      dftb_.../
    matching/
      pyscf_..._vs_dftb_....csv/json
```

## Recommended reference for fitting

Use **`pyscf_b3lyp_cc-pVDZ`** as primary target (analytical DFT Hessian).
DFTB+ SK sets are secondary benchmarks (mio/3ob for C,H; matsci/pbc for Si,H).

## Geometry note

Each method relaxed its **own** equilibrium structure (RMSD vs PySCF reference typically 0.002–0.03 A).
`equilibrium_reference.xyz` / `molecule.json` give the PySCF reference frame.
`methods/<tag>/relaxed.xyz` is the geometry at which that method's Hessian was computed.

## Units

| Quantity | Unit |
|----------|------|
| Positions | Angstrom |
| Masses | amu |
| Frequencies | cm^-1 |
| Hessian (export) | eV / Angstrom^2 |
| Mode vectors | Angstrom (Cartesian displacements) |

## Loading NPZ (Python example)

```python
import numpy as np
d = np.load('CH4/methods/pyscf_b3lyp_cc-pVDZ/vibrations.npz', allow_pickle=True)
H = d['hessian_3N_eV_Ang2']       # (3N, 3N)
nu = d['frequencies_cm1']         # (n_vib,)
modes = d['modes_cartesian']      # (n_vib, N, 3)
pos = d['positions_A']            # (N, 3)
m = d['masses_amu']               # (N,)
```

## Fitting workflow (classical springs)

1. Read `molecule.json` → bonds, angles, reference geometry.
2. Assign initial force constants K_bond, K_angle.
3. Build Cartesian Hessian H_classical at `positions_A` (same geometry as target method).
4. Compare either:
   - **Spectrum fit**: eigenfrequencies of H_classical vs `frequencies_cm1`
   - **Matrix fit**: Frobenius norm ||H_classical - H_QM||_F
5. Use `matching/*.csv` to pair modes when comparing DFTB to PySCF.

## Generated

{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}
"""
    (out_root / 'README.md').write_text(text)


def _write_schema(out_root):
    schema = """# Data schema

## manifest.json
- `export_version`, `created_utc`, `molecules[]`, `reference_method`, `units`

## molecule.json
- `symbols`, `masses_amu`, `positions_reference_A`
- `connectivity.bonds[]`: {i, j, r0_A, symbols}
- `connectivity.angles[]`: {i, j, k, theta0_deg}  (j central)

## vibrations.npz
| Array | Shape | Description |
|-------|-------|-------------|
| positions_A | (N,3) | Equilibrium geometry for this method |
| masses_amu | (N,) | Atomic masses |
| symbols | (N,) | Element symbols (unicode strings) |
| frequencies_cm1 | (n_vib,) | Harmonic vibrational frequencies |
| modes_cartesian | (n_vib,N,3) | Normal mode vectors (Å) |
| hessian_3N_eV_Ang2 | (3N,3N) | Cartesian Hessian d²E/dxᵢdxⱼ |

## matching/*.json
- `pairs[]`: ref_idx, tgt_idx, ref_freq, tgt_freq, delta_freq, cosine, rmse
- cosine: mass-weighted eigenvector similarity [0,1]
- rmse: RMS difference of signed-aligned unit mode vectors
"""
    (out_root / 'SCHEMA.md').write_text(schema)


def export_sich_bundle(workdir='results', out_dir='SiCH_small_export', molecules=None):
    """Export full SiCH small benchmark bundle."""
    workdir = Path(workdir)
    out_root = Path(out_dir)
    if out_root.exists():
        shutil.rmtree(out_root)
    out_root.mkdir(parents=True)
    mols = molecules or [m for m in SICH_MOLECULES if discover_methods(m, str(workdir))]
    all_summary = []
    mol_metas = {}
    for mol in mols:
        print(f'[export] {mol}')
        rows, meta = export_molecule(mol, str(workdir), out_root)
        all_summary.extend(rows)
        mol_metas[mol] = meta
    # global summary CSV
    with open(out_root / 'summary_all_modes.csv', 'w', newline='') as fp:
        if all_summary:
            w = csv.DictWriter(fp, fieldnames=list(all_summary[0].keys()))
            w.writeheader()
            w.writerows(all_summary)
    manifest = {
        'export_version': EXPORT_VERSION,
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'purpose': 'Classical force-field fitting to harmonic vibrations (SiCH small molecules)',
        'molecules': mols,
        'reference_method': REF_METHOD,
        'units': {
            'length': 'Angstrom', 'mass': 'amu', 'frequency': 'cm^-1',
            'hessian': 'eV/Angstrom^2', 'energy': 'eV',
        },
        'methods_documented': METHOD_INFO,
        'geometry_policy': 'Each QM method uses its own relaxed geometry; PySCF geometry is reference in molecule.json',
        'source_workdir': str(workdir.resolve()),
        'files_per_method': ['meta.json', 'vibrations.npz', 'frequencies.csv', 'modes.xyz', 'relaxed.xyz'],
    }
    _write_json(out_root / 'manifest.json', manifest)
    _write_schema(out_root)
    _write_readme(out_root)
    print(f'[export] Done -> {out_root.resolve()}')
    return out_root
