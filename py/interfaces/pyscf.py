"""
py/interfaces/pyscf.py — PySCF backend.

Wraps py/pyscf_utils.py for direct local execution.
"""

import os
import numpy as np
from typing import Optional, List
from ._base import CalculationBackend
from ..tasks.base import RelaxResult, VibResult
from .. import atomicUtils as au

# ============ Constants from pyscf_utils

hartree2eV = 27.211396641308
bohr2A = 0.52917721090380
verbosity = 0
default_conv_params = {
    'gradientmax': 0.45e-6,
    'gradientrms': 0.15e-6,
    'stepmax': 1.8e-3,
    'steprms': 1.2e-3,
}

# ============ Utility functions from pyscf_utils

def unpack_mol(mol, units=bohr2A):
    apos = np.array([a[1] for a in mol._atom]) * units
    es = np.array([a[0] for a in mol._atom])
    return apos, es

def pack_mol(apos, es):
    return [(es[i], apos[i]) for i in range(len(es))]

def printlist(lst):
    for item in lst: print(item)

def printObj(obj):
    printlist(dir(obj))

def saveAtoms(fname, atoms, unit=bohr2A):
    apos = np.array([a[1] for a in atoms]) * unit
    es = [a[0] for a in atoms]
    au.saveXYZ(es, apos, fname)

def preparemol(fname='relaxed.xyz', conv_params=None, atoms='O 0 0 0; H 1 0 0; H 0 1 0'):
    import pyscf
    from pyscf.geomopt.berny_solver import optimize
    if conv_params is None: conv_params = default_conv_params
    if os.path.isfile(fname):
        print("found(%s) => no need for relaxation " % fname)
        mol = pyscf.M(atom=fname)
    else:
        h2o = pyscf.M(atom=atoms)
        h2o.verbose = verbosity
        calc = pyscf.scf.RHF(h2o)
        mol = optimize(calc, maxsteps=1000, **conv_params)
        saveAtoms(fname, mol._atom)
    return mol

def evalHf(inp, params=None):
    import pyscf
    apos, es = inp
    m = pack_mol(apos, es)
    mol = pyscf.M(atom=pack_mol(apos, es))
    mol.verbose = verbosity
    out = pyscf.scf.UHF(mol).run()
    return out.e_tot * hartree2eV

def optHf(atoms, conv_params=None):
    import pyscf
    from pyscf.geomopt.berny_solver import optimize
    if conv_params is None: conv_params = default_conv_params
    print(atoms)
    job = pyscf.M(atom=atoms)
    job.SCF_max_cycle = 100
    job.verbose = verbosity
    calc = pyscf.scf.RHF(job)
    mol = optimize(calc, maxsteps=1000, **conv_params)
    printlist(mol)
    return mol


