"""
Result dataclasses for all task types.
These are plain data containers — no computation here.
"""

from dataclasses import dataclass, field
from typing import List, Optional
import numpy as np


@dataclass
class RelaxResult:
    """Result of a geometry relaxation."""
    geom: object           # AtomicSystem with optimized positions
    energies: List[float] = field(default_factory=list)  # per-step energies (eV)
    converged: bool = False
    n_steps: int = 0
    output_files: List[str] = field(default_factory=list)


@dataclass
class ScanResult:
    """Result of a rigid or relaxed scan."""
    coords: np.ndarray              # scan coordinate values (shape: [n_frames])
    energies: np.ndarray            # energies (eV), shape: [n_frames]
    geoms: List[object] = field(default_factory=list)   # AtomicSystem per frame
    comments: List[str] = field(default_factory=list)   # per-frame comment strings
    output_files: List[str] = field(default_factory=list)

    def __post_init__(self):
        self.coords   = np.asarray(self.coords)
        self.energies = np.asarray(self.energies)


@dataclass
class VibResult:
    """Result of a vibrational frequency calculation."""
    geom: object                    # AtomicSystem (relaxed geometry used)
    frequencies: np.ndarray         # wavenumbers (cm^-1), shape: [3N-6]
    modes: np.ndarray               # mass-weighted eigenvectors, shape: [3N-6, N, 3]
    masses: np.ndarray              # atomic masses (amu), shape: [N]
    ir_intensities: Optional[np.ndarray] = None   # shape: [3N-6]
    raman_activities: Optional[np.ndarray] = None
    output_files: List[str] = field(default_factory=list)

    def __post_init__(self):
        self.frequencies = np.asarray(self.frequencies)
        self.modes       = np.asarray(self.modes)
        self.masses      = np.asarray(self.masses)


@dataclass
class FukuiResult:
    """Result of a Fukui function calculation."""
    geom: object
    f_plus:  np.ndarray   # electron density of (N+1) state minus N state
    f_minus: np.ndarray   # N minus (N-1)
    f_zero:  np.ndarray   # (f_plus + f_minus) / 2
    grid_shape: tuple = ()
    grid_origin: Optional[np.ndarray] = None
    grid_vecs: Optional[np.ndarray] = None    # 3 lattice vectors of grid box
    condensed_f_plus:  Optional[np.ndarray] = None   # Mulliken condensed, shape: [N]
    condensed_f_minus: Optional[np.ndarray] = None
    condensed_f_zero:  Optional[np.ndarray] = None
    output_files: List[str] = field(default_factory=list)


@dataclass
class PhononResult:
    """Result of a periodic phonon calculation."""
    q_points: np.ndarray         # q-point path, shape: [n_q, 3]
    frequencies: np.ndarray      # THz or cm^-1, shape: [n_q, n_bands]
    eigenvectors: Optional[np.ndarray] = None   # shape: [n_q, n_bands, 3*N_prim]
    dos_energies: Optional[np.ndarray] = None
    dos_values:   Optional[np.ndarray] = None
    output_files: List[str] = field(default_factory=list)


@dataclass
class InteractionEnergyResult:
    """Result of an interaction energy calculation: E_int = E_whole - E_frag1 - E_frag2."""
    E_int: float                    # interaction energy (eV)
    E_whole: float                    # energy of whole system (eV)
    E_frag1: float                    # energy of fragment 1 (eV)
    E_frag2: float                    # energy of fragment 2 (eV)
    geom_whole: object                # AtomicSystem for whole (possibly relaxed)
    geom_frag1: object                # AtomicSystem for fragment 1 (possibly relaxed)
    geom_frag2: object                # AtomicSystem for fragment 2 (possibly relaxed)
    frag1_inds: np.ndarray            # atom indices for fragment 1
    frag2_inds: np.ndarray            # atom indices for fragment 2
    converged: bool = False
    output_files: List[str] = field(default_factory=list)

    def __post_init__(self):
        self.frag1_inds = np.asarray(self.frag1_inds)
        self.frag2_inds = np.asarray(self.frag2_inds)
