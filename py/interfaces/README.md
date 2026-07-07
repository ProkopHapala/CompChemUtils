# interfaces

QC program **task backends** — each subclass of `CalculationBackend` declares `name` and `capabilities`, implements `run_*` for local execution and/or `export_*` for cluster job files. Tasks call these; backends never import task modules.

Paths and binaries resolve via `machine_config.yaml` (`py/config_loader.py`). Never hard-code `/home/...` in source.

## DFTB+ — two layers

| Layer | Location | Role |
|-------|----------|------|
| **Task backend** | `dftbplus.py` | Subprocess `tools.dftb_bin`, GenFormat export, relax/phonons via ASE |
| **In-process + GPU** | `py/dftb/` | `DFTBcore` ctypes (`dftb.libdftbcore`), OpenCL grid/STM (`kernels/LCAO_*.cl`) |

- `DFTBPlusBackend` — batch workflows, geometry optimization, Hessian export
- `py.dftb.DFTBcore` — SCF in Python, export DM/H/S/eigenvectors without `eigenvec.bin`
- `py.dftb.Grid_dftb` — project density/MOs onto 3D grids; STM kernels in `LCAO_STM.cl`

Workflow: **DFTBcore SCF** → density matrix → **Grid_dftb** OpenCL projection. Same SK files (`sk_dir`) and fork (`dftb.repo`) as the subprocess backend.

Legacy examples import `pyBall.DFTB.*` from FireCore (`paths.pyball`). New code: `from py.dftb import DFTBcore, GridProjector`.

## Other backends

- **_base.py** — `CalculationBackend` ABC, capability guard (`check`), default stubs
- **pyscf.py** — PySCF HF/DFT (`PySCFBackend`); Fukui, grid properties
- **psi4.py** — Psi4 local + export (`Psi4Backend`), RESP/ESP
- **xtb.py** — GFN-xTB (`XTBBBackend`); tblite Python or `xtb` CLI
- **gpaw.py** — GPAW plane-wave/LCAO DFT (`GPAWBackend`)
- **mmff.py** — RDKit MMFF94 (`MMFFBackend`), local-only
- **__init__.py** — exports `CalculationBackend`
