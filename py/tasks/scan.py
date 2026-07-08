"""
tasks/scan.py — rigid and relaxed scan task orchestration.

Rigid scan:   pre-compute all geometry frames, then evaluate energy for each.
              No QM coupling between frames — can be fully parallelized.

Relaxed scan: step-by-step protocol — take result of previous step,
              apply geometry operation (via step_callback), then relax with
              constraints.  Tight coupling with geom_engine + GeomConstraint.

Supports 'local' and 'export' modes.

Geometry helpers:
  make_scan_grid()           — build an r-grid that is fine near contact, coarser further out
  make_rigid_shift_frames()  — shift a molecular fragment to a series of distances
"""

import os
import numpy as np
from typing import List, Optional, Callable
from .base import ScanResult, RelaxResult
from .relax import relax


def make_scan_grid(r_start=1.5, r_fine_end=2.5, dr_fine=0.1,
                   r_coarse_end=6.0, dr_coarse=0.2, r_inf=20.0):
    """Build a non-uniform distance grid suitable for adsorption scans.

    Grid regions:
      [r_start … r_fine_end]  : step dr_fine  (dense, near contact)
      [r_fine_end … r_coarse_end] : step dr_coarse
      r_inf                   : single far-field point for E_ref subtraction

    Returns
    -------
    numpy array of distances (Å)
    """
    r_fine   = np.arange(r_start, r_fine_end + 1e-9, dr_fine)
    r_coarse = np.arange(r_fine_end + dr_coarse, r_coarse_end + 1e-9, dr_coarse)
    return np.concatenate([r_fine, r_coarse, [r_inf]])


def make_scan_grid_geometric(r_eq, r_min=None, r_max=20.0,
                             dr_fine=0.1, fine_half_width=1.0,
                             span=1.0, dr_geo_init=0.2, dr_geo_factor=2.0,
                             r_1A=6.0, dr_1A=1.0, r_5A_start=15.0, dr_5A=5.0):
    """Bond-distance grid fine near r_eq, geometric coarsening, then 1 Å and 5 Å steps.

    Regions
    -------
    [r_min … r_eq+fine_half_width]     : dr_fine (default 0.1 Å)
    (r_eq+fine_half_width … r_1A]      : each `span` Å band, step doubles (0.2, 0.4, 0.8 … capped at dr_1A)
    [r_1A … r_5A_start]                : dr_1A (default 1.0 Å)
    [r_5A_start … r_max]               : dr_5A (default 5.0 Å), always includes r_max

    Parameters
    ----------
    r_eq : equilibrium bond distance (Å), e.g. O···O from relaxed dimer
    """
    r_min = float(r_min if r_min is not None else max(1.5, r_eq - fine_half_width))
    r_fine_hi = float(r_eq + fine_half_width)
    fine = np.arange(r_min, r_fine_hi + 1e-9, dr_fine)

    geo, r, dr = [], float(r_fine_hi), float(dr_geo_init)
    while r < r_1A - 1e-9:
        band_end = min(r + span, r_1A)
        n_added = 0
        while r + dr <= band_end + 1e-9:
            r = round(r + dr, 6)
            geo.append(r)
            n_added += 1
        if n_added == 0:
            r = round(band_end, 6)
            if not geo or geo[-1] < r - 1e-9:
                geo.append(r)
        dr = min(dr * dr_geo_factor, dr_1A)

    mid_start = max(r_1A, geo[-1] if geo else r_fine_hi)
    mid = np.arange(mid_start, r_5A_start + 1e-9, dr_1A)
    far = list(np.arange(r_5A_start, r_max + 1e-9, dr_5A))
    if not far or far[-1] < r_max - 1e-9:
        far.append(r_max)

    out = np.unique(np.round(np.concatenate([fine, geo, mid, far]), 6))
    out.sort()
    return out


def make_rigid_shift_frames(geom, i_fixed, i_mobile, distances,
                             direction=None, mobile_indices=None):
    """Generate rigid-scan geometry frames by translating a molecular fragment.

    The molecule is shifted so that atom i_mobile is at `distance` from atom i_fixed,
    along `direction` (auto-detected as i_fixed → i_mobile vector if None).
    All atoms in `mobile_indices` (default: all non-cluster atoms) are shifted together.

    Parameters
    ----------
    geom          : AtomicSystem  — reference geometry
    i_fixed       : int — anchor atom index (e.g. apex Au)
    i_mobile      : int — atom on the molecule that defines the bond (e.g. O)
    distances     : array of target distances (Å)
    direction     : unit vector (3,) for shift direction; auto from bond if None
    mobile_indices: list of atom indices to move; auto = all non-Au if None

    Returns
    -------
    list of (distance, AtomicSystem) tuples
    """
    import copy
    apos = np.array(geom.apos)
    es   = list(geom.enames)

    # Auto direction: from fixed atom toward mobile atom
    if direction is None:
        d = apos[i_mobile] - apos[i_fixed]
        direction = d / np.linalg.norm(d)
    else:
        direction = np.array(direction, dtype=float)
        direction /= np.linalg.norm(direction)

    # Auto mobile indices: all non-fixed-element atoms
    if mobile_indices is None:
        fixed_elem = es[i_fixed]
        mobile_indices = [i for i, e in enumerate(es) if e != fixed_elem]

    # Current bond distance
    r0 = np.linalg.norm(apos[i_mobile] - apos[i_fixed])

    frames = []
    for r in distances:
        apos_new = apos.copy()
        shift = direction * (r - r0)  # displacement from current position
        for idx in mobile_indices:
            apos_new[idx] += shift

        from ..AtomicSystem import AtomicSystem
        g = AtomicSystem()
        g.apos   = apos_new
        g.enames = list(es)
        g.natoms = len(es)
        g.qs     = None
        g.Rs     = None
        frames.append((r, g))

    return frames


