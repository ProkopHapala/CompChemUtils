#!/usr/bin/env python3
"""Hierarchical layout for vibrational spectra cache and results."""

import json
import shutil
from pathlib import Path
import numpy as np
from ase.io import read, write

# workdir/<mol>/<method_tag>/{relaxed.xyz,freq.npy,hessian.npy,modes.npy,modes.txt,all_modes.xyz,opt.traj}
# workdir/<mol>/plots/{overlay.png,hessian_comparison.png}
# workdir/<mol>/match/<ref>_vs_<tgt>.csv

FLAT_SUFFIXES = ('_freq.npy', '_hessian.npy', '_relaxed.xyz', '_modes.txt', '_all_modes.xyz', '_opt.traj')


def mol_dir(workdir, mol_name):
    return Path(workdir) / mol_name


def method_dir(workdir, mol_name, method_tag):
    return mol_dir(workdir, mol_name) / method_tag


def plots_dir(workdir, mol_name):
    return mol_dir(workdir, mol_name) / 'plots'


def match_dir(workdir, mol_name):
    return mol_dir(workdir, mol_name) / 'match'


def freq_npy_path(mol_name, method_tag, workdir='.'):
    return method_dir(workdir, mol_name, method_tag) / 'freq.npy'


def hessian_npy_path(mol_name, method_tag, workdir='.'):
    return method_dir(workdir, mol_name, method_tag) / 'hessian.npy'


def relaxed_xyz_path(mol_name, method_tag, workdir='.'):
    return method_dir(workdir, mol_name, method_tag) / 'relaxed.xyz'


def modes_npy_path(mol_name, method_tag, workdir='.'):
    return method_dir(workdir, mol_name, method_tag) / 'modes.npy'


def modes_txt_path(mol_name, method_tag, workdir='.'):
    return method_dir(workdir, mol_name, method_tag) / 'modes.txt'


def modes_xyz_path(mol_name, method_tag, workdir='.'):
    return method_dir(workdir, mol_name, method_tag) / 'all_modes.xyz'


def opt_traj_path(mol_name, method_tag, workdir='.'):
    return method_dir(workdir, mol_name, method_tag) / 'opt.traj'


def overlay_png_path(mol_name, workdir='.'):
    return plots_dir(workdir, mol_name) / 'overlay.png'


def match_csv_path(mol_name, ref_tag, tgt_tag, workdir='.'):
    return match_dir(workdir, mol_name) / f'{ref_tag}_vs_{tgt_tag}.csv'


def ensure_method_dir(mol_name, method_tag, workdir='.'):
    d = method_dir(workdir, mol_name, method_tag)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _flat_path(workdir, mol_name, method_tag, suffix):
    return Path(workdir) / f'{mol_name}_{method_tag}{suffix}'


def _is_flat_layout(workdir):
    wd = Path(workdir)
    return any(p.name.endswith('_freq.npy') for p in wd.glob('*_freq.npy'))


def _known_molecule_names(workdir='.'):
    """Molecule names from hierarchical dirs plus legacy flat freq files."""
    wd = Path(workdir)
    names = set()
    for p in wd.iterdir():
        if p.is_dir() and p.name not in ('plots', 'match', '__pycache__'):
            if any((p / sub / 'freq.npy').exists() for sub in p.iterdir() if sub.is_dir()):
                names.add(p.name)
    for p in wd.glob('*_freq.npy'):
        stem = p.stem[:-5] if p.stem.endswith('_freq') else p.stem
        for mol in ('Si10_H', 'adamantane', 'C2H6', 'Si2H6', 'SiH4', 'CH4'):
            if stem.startswith(mol + '_'):
                names.add(mol)
    try:
        from vib_spectra import MOLECULES
        names.update(MOLECULES.keys())
    except ImportError:
        pass
    return sorted(names, key=len, reverse=True)


def _parse_flat_freq_name(path, workdir='.'):
    """CH4_pyscf_b3lyp_cc-pVDZ_freq.npy -> (CH4, pyscf_b3lyp_cc-pVDZ)."""
    stem = path.stem
    if not stem.endswith('_freq'):
        return None, None
    body = stem[:-5]
    for mol in _known_molecule_names(workdir):
        prefix = mol + '_'
        if body.startswith(prefix):
            return mol, body[len(prefix):]
    i = body.find('_')
    if i < 1:
        return None, None
    return body[:i], body[i + 1:]


def discover_methods(mol_name, workdir='.'):
    """Return sorted method tags for molecule (hierarchical layout)."""
    md = mol_dir(workdir, mol_name)
    if not md.is_dir():
        return []
    tags = []
    for p in sorted(md.iterdir()):
        if p.is_dir() and p.name not in ('plots', 'match', '__pycache__') and (p / 'freq.npy').exists():
            tags.append(p.name)
    return tags


def discover_molecules(workdir='.'):
    wd = Path(workdir)
    mols = set()
    for p in wd.glob('*_freq.npy'):
        mol, _ = _parse_flat_freq_name(p, workdir)
        if mol:
            mols.add(mol)
    for p in wd.iterdir():
        if not p.is_dir() or p.name in ('plots', 'match', '__pycache__'):
            continue
        if any((sub / 'freq.npy').exists() for sub in p.iterdir() if sub.is_dir()):
            mols.add(p.name)
    return sorted(mols)


