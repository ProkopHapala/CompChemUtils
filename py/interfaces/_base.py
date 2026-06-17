"""
CalculationBackend ABC — base class for all QC program interfaces.

Each concrete backend implements run_* methods for local execution
and/or export_* methods for generating input files (cluster jobs).
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Set


class CalculationBackend(ABC):
    """Abstract base for all QC program backends.

    Subclasses declare `name` and `capabilities` (a set of task strings).
    Supported task keys: 'energy', 'relax', 'vibrations', 'phonons',
                         'density', 'esp', 'fukui', 'resp'.
    """

    name: str = "base"
    capabilities: Set[str] = set()

    def check(self, task: str):
        """Raise NotImplementedError if task is not in capabilities."""
        if task not in self.capabilities:
            raise NotImplementedError(f"{self.name!r} does not support task '{task}'")

    # ------------------------------------------------------------------ #
    # Local execution — override in subclasses that support direct calls  #
    # ------------------------------------------------------------------ #

    def run_energy(self, geom, method: str, basis: Optional[str] = None, **kw) -> float:
        """Compute single-point energy. Returns energy in eV."""
        self.check('energy')
        raise NotImplementedError

    def run_relax(self, geom, method: str, basis: Optional[str] = None,
                  constraints=None, **kw):
        """Geometry optimization. Returns optimized AtomicSystem."""
        self.check('relax')
        raise NotImplementedError

    def run_vibrations(self, geom, method: str, basis: Optional[str] = None, **kw):
        """Compute vibrational frequencies + modes. Returns VibResult."""
        self.check('vibrations')
        raise NotImplementedError

    def run_phonons(self, geom, method: str, basis: Optional[str] = None,
                    kpoints=None, **kw):
        """Compute periodic phonon bands. Returns PhononResult."""
        self.check('phonons')
        raise NotImplementedError

    def run_density(self, geom, method: str, basis: Optional[str] = None,
                    grid=None, **kw):
        """Compute electron density on grid. Returns DensityResult."""
        self.check('density')
        raise NotImplementedError

    def run_esp(self, geom, method: str, basis: Optional[str] = None,
                grid=None, **kw):
        """Compute electrostatic potential on grid."""
        self.check('esp')
        raise NotImplementedError

    def run_fukui(self, geom, method: str, basis: Optional[str] = None,
                  grid=None, **kw):
        """Compute Fukui functions (f+, f-, f0). Returns FukuiResult."""
        self.check('fukui')
        raise NotImplementedError

    def run_resp(self, geom, method: str, basis: Optional[str] = None, **kw):
        """Fit RESP charges. Returns array of charges."""
        self.check('resp')
        raise NotImplementedError

    # ------------------------------------------------------------------ #
    # File export — override in subclasses that support cluster export    #
    # ------------------------------------------------------------------ #

    def export_energy(self, geom, method: str, basis: Optional[str] = None,
                      outdir: str = '.', **kw) -> List[str]:
        """Write input files for a single-point energy job. Returns file paths."""
        raise NotImplementedError(f"{self.name!r} does not support export_energy")

    def export_relax(self, geom, method: str, basis: Optional[str] = None,
                     constraints=None, outdir: str = '.', **kw) -> List[str]:
        """Write input files for a geometry optimization job. Returns file paths."""
        raise NotImplementedError(f"{self.name!r} does not support export_relax")

    def export_vibrations(self, geom, method: str, basis: Optional[str] = None,
                           outdir: str = '.', **kw) -> List[str]:
        """Write input files for a vibrational frequency job. Returns file paths."""
        raise NotImplementedError(f"{self.name!r} does not support export_vibrations")

    def export_scan_frames(self, frames, method: str, basis: Optional[str] = None,
                           outdir: str = '.', **kw) -> List[str]:
        """Write input files for each frame in a scan. Returns file paths."""
        raise NotImplementedError(f"{self.name!r} does not support export_scan_frames")

    def __repr__(self):
        return f"{self.__class__.__name__}(name={self.name!r}, capabilities={sorted(self.capabilities)})"
