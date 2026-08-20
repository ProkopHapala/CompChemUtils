"""
tasks/metal_tip.py — metal slab relaxation and interaction energy workflow.

Core function: relax_metal_system() — relaxes an FCC(111) slab (bare or with
adatom) with bottom layers frozen, using GPAW with dipole correction. This is
the foundation for the systematic metal-tip × molecule interaction study
(spec §2 Step 2, §10.3).

Two-cell strategy (spec §5.1b): small z-cell for relaxation (less vacuum),
large z-cell for rigid scans (more vacuum for molecule). This module handles
the relaxation cell; scan cells are set up in the scan driver.
"""

import os, time, json
import numpy as np
from typing import Optional, List
from .base import RelaxResult
from ..geom_engine import freeze_atoms
from ..system_specific.MetalTips import (
    lattice_constant, layer_indices, bottom_layer_indices, slab_to_arrays
)


def relax_metal_system(
    slab, backend, frozen_indices, mode='local',
    outdir='.', fmax=0.05, maxsteps=200, label='metal_slab',
    save_traj=True, save_relaxed_xyz=True, write_meta=True,
    extra_meta=None, **kw):
    """Relax a metal slab with frozen bottom layers.

    This is the core function of the metal-tip study (spec §2 Step 2).
    Handles both local execution and export modes, saves relaxed geometry
    + metadata following the ChemBook protocol.

    Parameters
    ----------
    slab           : ase.Atoms — the slab to relax (with cell + positions set)
    backend        : CalculationBackend (e.g. GPAWBackend) — must support 'relax'
    frozen_indices : list of int — atom indices to freeze (bottom layers)
    mode           : 'local' — run directly; 'export' — write runner script
    outdir         : output directory
    fmax           : max force convergence criterion (eV/Å)
    maxsteps       : max optimization steps
    label          : name for output files (e.g. 'Cu_bare_111_3x3x3')
    save_traj      : save ASE trajectory of relaxation
    save_relaxed_xyz : save relaxed geometry as extended XYZ
    write_meta     : write meta.json with relaxation metadata
    extra_meta     : dict of extra metadata to include in meta.json
    **kw           : passed to backend.run_relax / backend.export_relax

    Returns
    -------
    result : RelaxResult with geom (relaxed), converged, n_steps, energy
    """
    os.makedirs(outdir, exist_ok=True)
    constraints = [freeze_atoms(frozen_indices)]

    # Record initial geometry for provenance
    es_init = list(slab.get_chemical_symbols())
    ps_init = np.array(slab.get_positions())
    cell_init = np.array(slab.get_cell())
    n_atoms = len(slab)
    n_frozen = len(frozen_indices)

    t0 = time.time()
    print(f"[relax_metal_system] {label}: {n_atoms} atoms, {n_frozen} frozen, mode={mode}")

    if mode == 'local':
        from ..AtomicSystem import AtomicSystem
        # Run relaxation directly
        geom_in = AtomicSystem(apos=ps_init, enames=es_init, lvec=cell_init)
        geom_out = backend.run_relax(geom_in, constraints=constraints,
                                     fmax=fmax, maxsteps=maxsteps, **kw)
        t1 = time.time()
        elapsed = t1 - t0

        # Extract relaxed positions
        ps_relaxed = np.array(geom_out.apos)
        es_relaxed = list(geom_out.enames)

        # Get final energy
        from ase import Atoms
        atoms_relaxed = Atoms(symbols=es_relaxed, positions=ps_relaxed,
                              cell=cell_init, pbc=True)
        atoms_relaxed.calc = backend._make_calc()
        E_final = float(atoms_relaxed.get_potential_energy())

        # Verify frozen atoms didn't move
        frozen_disp = np.max(np.linalg.norm(
            ps_relaxed[frozen_indices] - ps_init[frozen_indices], axis=1))
        print(f"[relax_metal_system] {label}: E={E_final:.6f} eV, time={elapsed:.1f}s, "
              f"max_frozen_disp={frozen_disp:.2e} Å")

        # Save relaxed geometry
        if save_traj:
            traj_path = os.path.join(outdir, f'{label}.traj')
            atoms_relaxed.write(traj_path)
            print(f"  Saved: {traj_path}")
        if save_relaxed_xyz:
            xyz_path = os.path.join(outdir, 'relaxed.xyz')
            sys_out = AtomicSystem(apos=ps_relaxed, enames=es_relaxed, lvec=cell_init)
            sys_out.saveXYZ(xyz_path)
            print(f"  Saved: {xyz_path}")

        result = RelaxResult(geom=geom_out, converged=True, n_steps=maxsteps,
                             energies=[E_final])

    elif mode == 'export':
        from ..AtomicSystem import AtomicSystem
        geom_in = AtomicSystem(apos=ps_init, enames=es_init, lvec=cell_init)
        files = backend.export_relax(geom_in, constraints=constraints,
                                     outdir=outdir, fmax=fmax, maxsteps=maxsteps, **kw)
        t1 = time.time()
        elapsed = t1 - t0
        print(f"[relax_metal_system] {label}: exported in {elapsed:.1f}s")
        # Save initial geometry for reference
        if save_relaxed_xyz:
            xyz_path = os.path.join(outdir, 'start.xyz')
            geom_in.saveXYZ(xyz_path)
        result = RelaxResult(geom=geom_in, converged=False, output_files=files)
        E_final = None
        frozen_disp = None

    else:
        raise ValueError(f"relax_metal_system: unknown mode {mode!r}")

    # Write metadata
    if write_meta:
        meta = {
            "schema": "chembook.job.v0.1",
            "title": label,
            "status": "done" if mode == 'local' else "exported",
            "project": "MetalTip_Molecule_interaction",
            "system": {
                "n_atoms": n_atoms,
                "n_frozen": n_frozen,
                "frozen_indices": sorted(frozen_indices),
                "cell": cell_init.tolist(),
            },
            "method": {
                "code": backend.name,
                "xc": getattr(backend, 'xc', 'unknown'),
                "kpts": getattr(backend, 'kpts', None),
                "mode": getattr(backend, 'mode', 'unknown'),
                "ecut": getattr(backend, 'ecut', None),
                "h": getattr(backend, 'h', None),
                "dipole": getattr(backend, 'dipole', None),
                "fmax": fmax,
                "maxsteps": maxsteps,
            },
            "results": {
                "energy_eV": E_final,
                "elapsed_s": elapsed,
                "max_frozen_disp_A": frozen_disp,
            },
            "files": {
                "relaxed": "relaxed.xyz" if save_relaxed_xyz and mode == 'local' else None,
                "trajectory": f"{label}.traj" if save_traj and mode == 'local' else None,
                "exported": files if mode == 'export' else None,
            },
        }
        if extra_meta:
            meta.update(extra_meta)
        meta_path = os.path.join(outdir, 'meta.json')
        with open(meta_path, 'w') as f:
            json.dump(meta, f, indent=2)
        print(f"  Saved: {meta_path}")

    return result


