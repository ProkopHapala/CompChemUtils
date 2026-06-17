"""
py/interfaces/mmff.py — MMFF94 backend via RDKit.

Supports local energy, relax, and vibration calculations.
No cluster export needed — all runs are fast locally.
"""

from typing import Optional
import numpy as np
from ._base import CalculationBackend
from ..tasks.base import VibResult


class MMFFBackend(CalculationBackend):
    """RDKit MMFF94 force-field backend."""

    name = "mmff"
    capabilities = {'energy', 'relax', 'vibrations'}

    def __init__(self, ff_type: str = 'MMFF94'):
        self.ff_type = ff_type  # 'MMFF94' or 'MMFF94s'

    def _to_rdmol(self, geom):
        """Convert AtomicSystem or (apos, es) to RDKit Mol with positions."""
        from rdkit import Chem
        from rdkit.Chem import AllChem, rdchem
        if hasattr(geom, 'apos') and hasattr(geom, 'enames'):
            apos, es = geom.apos, geom.enames
        else:
            apos, es = geom
        em = rdchem.EditableMol(Chem.RWMol())
        for e in es:
            a = rdchem.Atom(e)
            em.AddAtom(a)
        mol = em.GetMol()
        mol = Chem.RWMol(mol)
        AllChem.EmbedMolecule(mol, AllChem.ETKDG())
        conf = mol.GetConformer()
        for i, p in enumerate(apos):
            conf.SetAtomPosition(i, [float(p[0]), float(p[1]), float(p[2])])
        mol = mol.GetMol()
        return mol

    def _get_ff(self, mol):
        from rdkit.Chem import AllChem
        ff = AllChem.MMFFGetMoleculeForceField(mol, AllChem.MMFFGetMoleculeProperties(mol, mmffVariant=self.ff_type))
        if ff is None:
            raise RuntimeError("MMFFBackend: could not create force field (unrecognized atoms?)")
        return ff

    def run_energy(self, geom, method: str = 'mmff94', basis=None, **kw) -> float:
        self.check('energy')
        mol = self._to_rdmol(geom)
        ff  = self._get_ff(mol)
        return float(ff.CalcEnergy()) * 0.0103643  # kcal/mol → eV

    def run_relax(self, geom, method: str = 'mmff94', basis=None, constraints=None, **kw):
        self.check('relax')
        mol = self._to_rdmol(geom)
        ff  = self._get_ff(mol)
        if constraints:
            for c in constraints:
                if c.type == 'freeze_atoms':
                    for idx in c.atoms:
                        ff.AddFixedPoint(idx)
        ff.Minimize(maxIts=2000)
        conf = mol.GetConformer()
        apos_out = np.array([[conf.GetAtomPosition(i).x,
                               conf.GetAtomPosition(i).y,
                               conf.GetAtomPosition(i).z] for i in range(mol.GetNumAtoms())])
        if hasattr(geom, 'apos'):
            geom_out = geom.__class__.__new__(geom.__class__)
            geom_out.__dict__.update(geom.__dict__)
            geom_out.apos = apos_out
            return geom_out
        es = geom[1] if isinstance(geom, tuple) else geom.enames
        return (apos_out, list(es))

    def run_vibrations(self, geom, method: str = 'mmff94', basis=None, **kw) -> VibResult:
        """Compute MMFF94 Hessian numerically and diagonalize for normal modes."""
        self.check('vibrations')
        mol = self._to_rdmol(geom)
        ff  = self._get_ff(mol)
        na  = mol.GetNumAtoms()
        n3  = na * 3

        # numerical Hessian via finite differences on force field
        dx = 1e-3  # Å
        conf = mol.GetConformer()
        apos0 = np.array([[conf.GetAtomPosition(i).x,
                            conf.GetAtomPosition(i).y,
                            conf.GetAtomPosition(i).z] for i in range(na)])

        H = np.zeros((n3, n3))
        from rdkit.Chem import AllChem
        def get_grad(apos):
            for i, p in enumerate(apos):
                conf.SetAtomPosition(i, [float(p[0]), float(p[1]), float(p[2])])
            ff2 = AllChem.MMFFGetMoleculeForceField(mol, AllChem.MMFFGetMoleculeProperties(mol, mmffVariant=self.ff_type))
            ff2.CalcEnergy()
            g = np.array(ff2.CalcGrad())
            return g.reshape(na, 3)

        for i in range(na):
            for k in range(3):
                ap_p = apos0.copy(); ap_p[i, k] += dx
                ap_m = apos0.copy(); ap_m[i, k] -= dx
                gp = get_grad(ap_p).ravel()
                gm = get_grad(ap_m).ravel()
                H[i*3+k, :] = (gp - gm) / (2 * dx)

        # mass-weight Hessian
        from .. import elements as el
        es = [mol.GetAtomWithIdx(i).GetSymbol() for i in range(na)]
        masses = np.array([el.ELEMENTS_MASS.get(e, 1.0) for e in es])  # amu
        m_sq = np.repeat(np.sqrt(masses), 3)
        Hmw = H / np.outer(m_sq, m_sq)

        evals, evecs = np.linalg.eigh(Hmw)
        # Convert eigenvalues to cm^-1
        # evals in kcal/(mol·Å²·amu), need cm^-1
        # 1 kcal/mol·Å²·amu * conv = cm^-1
        conv = 108.591  # (derived from c, h, Avogadro, unit factors)
        with np.errstate(invalid='ignore'):
            freqs = np.sign(evals) * np.sqrt(np.abs(evals)) * conv
        modes = evecs.T.reshape(n3, na, 3)
        return VibResult(geom=geom, frequencies=freqs, modes=modes, masses=masses)
