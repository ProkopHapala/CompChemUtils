"""
tasks/interaction_energy.py — interaction energy workflow orchestration.

E_int = E_whole - E_frag1 - E_frag2

Workflow:
  1. (optional) Relax whole system with constraints.
  2. Compute single-point energy of whole system.
  3. Split (possibly relaxed) whole into two fragments by atom indices.
  4. (optional) Relax each fragment individually with constraints.
  5. Compute single-point energy of each fragment.
  6. Return E_int and all component energies.

Supports 'local' and 'export' modes.
"""

import os
import numpy as np
from typing import List, Optional
from .base import InteractionEnergyResult
from .relax import relax


def _validate_fragments(geom, frag1, frag2):
    """Check fragment indices are valid, disjoint, and cover all atoms."""
    frag1 = np.asarray(frag1, dtype=int)
    frag2 = np.asarray(frag2, dtype=int)
    natoms = geom.natoms
    if natoms == 0:
        raise ValueError("geometry has zero atoms")
    if np.any(frag1 < 0) or np.any(frag1 >= natoms):
        raise ValueError(f"frag1 indices out of range [0, {natoms})")
    if np.any(frag2 < 0) or np.any(frag2 >= natoms):
        raise ValueError(f"frag2 indices out of range [0, {natoms})")
    if len(np.intersect1d(frag1, frag2)) > 0:
        raise ValueError("frag1 and frag2 must be disjoint")
    if len(np.union1d(frag1, frag2)) != natoms:
        raise ValueError("frag1 and frag2 must together cover all atoms")
    return frag1, frag2


def interaction_energy(geom, backend, frag1, frag2, method: str, basis: Optional[str] = None,
                       relax_whole: bool = False, relax_frag1: bool = False, relax_frag2: bool = False,
                       constraints_whole=None, constraints_frag1=None, constraints_frag2=None,
                       mode: str = 'local', outdir: str = '.', **kw) -> InteractionEnergyResult:
    """Run or export an interaction energy calculation.

    Parameters
    ----------
    geom            : AtomicSystem  — starting geometry of the whole system
    backend         : CalculationBackend subclass
    frag1           : array-like of int — atom indices belonging to fragment 1
    frag2           : array-like of int — atom indices belonging to fragment 2
    method          : method string, e.g. 'b3lyp', 'pbe', 'gfn2-xtb'
    basis           : basis set string; None for semiempirical methods
    relax_whole     : whether to relax the whole system before splitting
    relax_frag1     : whether to relax fragment 1 after splitting
    relax_frag2     : whether to relax fragment 2 after splitting
    constraints_whole : list of GeomConstraint for whole-system relaxation
    constraints_frag1 : list of GeomConstraint for fragment-1 relaxation
    constraints_frag2 : list of GeomConstraint for fragment-2 relaxation
    mode            : 'local' — run calculations directly;
                      'export' — write input files to subdirectories
    outdir          : output directory (only used in 'export' mode)
    **kw            : extra arguments forwarded to backend methods
    """
    frag1, frag2 = _validate_fragments(geom, frag1, frag2)

    if mode == 'local':
        backend.check('energy')

        # --- 1. whole system (optional relax + energy)
        geom_whole = geom
        if relax_whole:
            res_whole = relax(geom_whole, backend, method=method, basis=basis,
                                constraints=constraints_whole, mode='local', **kw)
            geom_whole = res_whole.geom
        E_whole = backend.run_energy(geom_whole, method=method, basis=basis, **kw)

        # --- 2. split into fragments
        geom_frag1 = geom_whole.selectSubset(frag1)
        geom_frag2 = geom_whole.selectSubset(frag2)

        # --- 3. fragment 1 (optional relax + energy)
        if relax_frag1:
            res_f1 = relax(geom_frag1, backend, method=method, basis=basis,
                           constraints=constraints_frag1, mode='local', **kw)
            geom_frag1 = res_f1.geom
        E_frag1 = backend.run_energy(geom_frag1, method=method, basis=basis, **kw)

        # --- 4. fragment 2 (optional relax + energy)
        if relax_frag2:
            res_f2 = relax(geom_frag2, backend, method=method, basis=basis,
                           constraints=constraints_frag2, mode='local', **kw)
            geom_frag2 = res_f2.geom
        E_frag2 = backend.run_energy(geom_frag2, method=method, basis=basis, **kw)

        # --- 5. interaction energy
        E_int = E_whole - E_frag1 - E_frag2

        return InteractionEnergyResult(
            E_int=E_int, E_whole=E_whole, E_frag1=E_frag1, E_frag2=E_frag2,
            geom_whole=geom_whole, geom_frag1=geom_frag1, geom_frag2=geom_frag2,
            frag1_inds=frag1, frag2_inds=frag2, converged=True
        )

    elif mode == 'export':
        files = []

        # --- whole system
        whole_dir = os.path.join(outdir, 'whole')
        os.makedirs(whole_dir, exist_ok=True)
        if relax_whole:
            res = relax(geom, backend, method=method, basis=basis,
                          constraints=constraints_whole, mode='export', outdir=whole_dir, **kw)
            files.extend(res.output_files)
        else:
            files.extend(backend.export_energy(geom, method=method, basis=basis,
                                               outdir=whole_dir, **kw))

        # --- fragments (extract from starting geometry for export)
        geom_frag1 = geom.selectSubset(frag1)
        geom_frag2 = geom.selectSubset(frag2)

        f1_dir = os.path.join(outdir, 'frag1')
        os.makedirs(f1_dir, exist_ok=True)
        if relax_frag1:
            res = relax(geom_frag1, backend, method=method, basis=basis,
                          constraints=constraints_frag1, mode='export', outdir=f1_dir, **kw)
            files.extend(res.output_files)
        else:
            files.extend(backend.export_energy(geom_frag1, method=method, basis=basis,
                                               outdir=f1_dir, **kw))

        f2_dir = os.path.join(outdir, 'frag2')
        os.makedirs(f2_dir, exist_ok=True)
        if relax_frag2:
            res = relax(geom_frag2, backend, method=method, basis=basis,
                          constraints=constraints_frag2, mode='export', outdir=f2_dir, **kw)
            files.extend(res.output_files)
        else:
            files.extend(backend.export_energy(geom_frag2, method=method, basis=basis,
                                               outdir=f2_dir, **kw))

        return InteractionEnergyResult(
            E_int=np.nan, E_whole=np.nan, E_frag1=np.nan, E_frag2=np.nan,
            geom_whole=geom, geom_frag1=geom_frag1, geom_frag2=geom_frag2,
            frag1_inds=frag1, frag2_inds=frag2, converged=False, output_files=files
        )

    else:
        raise ValueError(f"interaction_energy(): unknown mode {mode!r}; expected 'local' or 'export'")
