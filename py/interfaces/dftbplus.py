"""
py/interfaces/dftbplus.py — DFTB+ backend (SCC-DFTB).

Wraps ASE Dftb calculator for local execution and writes
standalone dftb_in.hsd + Python runner for cluster export.

Key design decision: Slater-Koster (SK) path is *mandatory* and passed
to the backend at construction.  The `method` kwarg maps to dispersion
and SCC options (D3H5, D3, None).
"""

import os
from typing import Optional, List
from ._base import CalculationBackend


class DFTBPlusBackend(CalculationBackend):
    """DFTB+ backend via ASE's Dftb calculator or direct subprocess.

    Parameters
    ----------
    sk_path     : directory containing .skf Slater-Koster files
    method      : dispersion suffix; '' or None = plain SCC-DFTB,
                  'D3' = DFT-D3, 'D3H5' = DFT-D3 with H5 correction
    scc         : enable self-consistent charge (default True)
    orbital_resolved_scc : required for auorg set (default False)
    temperature : electronic temperature in K (default 300)
    kpts        : k-point mesh; None = gamma-only
    maxiter     : max SCC iterations
    opt         : whether to optimize geometry (used by default params)
    """
    name = "dftb+"
    capabilities = {'energy', 'relax', 'vibrations', 'phonons'}

    def __init__(self, sk_path: Optional[str] = None, method: Optional[str] = None,
                 scc: bool = True, orbital_resolved_scc: bool = False,
                 temperature: float = 300.0, kpts=None, maxiter: int = 250,
                 opt: bool = False, hamiltonian=None):
        self.method = (method or '').strip()
        # Auto-detect xTB Hamiltonian from method name
        if hamiltonian is None:
            if self.method.upper() in ('GFN1-XTB', 'GFN2-XTB'):
                hamiltonian = 'xTB'
            else:
                hamiltonian = 'DFTB'
        if sk_path is not None and not os.path.isdir(sk_path):
            raise FileNotFoundError(f"DFTBPlusBackend: Slater-Koster path not found: {sk_path}")
        if hamiltonian == 'DFTB' and sk_path is None:
            raise ValueError("DFTBPlusBackend: sk_path is required for DFTB Hamiltonian")
        self.sk_path = sk_path
        self.scc = scc
        self.orbital_resolved_scc = orbital_resolved_scc
        self.temperature = float(temperature)
        self.kpts = kpts
        self.maxiter = maxiter
        self.opt = opt
        self.hamiltonian = hamiltonian

    def _to_ase(self, geom):
        """Convert AtomicSystem or (apos, es) to ASE Atoms."""
        from ase import Atoms
        if hasattr(geom, 'apos') and hasattr(geom, 'enames'):
            apos, es = geom.apos, list(geom.enames)
            cell = getattr(geom, 'lvec', None)
        else:
            apos, es = geom
            cell = None
        pbc = cell is not None
        atoms = Atoms(symbols=es, positions=apos, cell=cell, pbc=pbc)
        return atoms

    def _from_ase(self, atoms):
        import numpy as np
        return np.array(atoms.positions), list(atoms.get_chemical_symbols())

    def _dispersion_key(self):
        if self.method == 'D3H5':
            return 'DftD3'
        elif self.method == 'D3':
            return 'DftD3'
        return None

    def _max_ang_mom(self, es):
        """Infer MaxAngularMomentum from element symbols."""
        from .. import elements as el
        ma = {}
        for e in set(es):
            # map common element symbols to default angular momentum
            default = {
                'H': 's', 'He': 's',
                'Li': 'p', 'Be': 'p', 'B': 'p', 'C': 'p', 'N': 'p', 'O': 'p', 'F': 'p', 'Ne': 'p',
                'Na': 'p', 'Mg': 'p', 'Al': 'p', 'Si': 'p', 'P': 'p', 'S': 'p', 'Cl': 'p', 'Ar': 'p',
                'K': 'p', 'Ca': 'p',
                'Sc': 'd', 'Ti': 'd', 'V': 'd', 'Cr': 'd', 'Mn': 'd', 'Fe': 'd', 'Co': 'd', 'Ni': 'd',
                'Cu': 'd', 'Zn': 'd',
                'Ga': 'd', 'Ge': 'd', 'As': 'd', 'Se': 'd', 'Br': 'd', 'Kr': 'd',
                'Rb': 'p', 'Sr': 'p',
                'Y': 'd', 'Zr': 'd', 'Nb': 'd', 'Mo': 'd', 'Tc': 'd', 'Ru': 'd', 'Rh': 'd',
                'Pd': 'd', 'Ag': 'd', 'Cd': 'd',
                'In': 'd', 'Sn': 'd', 'Sb': 'd', 'Te': 'd', 'I': 'd', 'Xe': 'd',
                'Cs': 'p', 'Ba': 'p',
                'Hf': 'd', 'Ta': 'd', 'W': 'd', 'Re': 'd', 'Os': 'd', 'Ir': 'd',
                'Pt': 'd', 'Au': 'd', 'Hg': 'd',
                'Tl': 'd', 'Pb': 'd', 'Bi': 'd', 'Po': 'd', 'At': 'd', 'Rn': 'd',
            }
            ma[e] = default.get(e, 'p')
        return ma

    def _make_params(self, es):
        """Build ASE Dftb keyword dictionary from element list."""
        prefix = self.sk_path if self.sk_path.endswith('/') else self.sk_path + '/'
        p = {
            'Hamiltonian_SCC': 'Yes' if self.scc else 'No',
            'Hamiltonian_MaxAngularMomentum_': '',
            'Hamiltonian_SlaterKosterFiles_Prefix': prefix,
            'Hamiltonian_SlaterKosterFiles_Separator': '"-"',
            'Hamiltonian_SlaterKosterFiles_Suffix': '".skf"',
        }
        # MaxAngularMomentum
        for e, am in self._max_ang_mom(es).items():
            p[f'Hamiltonian_MaxAngularMomentum_{e}'] = f'"{am}"'
        if self.orbital_resolved_scc:
            p['Hamiltonian_OrbitalResolvedSCC'] = 'Yes'
        if self.temperature > 0:
            p['Hamiltonian_Filling'] = f'Fermi {{ Temperature [Kelvin] = {self.temperature} }}'
        if self.method in ('D3', 'D3H5'):
            p['Hamiltonian_Dispersion'] = 'DftD3 { Damping = BeckeJohnson {} }'
        # K-points
        if self.kpts is not None:
            kp = self.kpts if isinstance(self.kpts, tuple) else tuple(self.kpts)
            p['Hamiltonian_KPointsAndWeights'] = 'SupercellFolding { %i %i %i 0.0 0.0 0.0 }' % kp
        if self.maxiter != 250:
            p['Hamiltonian_MaxSccIterations'] = str(self.maxiter)
        return p

    # ---- local execution (requires ASE + dftbplus installed)
    def run_energy(self, geom, method=None, basis=None, **kw) -> float:
        """Single-point energy via subprocess dftb+. Returns energy in eV."""
        self.check('energy')
        import tempfile, subprocess, shutil, numpy as np
        atoms = self._to_ase(geom)
        if self.hamiltonian == 'DFTB' and self.sk_path is None:
            raise RuntimeError("DFTBPlusBackend: sk_path must be set for DFTB Hamiltonian")
        wd = tempfile.mkdtemp(prefix='dftb_sp_')
        try:
            self._write_hsd(atoms, os.path.join(wd, 'dftb_in.hsd'), driver=None)
            self._write_gen(atoms, os.path.join(wd, 'geo.gen'))
            r = subprocess.run(['dftb+'], cwd=wd, capture_output=True, text=True)
            if r.returncode != 0:
                raise RuntimeError(f"DFTB+ SP failed:\n{r.stderr[-400:]}")
            # Parse total energy from detailed.out (line: "Total energy: ... <E_Ha> H <E_eV> eV")
            det = os.path.join(wd, 'detailed.out')
            if os.path.exists(det):
                with open(det) as f:
                    for line in f:
                        if 'Total energy:' in line:
                            return float(line.split()[-2])  # already in eV
            # Fallback: parse results.tag (Hartree)
            tag = os.path.join(wd, 'results.tag')
            if os.path.exists(tag):
                with open(tag) as f:
                    lines = f.readlines()
                for i, l in enumerate(lines):
                    if 'total_energy' in l:
                        return float(lines[i+1].strip()) * 27.2114
            raise RuntimeError("DFTB+ SP: could not parse energy")
        finally:
            shutil.rmtree(wd)

    def run_relax(self, geom, method=None, basis=None, constraints=None,
                  fmax=0.05, maxsteps=200, outdir=None, **kw):
        self.check('relax')
        import tempfile
        import subprocess
        import shutil
        import numpy as np

        atoms = self._to_ase(geom)
        if self.hamiltonian == 'DFTB' and self.sk_path is None:
            raise RuntimeError("DFTBPlusBackend: sk_path must be set for DFTB Hamiltonian")

        # Extract moved_atoms from freeze_atoms constraints (1-based indexing for DFTB+)
        moved_atoms = None
        if constraints:
            for c in constraints:
                if c.type == 'freeze_atoms':
                    # DFTB+ MovedAtoms specifies which atoms CAN move
                    all_indices = set(range(len(atoms)))
                    frozen = set(c.atoms)
                    moved = sorted(all_indices - frozen)
                    if moved:
                        moved_atoms = [i + 1 for i in moved]  # 1-based for DFTB+
                    break

        # Use persistent output directory if provided, otherwise temp
        if outdir is None:
            wd = tempfile.mkdtemp(prefix='dftb_relax_')
            cleanup = True
        else:
            os.makedirs(outdir, exist_ok=True)
            wd = outdir
            cleanup = False
        try:
            # Write dftb_in.hsd with Optimize driver
            hsd_path = os.path.join(wd, 'dftb_in.hsd')
            self._write_hsd(atoms, hsd_path, driver='Optimize',
                           moved_atoms=moved_atoms, max_steps=maxsteps,
                           max_force_component=fmax)

            # Write geo.gen
            gen_path = os.path.join(wd, 'geo.gen')
            self._write_gen(atoms, gen_path)

            # Run DFTB+
            result = subprocess.run(['dftb+'], cwd=wd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"DFTB+ stderr:\n{result.stderr}")
                raise RuntimeError(f"DFTB+ failed with code {result.returncode}")

            # Read optimized geometry from geo_end.gen
            if os.path.exists(os.path.join(wd, 'geo_end.gen')):
                apos_out, es_out = self._read_gen(os.path.join(wd, 'geo_end.gen'))
            else:
                raise FileNotFoundError("DFTB+ did not produce geo_end.gen")

            if hasattr(geom, 'apos'):
                from ..AtomicSystem import AtomicSystem
                out = AtomicSystem(); out.apos = apos_out; out.enames = list(es_out)
                out.lvec = atoms.cell.array if atoms.cell.rank > 0 else None
                return out
            return (apos_out, list(es_out))
        finally:
            if cleanup:
                shutil.rmtree(wd)

    def run_vibrations(self, geom, method=None, basis=None, **kw):
        self.check('vibrations')
        # DFTB+ can do hessian via SecondDerivatives driver
        # For now, we export and document; local execution via subprocess
        import tempfile, subprocess
        atoms = self._to_ase(geom)
        wd = tempfile.mkdtemp(prefix='dftb_hess_')
        es = atoms.get_chemical_symbols()
        from py import atomicUtils as au
        au.saveXYZ(es, atoms.positions, os.path.join(wd, 'geo.xyz'))
        # Write dftb_in.hsd with SecondDerivatives driver
        fname = os.path.join(wd, 'dftb_in.hsd')
        self._write_hsd(atoms, fname, driver='SecondDerivatives',
                         delta=kw.get('delta', 1e-4))
        subprocess.run(['dftb+'], cwd=wd, check=True)
        # Parse hessian.out
        from .. import dftb_utils as dftbu  # may not exist in this repo
        # Fallback: read binary / text hessian.out directly
        hess_path = os.path.join(wd, 'hessian.out')
        if os.path.exists(hess_path):
            H = self._read_hessian_out(hess_path, len(atoms))
        else:
            raise FileNotFoundError("DFTB+ did not produce hessian.out")
        from ..tasks.base import VibResult
        import numpy as np
        masses = atoms.get_masses()
        # mass-weight and diagonalize
        n3 = len(atoms) * 3
        m_sqrt = np.repeat(np.sqrt(masses), 3)
        Hmw = H / np.outer(m_sqrt, m_sqrt)
        evals, evecs = np.linalg.eigh(Hmw)
        conv = 108.591
        with np.errstate(invalid='ignore'):
            freqs = np.sign(evals) * np.sqrt(np.abs(evals)) * conv
        return VibResult(geom=geom, frequencies=freqs, modes=evecs.T.reshape(n3, len(atoms), 3), masses=masses)

    def _read_hessian_out(self, fname, n_atoms):
        """Read DFTB+ hessian.out (text: 3N columns, N rows of 3 values each)."""
        import numpy as np
        raw = np.loadtxt(fname)
        n3 = n_atoms * 3
        return raw.reshape(n3, n3)

    def _write_gen(self, atoms, fname):
        """Write DFTB+ GenFormat geometry file."""
        es = atoms.get_chemical_symbols()
        apos = atoms.positions
        unique_es = sorted(set(es))
        elem_map = {e: i+1 for i, e in enumerate(unique_es)}
        with open(fname, 'w') as f:
            f.write(f"{len(es)}  C\n")
            f.write(" ".join(unique_es) + "\n")
            for i, (e, pos) in enumerate(zip(es, apos)):
                f.write(f"{elem_map[e]}  {pos[0]:.15f}  {pos[1]:.15f}  {pos[2]:.15f}\n")

    def _read_gen(self, fname):
        """Read DFTB+ GenFormat geometry file.

        Format:
        Line 1: natoms coord_type
        Line 2: unique_elements (space-separated)
        Lines 3+: atom_number element_index x y z

        Note: atom_number is sequential (1-based), element_index is index into unique_elements list (1-based).
        """
        import numpy as np
        with open(fname) as f:
            lines = f.readlines()
        parts = lines[0].strip().split()
        natoms = int(parts[0])
        # Element names on second line (may have leading spaces)
        unique_es = lines[1].strip().split()
        apos = []
        es = []
        for i, line in enumerate(lines[2:2+natoms]):
            parts = line.strip().split()
            # First column is atom number (ignore), second is element index (1-based)
            elem_idx = int(parts[1]) - 1  # convert to 0-based
            if elem_idx < len(unique_es):
                es.append(unique_es[elem_idx])
            else:
                raise ValueError(f"Element index {elem_idx} (0-based) out of range for unique_es={unique_es}")
            apos.append([float(parts[2]), float(parts[3]), float(parts[4])])
        return np.array(apos), es

    # ---- export: write dftb_in.hsd + optional Python runner
    def _write_hsd(self, atoms, fname, driver=None, delta=1e-4, moved_atoms=None, max_steps=200, max_force_component=0.05):
        """Write a standalone dftb_in.hsd file."""
        es = atoms.get_chemical_symbols()
        with open(fname, 'w') as f:
            f.write("Geometry = GenFormat {\n")
            f.write('  <<< "geo.gen"\n')
            f.write("}\n\n")
            if self.hamiltonian == 'xTB':
                f.write('Hamiltonian = xTB {\n')
                f.write(f'  Method = "{self.method}"\n')
                if self.kpts is not None:
                    kp = self.kpts if isinstance(self.kpts, tuple) else tuple(self.kpts)
                    if all(k == 1 for k in kp):
                        # Gamma point only
                        f.write("  KPointsAndWeights {\n")
                        f.write("    0.0 0.0 0.0  1.0\n")
                        f.write("  }\n")
                    else:
                        # Supercell folding for k-point mesh
                        f.write(f"  KPointsAndWeights = SupercellFolding {{ {kp[0]} {kp[1]} {kp[2]} 0.0 0.0 0.0 }}\n")
                # Looser tolerance for GFN2-xTB convergence
                if self.method == 'GFN2-xTB':
                    f.write("  SCCTolerance = 1.0E-4\n")
                else:
                    f.write("  SCCTolerance = 1.0E-5\n")
                f.write("}\n")
            else:
                ma = self._max_ang_mom(es)
                f.write("Hamiltonian = DFTB {\n")
                if self.scc:
                    f.write("  SCC = Yes\n")
                # OrbitalResolvedSCC not supported in this DFTB+ version
                # if self.orbital_resolved_scc:
                #     f.write("  OrbitalResolvedSCC = Yes\n")
                f.write("  SlaterKosterFiles = Type2FileNames {\n")
                prefix = self.sk_path if self.sk_path.endswith('/') else self.sk_path + '/'
                f.write(f'    Prefix = "{prefix}"\n')
                f.write('    Separator = "-"\n')
                f.write('    Suffix = ".skf"\n')
                f.write("  }\n")
                f.write("  MaxAngularMomentum = {\n")
                for e, am in ma.items():
                    f.write(f'    {e} = "{am}"\n')
                f.write("  }\n")
                if self.temperature > 0:
                    f.write(f"  Filling = Fermi {{ Temperature [Kelvin] = {self.temperature} }}\n")
                if self.method in ('D3', 'D3H5'):
                    f.write("  Dispersion = DftD3 {\n")
                    f.write("    Damping = BeckeJohnson {}\n")
                    f.write("  }\n")
                if self.kpts is not None:
                    kp = self.kpts if isinstance(self.kpts, tuple) else tuple(self.kpts)
                    if all(k == 1 for k in kp):
                        # Gamma point only
                        f.write("  KPointsAndWeights {\n")
                        f.write("    0.0 0.0 0.0  1.0\n")
                        f.write("  }\n")
                    else:
                        # Supercell folding for k-point mesh
                        f.write(f"  KPointsAndWeights = SupercellFolding {{ {kp[0]} {kp[1]} {kp[2]} 0.0 0.0 0.0 }}\n")
                f.write("}\n")
            if driver == 'SecondDerivatives':
                f.write("\nAnalysis = {\n")
                f.write(f"  SecondDerivatives {{ Delta = {delta} }}\n")
                f.write("}\n")
            elif driver == 'Optimize':
                f.write("\nDriver = ConjugateGradient {\n")
                if moved_atoms is not None:
                    import numpy as np
                    if isinstance(moved_atoms, (list, tuple, np.ndarray)):
                        ma_idx = [int(i) for i in moved_atoms]
                        ma_idx = sorted(set(ma_idx))
                        if len(ma_idx) == 0:
                            raise ValueError('DFTBPlusBackend._write_hsd(): moved_atoms is empty')
                        contiguous = (ma_idx[-1] - ma_idx[0] + 1) == len(ma_idx)
                        if contiguous:
                            moved_atoms_str = f"{ma_idx[0]}:{ma_idx[-1]}"
                        else:
                            moved_atoms_str = "{ " + " ".join(str(i) for i in ma_idx) + " }"
                    else:
                        moved_atoms_str = str(moved_atoms)
                    f.write(f"  MovedAtoms = {moved_atoms_str}\n")
                f.write(f"  MaxSteps = {int(max_steps)}\n")
                f.write(f"  MaxForceComponent = {float(max_force_component)}\n")
                f.write("}\n")
            f.write("\nOptions {\n")
            f.write("  WriteResultsTag = Yes\n")
            f.write("}\n")

    def export_energy(self, geom, method=None, basis=None, outdir='.', fname='dftb_in.hsd', **kw) -> List[str]:
        atoms = self._to_ase(geom)
        os.makedirs(outdir, exist_ok=True)
        hsd_path = os.path.join(outdir, fname)
        self._write_hsd(atoms, hsd_path)
        # Also write geo.gen (DFTB+ GenFormat)
        gen_path = os.path.join(outdir, 'geo.gen')
        self._write_gen(atoms, gen_path)
        return [hsd_path, gen_path]

    def export_relax(self, geom, method=None, basis=None, constraints=None,
                     outdir='.', fname='dftb_in.hsd', **kw) -> List[str]:
        atoms = self._to_ase(geom)
        os.makedirs(outdir, exist_ok=True)
        hsd_path = os.path.join(outdir, fname)
        moved_atoms = kw.get('moved_atoms', None)
        max_steps = kw.get('max_steps', 200)
        max_force_component = kw.get('max_force_component', 0.05)
        self._write_hsd(atoms, hsd_path, driver='Optimize', moved_atoms=moved_atoms, max_steps=max_steps, max_force_component=max_force_component)
        gen_path = os.path.join(outdir, 'geo.gen')
        self._write_gen(atoms, gen_path)
        return [hsd_path, gen_path]

    def export_vibrations(self, geom, method=None, basis=None, outdir='.',
                          fname='dftb_in.hsd', delta=1e-4, **kw) -> List[str]:
        atoms = self._to_ase(geom)
        os.makedirs(outdir, exist_ok=True)
        hsd_path = os.path.join(outdir, fname)
        self._write_hsd(atoms, hsd_path, driver='SecondDerivatives', delta=delta)
        gen_path = os.path.join(outdir, 'geo.gen')
        self._write_gen(atoms, gen_path)
        return [hsd_path, gen_path]

    def _write_gen(self, atoms, fname):
        """Write ASE-style GenFormat file."""
        from ase.io import write
        write(fname, atoms, format='dftb')
