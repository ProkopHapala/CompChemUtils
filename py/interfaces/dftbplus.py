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
                 opt: bool = False, hamiltonian='DFTB'):
        if sk_path is not None and not os.path.isdir(sk_path):
            raise FileNotFoundError(f"DFTBPlusBackend: Slater-Koster path not found: {sk_path}")
        self.sk_path = sk_path
        self.method = (method or '').strip()
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
        p = {
            'Hamiltonian_SCC': 'Yes' if self.scc else 'No',
            'Hamiltonian_MaxAngularMomentum_': '',
            'Hamiltonian_SlaterKosterFiles_Prefix': self.sk_path,
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
        self.check('energy')
        atoms = self._to_ase(geom)
        if self.sk_path is None:
            raise RuntimeError("DFTBPlusBackend: sk_path must be set for local execution")
        p = self._make_params(atoms.get_chemical_symbols())
        from ase.calculators.dftb import Dftb
        calc = Dftb(**p)
        atoms.calc = calc
        return float(atoms.get_potential_energy())

    def run_relax(self, geom, method=None, basis=None, constraints=None,
                  fmax=0.05, maxsteps=200, **kw):
        self.check('relax')
        from ase.optimize import BFGS
        atoms = self._to_ase(geom)
        if self.sk_path is None:
            raise RuntimeError("DFTBPlusBackend: sk_path must be set for local execution")
        p = self._make_params(atoms.get_chemical_symbols())
        p['Driver_'] = ''
        p['Driver_MaxSteps'] = str(maxsteps)
        p['Driver_MaxForceComponent [eV/AA]'] = str(fmax)
        from ase.calculators.dftb import Dftb
        calc = Dftb(**p)
        atoms.calc = calc
        if constraints:
            cstrs = []
            for c in constraints:
                if c.type == 'freeze_atoms':
                    from ase.constraints import FixAtoms
                    cstrs.append(FixAtoms(indices=c.atoms))
            if cstrs:
                atoms.set_constraint(cstrs)
        BFGS(atoms, maxstep=0.2).run(fmax=fmax, steps=maxsteps)
        apos, es = self._from_ase(atoms)
        if hasattr(geom, 'apos'):
            from ..AtomicSystem import AtomicSystem
            out = AtomicSystem(); out.apos = apos; out.enames = es
            out.lvec = atoms.cell.array if atoms.cell.rank > 0 else None
            return out
        return (apos, es)

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

    # ---- export: write dftb_in.hsd + optional Python runner
    def _write_hsd(self, atoms, fname, driver=None, delta=1e-4):
        """Write a standalone dftb_in.hsd file."""
        es = atoms.get_chemical_symbols()
        ma = self._max_ang_mom(es)
        with open(fname, 'w') as f:
            f.write("Geometry = GenFormat {\n")
            f.write('  <<< "geo.gen"\n')
            f.write("}\n\n")
            f.write("Hamiltonian = DFTB {\n")
            if self.scc:
                f.write("  SCC = Yes\n")
            if self.orbital_resolved_scc:
                f.write("  OrbitalResolvedSCC = Yes\n")
            f.write("  SlaterKosterFiles = Type2FileNames {\n")
            f.write(f'    Prefix = "{self.sk_path}"\n')
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
                f.write(f"  KPointsAndWeights = SupercellFolding {{ {kp[0]} {kp[1]} {kp[2]} 0.0 0.0 0.0 }}\n")
            f.write("}\n")
            if driver == 'SecondDerivatives':
                f.write("\nAnalysis = {\n")
                f.write(f"  SecondDerivatives {{ Delta = {delta} }}\n")
                f.write("}\n")
            elif driver == 'Optimize':
                f.write("\nDriver = {}\n")
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
        self._write_hsd(atoms, hsd_path, driver='Optimize')
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
