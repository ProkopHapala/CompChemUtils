# tSiNCs

Molecular vibrational spectra pipeline — PySCF (analytical Hessian), DFTB+, MMFF, GPAW, CP2K, Psi4 backends with consolidated `.npy` caching (no scattered ASE JSON). Unified CLI in `vib_spectra.py`.

- **vib_spectra.py** — main entry: subcommands `run`, `plot`, `match`, `export`, `bundle`, `migrate`, `list`
- **vib_utils.py** — calculators, optimization, Hessian extraction, mode export, per-backend pipelines
- **vib_store.py** — hierarchical cache layout `workdir/<mol>/<method>/`
- **vib_plot.py** — stick/Gaussian overlay plotting helpers
- **vib_match.py** — assign modes between methods via mass-weighted eigenvector projection
- **vib_export.py** — backfill `modes.npy` from cached Hessians; bundle export for external FF fitting
- **run_vib_spectra.py** / **plot_vib_spectra.py** — deprecated wrappers → use `vib_spectra.py`
- **plot_modes_arrows.py** — vector arrows on normal-mode displacements
- **mmff_molecular_session.py** — interactive MMFF vibrational exploration
- **fit_mmff_ch4.py** / **fit_mmff_c2h6.py** — scale MMFF force constants to match reference modes
- **analyze_ch4_modes.py** / **analyze_c2h6_modes.py** / **analyze_adamantane_modes.py** — mode assignment tables vs reference
- **MMFF_VIBRATION_FITTING_REPORT.md** — fitting results summary
- **CP2K_INSTALLATION_GUIDE.md** / **GPU_Acceletated_QM_packages.md** / **VibSpectra_ASE.md** — setup notes
- **pyscf/** — PySCF/GPU tests and basis listing — [`pyscf/README.md`](pyscf/README.md)
- **orca/** — ORCA MPI example inputs — [`orca/README.md`](orca/README.md)
- **SiNCs_notes/** — result writeups — [`SiNCs_notes/README.md`](SiNCs_notes/README.md)

Bulk crystal phonons (periodic) live in [`../phonons/README.md`](../phonons/README.md), not here.