def build_relax_backend(xc='PBE', ecut=400.0, kpts=(1, 1, 1), dipole='z',
                        mode='pw', h=None, spinpol=False, maxiter=333):
    """Build a GPAWBackend configured for metal slab relaxation.

    Defaults follow spec §5.1 (dipole correction in z) and §5.8 (gamma-point
    for initial relaxation). Use denser kpts for refinement.
    """
    from ..interfaces.gpaw import GPAWBackend
    return GPAWBackend(
        kpts=kpts, mode=mode, ecut=ecut, xc=xc,
        spinpol=spinpol, h=h, maxiter=maxiter,
        dipole=dipole,  # spec §5.1: dipole correction at cell boundary below slab
    )


def load_slab_from_job(job_dir):
    """Load a slab geometry from a ChemBook job directory (input/CONTCAR or input/start.xyz).

    Returns (slab_as_ase_Atoms, frozen_indices, adatom_indices, meta).
    """
    from ase.io import read
    import json

    # Load geometry
    contcar = os.path.join(job_dir, 'input', 'CONTCAR')
    xyz = os.path.join(job_dir, 'input', 'start.xyz')
    if os.path.exists(contcar):
        slab = read(contcar)
    elif os.path.exists(xyz):
        slab = read(xyz)
    else:
        raise FileNotFoundError(f"No geometry file in {job_dir}/input/")

    # Load metadata
    meta_path = os.path.join(job_dir, 'meta.json')
    with open(meta_path) as f:
        meta = json.load(f)

    frozen = meta.get('geometry', {}).get('frozen_indices', [])
    adatom_idx = meta.get('geometry', {}).get('adatom_index', None)
    adatom_indices = [adatom_idx] if adatom_idx is not None else \
        meta.get('geometry', {}).get('adatom_indices', [])

    return slab, frozen, adatom_indices, meta