def rigid_scan(frames, backend, method: str, basis: Optional[str] = None,  mode: str = 'local', outdir: str = '.', **kw) -> ScanResult:
    """Evaluate energy for each pre-generated geometry frame.

    Parameters
    ----------
    frames   : list of (coord_value, AtomicSystem) tuples
    backend  : CalculationBackend
    method, basis : calculation settings
    mode     : 'local' — call backend.run_energy() per frame;
               'export' — call backend.export_scan_frames() for all frames
    """
    if mode == 'local':
        backend.check('energy')
        coords  = []
        energies = []
        geoms    = []
        for coord, geom in frames:
            E = backend.run_energy(geom, method=method, basis=basis, **kw)
            coords.append(coord)
            energies.append(E)
            geoms.append(geom)
        return ScanResult(coords=np.array(coords), energies=np.array(energies), geoms=geoms)

    elif mode == 'export':
        geom_list = [g for _, g in frames]
        coord_list = [c for c, _ in frames]
        files = backend.export_scan_frames(geom_list, method=method, basis=basis,
                                            outdir=outdir, **kw)
        return ScanResult(coords=np.array(coord_list), energies=np.full(len(frames), np.nan),
                          geoms=geom_list, output_files=files)
    else:
        raise ValueError(f"rigid_scan(): unknown mode {mode!r}")


def relaxed_scan(geom_start, backend, method: str, basis: Optional[str] = None,
                 constraints_fn: Optional[Callable] = None,
                 step_callback: Optional[Callable] = None,
                 coord_values=None,
                 mode: str = 'local', outdir: str = '.', **kw) -> ScanResult:
    """Perform a constrained relaxation scan.

    Each step:
    1. Apply step_callback(geom, coord_value) — geometry engine operation.
       Returns modified AtomicSystem (e.g., shift atoms, update constraint value).
    2. Get constraints from constraints_fn(coord_value) — list of GeomConstraint.
    3. Relax with those constraints (or export the relax job).
    4. Use the result as input for the next step.

    Parameters
    ----------
    geom_start    : AtomicSystem  — initial geometry
    backend       : CalculationBackend
    method, basis : calculation settings
    constraints_fn: callable(coord_value) -> List[GeomConstraint];
                    defines constraints at each scan step
    step_callback : callable(geom, coord_value) -> AtomicSystem;
                    geometry engine operation applied before each relax
    coord_values  : iterable of scan coordinate values (e.g. distances, angles)
    mode          : 'local' or 'export'
    outdir        : used in export mode; subdirs per step created automatically
    """
    if coord_values is None:
        raise ValueError("relaxed_scan(): coord_values must be provided")

    coords   = []
    energies = []
    geoms    = []
    files    = []
    geom_cur = geom_start

    for i, cv in enumerate(coord_values):
        # --- geometry engine step
        if step_callback is not None:
            geom_cur = step_callback(geom_cur, cv)

        # --- constraints for this step
        constraints = None
        if constraints_fn is not None:
            constraints = constraints_fn(cv)

        # --- relax or export
        if mode == 'local':
            res = relax(geom_cur, backend, method=method, basis=basis, constraints=constraints, mode='local', **kw)
            geom_cur = res.geom
            # energy: try to extract from backend energy call if not in RelaxResult
            try:
                E = backend.run_energy(geom_cur, method=method, basis=basis)
            except Exception:
                E = np.nan
            coords.append(cv)
            energies.append(E)
            geoms.append(geom_cur)

        elif mode == 'export':
            step_dir = os.path.join(outdir, f"step_{i:04d}_cv{cv:.4g}")
            os.makedirs(step_dir, exist_ok=True)
            res = relax(geom_cur, backend, method=method, basis=basis,  constraints=constraints, mode='export', outdir=step_dir, **kw)
            files.extend(res.output_files)
            coords.append(cv)
            energies.append(np.nan)
            geoms.append(geom_cur)
        else:
            raise ValueError(f"relaxed_scan(): unknown mode {mode!r}")

    return ScanResult(coords=np.array(coords), energies=np.array(energies),  geoms=geoms, output_files=files)
