# tPsi4resp

Psi4 RESP charge fitting, fragment jobs, and 1D/2D potential scans — uses `py.interfaces.psi4` and `atomicUtils` orientation helpers.

- **psi4resp.py** — main RESP workflow driver (conda `p4env`, `psi4` + `resp` packages)
- **psi4resp_2.py** — variant RESP run with alternate method/basis blocks
- **psi4scan.py** — local Psi4 scans (H₂O dimer, HCOOH dimer, XYZ movie frames) via `FFFit.linearScan`
- **psi4_scan_jobs.py** — export Psi4 input files for scan batches
- **psi4_scan_getE.py** — harvest energies from completed scan jobs
- **psi4_jobs_frags.py** — fragment-based Psi4 job export (counterpoise-style setups)
- **scan_2d.py** — 2D potential scan (two collective coordinates)
- **scan_2d_jobs.py** — cluster export for 2D scans
- **HBondModel.py** — H-bond dimer model geometry/energy helpers
- **plot_charges.py** — visualize RESP-fitted charges
- **plot_scan_2d.py** / **plot_scan_2d_B3LYP_vs_DFTB.py** — 2D scan surface plots, method comparison

Modern equivalent for rigid scans: `py.tasks.scan` + `Psi4Backend` export mode (see [`/ARCHITECTURE.md`](/ARCHITECTURE.md) Pattern 3).
