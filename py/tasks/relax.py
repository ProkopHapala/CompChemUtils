"""
tasks/relax.py — geometry relaxation task orchestration.

Supports two modes:
  local:  run directly via backend.run_relax()
  export: write input files via backend.export_relax()
"""

from typing import List, Optional
from .base import RelaxResult


def relax(geom, backend, method: str, basis: Optional[str] = None,
          constraints=None, mode: str = 'local', outdir: str = '.', **kw) -> RelaxResult:
    """Run or export a geometry relaxation.

    Parameters
    ----------
    geom        : AtomicSystem  — starting geometry
    backend     : CalculationBackend subclass
    method      : method string, e.g. 'b3lyp', 'pbe', 'gfn2-xtb'
    basis       : basis set string; None for semiempirical methods
    constraints : list of GeomConstraint; None = no constraints
    mode        : 'local' — run directly; 'export' — write input files
    outdir      : output directory (only used in 'export' mode)
    """
    if mode == 'local':
        backend.check('relax')
        geom_out = backend.run_relax(geom, method=method, basis=basis,
                                     constraints=constraints, outdir=outdir, **kw)
        return RelaxResult(geom=geom_out, converged=True)
    elif mode == 'export':
        files = backend.export_relax(geom, method=method, basis=basis,
                                     constraints=constraints, outdir=outdir, **kw)
        return RelaxResult(geom=geom, converged=False, output_files=files)
    else:
        raise ValueError(f"relax(): unknown mode {mode!r}; expected 'local' or 'export'")