class PySCFBackend(CalculationBackend):
    """PySCF local execution backend.

    Lazy-loads pyscf_utils to avoid import-time dependency on PySCF.

    engine: 'geometric' (default, pySCF built-in) or 'ase' (ASE BFGS optimizer,
            often faster for metal clusters)
    """
    name = "pyscf"
    capabilities = {'energy', 'relax', 'vibrations', 'density', 'esp', 'fukui'}

    def __init__(self, verbose: int = 0, engine: str = 'geometric'):
        self.verbose = verbose
        self.engine = engine

    def _import_pyscf(self):
        import pyscf
        return pyscf

    # ---- helpers
    def _to_pyscf_mol(self, geom, basis=None, ecp=None):
        """Convert AtomicSystem or (apos, es) tuple to pyscf.M.

        Parameters
        ----------
        basis : str or dict
            Basis set specification (e.g. 'def2-svp' or element dict)
        ecp : str or dict
            ECP specification (e.g. {'Au': 'lanl2dz'})
        """
        pyscf = self._import_pyscf()
        if hasattr(geom, 'apos') and hasattr(geom, 'enames'):
            apos, es = geom.apos, geom.enames
        else:
            apos, es = geom  # (apos, es) tuple
        atom_str = '; '.join(f"{e} {p[0]:.8f} {p[1]:.8f} {p[2]:.8f}" for e, p in zip(es, apos))
        kwargs = {'atom': atom_str, 'verbose': self.verbose}
        if basis is not None:
            kwargs['basis'] = basis
        if ecp is not None:
            kwargs['ecp'] = ecp
        return pyscf.M(**kwargs)

    def _mol_to_geom(self, mol):
        """Extract (apos, es) from an optimized pyscf Mole."""
        return unpack_mol(mol)

    # ---- local execution
    def run_energy(self, geom, method: str = 'hf', basis: Optional[str] = None,
                   ecp=None, **kw) -> float:
        self.check('energy')
        pyscf = self._import_pyscf()
        mol = self._to_pyscf_mol(geom, basis, ecp=ecp)
        if method.lower() in ('hf', 'rhf'):
            E = pyscf.scf.RHF(mol).kernel()
        elif method.lower() == 'uhf':
            E = pyscf.scf.UHF(mol).kernel()
        else:
            calc = pyscf.dft.RKS(mol)
            calc.xc = method
            E = calc.kernel()
        return float(E) * hartree2eV

    def run_relax(self, geom, method: str = 'hf', basis: Optional[str] = None,
                  ecp=None, constraints=None, **kw) -> object:
        """Returns optimized AtomicSystem (or (apos, es) tuple if AtomicSystem unavailable)."""
        self.check('relax')
        pyscf = self._import_pyscf()
        mol = self._to_pyscf_mol(geom, basis, ecp=ecp)
        mol.verbose = self.verbose
        if method.lower() in ('hf', 'rhf'):
            calc = pyscf.scf.RHF(mol)
        elif method.lower() == 'uhf':
            calc = pyscf.scf.UHF(mol)
        else:
            calc = pyscf.dft.RKS(mol)
            calc.xc = method
        # Note: PySCF does not natively handle GeomConstraint — constraints are ignored
        if constraints:
            import warnings
            warnings.warn("PySCFBackend.run_relax(): constraints not yet implemented in PySCF interface; ignored.")
        if self.engine == 'ase':
            return self._relax_ase(geom, calc, constraints=constraints, **kw)
        mol_opt = pyscf.geomopt.optimize(calc)
        apos, es = self._mol_to_geom(mol_opt)
        # Return AtomicSystem if input was one
        if hasattr(geom, 'apos'):
            from ..AtomicSystem import AtomicSystem
            out = AtomicSystem()
            out.apos   = apos
            out.enames = list(es)
            return out
        return (apos, list(es))

    def _relax_ase(self, geom, calc, constraints=None, fmax: float = 0.01,
                   maxsteps: int = 200, **kw) -> object:
        """Relax using ASE BFGS (often faster for metal clusters than geometric internal coords)."""
        import numpy as np
        from ase import Atoms
        from ase.optimize import BFGS
        from ase.calculators.calculator import Calculator

        class _PySCFCalc(Calculator):
            implemented_properties = ['energy', 'forces']
            def __init__(self, calc):
                super().__init__()
                self._calc = calc
            def calculate(self, atoms, properties, system_changes):
                pos = atoms.get_positions()
                self._calc.mol.set_geom_(pos, unit='Ang')
                e = self._calc.kernel()
                grad = self._calc.nuc_grad_method().kernel()
                self.results['energy'] = e * 27.211396641308  # Ha -> eV
                self.results['forces'] = -np.array(grad) * 51.42208712055592  # Ha/Bohr -> eV/A

        apos_in, es_in = (geom.apos, geom.enames) if hasattr(geom, 'apos') else geom
        ase_atoms = Atoms(symbols=es_in, positions=apos_in)
        ase_atoms.calc = _PySCFCalc(calc)

        # Apply freeze_atoms constraints via ASE FixAtoms
        if constraints:
            from ase.constraints import FixAtoms
            freeze_inds = []
            for c in constraints:
                if c.type == 'freeze_atoms':
                    freeze_inds.extend(c.atoms)
            if freeze_inds:
                ase_atoms.set_constraint(FixAtoms(indices=freeze_inds))

        opt = BFGS(ase_atoms)
        opt.run(fmax=fmax, steps=maxsteps)

        apos = np.array(ase_atoms.positions)
        es = list(ase_atoms.get_chemical_symbols())
        if hasattr(geom, 'apos'):
            from ..AtomicSystem import AtomicSystem
            out = AtomicSystem()
            out.apos = apos
            out.enames = es
            return out
        return (apos, es)

    def run_vibrations(self, geom, method: str = 'hf', basis: Optional[str] = None, **kw) -> VibResult:
        self.check('vibrations')
        pyscf = self._import_pyscf()
        mol = self._to_pyscf_mol(geom, basis)
        mol.verbose = self.verbose
        if method.lower() in ('hf', 'rhf'):
            calc = pyscf.scf.RHF(mol)
        else:
            calc = pyscf.dft.RKS(mol); calc.xc = method
        calc.kernel()
        hess = calc.Hessian().kernel()
        from pyscf.hessian import thermo
        freq_info = thermo.harmonic_analysis(mol, hess)
        freqs = freq_info['freq_wavenumber']
        modes = freq_info['norm_mode']
        import numpy as np
        masses = np.array([mol.atom_mass_list()[i] for i in range(mol.natm)])
        return VibResult(geom=geom, frequencies=freqs, modes=modes, masses=masses)
