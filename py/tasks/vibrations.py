"""
tasks/vibrations.py — vibrational frequency task orchestration.
"""

from typing import Optional
from .base import VibResult


def vibrations(geom, backend, method: str, basis: Optional[str] = None,
               mode: str = 'local', outdir: str = '.', **kw) -> VibResult:
    """Compute vibrational frequencies and normal modes.

    Parameters
    ----------
    geom        : AtomicSystem
    backend     : CalculationBackend
    method      : e.g. 'b3lyp', 'gfn2-xtb', 'mmff94'
    basis       : basis set; None for semiempirical / force-field
    mode        : 'local' or 'export'
    """
    if mode == 'local':
        backend.check('vibrations')
        return backend.run_vibrations(geom, method=method, basis=basis, **kw)
    elif mode == 'export':
        files = backend.export_vibrations(geom, method=method, basis=basis, outdir=outdir, **kw)
        return VibResult(geom=geom, frequencies=[], modes=[], masses=[], output_files=files)
    else:
        raise ValueError(f"vibrations(): unknown mode {mode!r}")
