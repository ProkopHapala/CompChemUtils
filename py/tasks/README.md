# tasks

Backend-agnostic orchestration of QC calculation types — dispatches to `CalculationBackend.run_*` (local) or `export_*` (cluster input files). No backend-specific logic here; geometry constraints come from `geom_engine.GeomConstraint`.

- **base.py** — result dataclasses only (`RelaxResult`, `ScanResult`, `VibResult`, `FukuiResult`, `PhononResult`, `InteractionEnergyResult`)
- **relax.py** — geometry optimization entry point (`relax`, modes `local`/`export`)
- **scan.py** — rigid and relaxed coordinate scans, non-uniform adsorption grids (`make_scan_grid`, `make_rigid_shift_frames`, `rigid_scan`, `relaxed_scan`)
- **vibrations.py** — harmonic frequency/mode workflow (`vibrations`)
- **interaction_energy.py** — fragment-based binding energy, E_int = E_whole − E_frag1 − E_frag2, optional per-fragment relaxation
- **bake_jobs.py** — generic Fukui cluster job baker: XYZ ingest, charge-state loops (N/N±1), PBS scripts, backend-specific run-script callbacks (`bake_fukui_jobs`, `bake_pbs`)
- **__init__.py** — re-exports result types and `interaction_energy`, `bake_fukui_jobs`
