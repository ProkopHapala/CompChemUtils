# dftb

DFTB+ examples: rigid/relaxed scans, fragment jobs, orbital/density visualization, and low-level API tests. Most scripts use legacy `pyBall.dftb_utils`; newer work should use `py.interfaces.dftbplus`.

- **dftb.py** — batch parallel DFTB+ relax driver over a workdir of inputs (legacy `pyBall` + subprocess)
- **dftb_scan.py** — 1D rigid scan via `FFFit.linearScan` + DFTB+ single-points
- **dftb_scan_2.py** — variant scan workflow (second geometry set)
- **dftb_scan_getE.py** — extract energies from completed scan directories
- **dftb_scan_jobs.py** — export/batch scan jobs for cluster submission
- **dftb_jobs_frags.py** — fragment-based DFTB+ job generation
- **dftb_post_proc.py** / **dftb_postproc.py** — post-process DFTB+ outputs (energies, geometries)
- **plot_Es.py** — plot scan energy curves from DFTB results
- **example_dftb_lib.py** — minimal `dftb_utils` usage demo
- **example_hessian.py** — DFTB+ Hessian readout and vibrational sanity check
- **example_orbitals.py** — DFTB+ eigenvectors → waveplot cubes → `plotUtils.plot_cube_slice`
- **compare_density_multizeta.py** — compare electron density across SK/zeta variants
- **compare_waveplot_lib.py** — waveplot vs in-process density extraction parity
- **test_python_api.py** — DFTB+ Python/ASE API smoke tests
- **test_waveplot_dftb.py** / **test_waveplot_dftbcore.py** — waveplot integration tests
- **test_dense_projection.py** — dense-basis projection onto DFTB grid (active); `test_dense_projection copy.py`, `test_dense_projection_bak.py` — backups
- **test_3d_grid_density.py** — 3D grid density sampling validation
- **DFTB_docs.md** — consolidated DFTB+ notes from refactoring effort
- **dftb_ASI_level3_interface.md** — ASI Level-3 API notes

Configure SK paths via `machine_config.yaml` (`sk_dir`); do not hard-code personal paths in new scripts.