def migrate_flat_to_hierarchical(workdir='.', dry_run=False):
    """Move legacy flat files into workdir/<mol>/<method_tag>/."""
    wd = Path(workdir)
    moved = []
    for freq_path in sorted(wd.glob('*_freq.npy')):
        mol_name, method_tag = _parse_flat_freq_name(freq_path, workdir)
        if not mol_name:
            continue
        dst_dir = method_dir(workdir, mol_name, method_tag)
        mapping = {
            '_freq.npy': 'freq.npy',
            '_hessian.npy': 'hessian.npy',
            '_relaxed.xyz': 'relaxed.xyz',
            '_modes.txt': 'modes.txt',
            '_all_modes.xyz': 'all_modes.xyz',
            '_opt.traj': 'opt.traj',
        }
        for src_suffix, dst_name in mapping.items():
            src = _flat_path(workdir, mol_name, method_tag, src_suffix)
            if not src.exists():
                continue
            dst = dst_dir / dst_name
            if dst.exists():
                continue
            moved.append((src, dst))
            if not dry_run:
                dst_dir.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dst))
    # flat overlay PNGs -> plots/
    for png in sorted(wd.glob('*_vib_overlay.png')):
        mol_name = png.stem.replace('_vib_overlay', '')
        dst = overlay_png_path(mol_name, workdir)
        if dst.exists():
            continue
        moved.append((png, dst))
        if not dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(png), str(dst))
    # flat logs stay in workdir root or move to mol dir
    for log in sorted(wd.glob('*.log')):
        mol_name = log.stem
        if mol_dir(workdir, mol_name).exists():
            dst = mol_dir(workdir, mol_name) / log.name
            if dst.exists():
                continue
            moved.append((log, dst))
            if not dry_run:
                shutil.move(str(log), str(dst))
    return moved


def load_method(mol_name, method_tag, workdir='.', threshold=10.0):
    """Load one method result. Returns dict with atoms, freqs, hessian, modes, mode_freqs."""
    from vib_utils import filter_real_freqs, select_real_modes
    d = method_dir(workdir, mol_name, method_tag)
    freq_path = d / 'freq.npy'
    if not freq_path.exists():
        freq_path = _flat_path(workdir, mol_name, method_tag, '_freq.npy')
    if not freq_path.exists():
        raise FileNotFoundError(f'No frequencies for {mol_name}/{method_tag} in {workdir}')
    freqs = np.load(str(freq_path))
    hess_path = hessian_npy_path(mol_name, method_tag, workdir)
    if not hess_path.exists():
        hess_path = _flat_path(workdir, mol_name, method_tag, '_hessian.npy')
    hessian = np.load(str(hess_path)) if hess_path.exists() else None
    xyz_path = relaxed_xyz_path(mol_name, method_tag, workdir)
    if not xyz_path.exists():
        xyz_path = _flat_path(workdir, mol_name, method_tag, '_relaxed.xyz')
    atoms = read(str(xyz_path)) if xyz_path.exists() else None
    if hessian is not None and atoms is not None:
        all_modes = modes_from_hessian(mol_name, method_tag, workdir, atoms, hessian, freqs)
    elif modes_npy_path(mol_name, method_tag, workdir).exists():
        all_modes = list(np.load(str(modes_npy_path(mol_name, method_tag, workdir))))
        if len(all_modes) != len(freqs):
            raise FileNotFoundError(f'Cannot rebuild full modes for {mol_name}/{method_tag}; missing Hessian')
    else:
        raise FileNotFoundError(f'No Hessian or modes.npy for {mol_name}/{method_tag}')
    mode_freqs, vib_modes = select_real_modes(freqs, all_modes, threshold=threshold)
    return {'mol_name': mol_name, 'method_tag': method_tag, 'atoms': atoms, 'freqs': freqs,
            'all_modes': all_modes, 'mode_freqs': mode_freqs, 'modes': vib_modes,
            'hessian': hessian, 'dir': d}


def modes_from_hessian(mol_name, method_tag, workdir, atoms, hessian, freqs):
    """Rebuild mode list from Hessian when modes.npy missing."""
    from vib_utils import _modes_from_hessian_ase
    if hessian is None or atoms is None:
        raise FileNotFoundError(f'modes.npy missing for {mol_name}/{method_tag}; re-run export')
    if hessian.ndim == 2:
        _, modes_all = _modes_from_hessian_ase(atoms, hessian)
        return list(modes_all)  # 3N modes aligned with ASE freq array
    from pyscf import gto
    from pyscf.hessian import thermo
    syms = atoms.get_chemical_symbols()
    pos = atoms.get_positions()
    atom_str = '; '.join(f'{s} {x:.6f} {y:.6f} {z:.6f}' for s, (x, y, z) in zip(syms, pos))
    basis = 'cc-pVDZ' if 'ccpVDZ' in method_tag or 'cc-pVDZ' in method_tag else 'sto-3g'
    mol = gto.M(atom=atom_str, basis=basis, charge=0, spin=0, verbose=0)
    res = thermo.harmonic_analysis(mol, hessian)
    return [m for m in res['norm_mode']]


def save_modes_npy(mol_name, method_tag, modes, mode_freqs, workdir='.'):
    ensure_method_dir(mol_name, method_tag, workdir)
    np.save(str(modes_npy_path(mol_name, method_tag, workdir)), np.asarray(modes))
    meta = {'method_tag': method_tag, 'n_modes': len(mode_freqs), 'freqs_cm1': [float(f) for f in mode_freqs]}
    with open(method_dir(workdir, mol_name, method_tag) / 'modes_meta.json', 'w') as fp:
        json.dump(meta, fp, indent=2)
