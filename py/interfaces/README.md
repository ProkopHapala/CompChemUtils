# interfaces

QC program backends — each subclass of `CalculationBackend` declares `name` and `capabilities`, implements `run_*` for local execution and/or `export_*` for cluster job files. Tasks call these; backends never import task modules.

- **_base.py** — `CalculationBackend` ABC, capability guard (`check`), default stubs for energy/relax/vibrations/phonons/density/esp/fukui/resp and export hooks
- **dftbplus.py** — DFTB+ via ASE/subprocess (`DFTBPlusBackend`), SK-parameter Hamiltonian, GenFormat export, Hessian readout; capabilities: energy, relax, vibrations, phonons
- **pyscf.py** — PySCF HF/DFT (`PySCFBackend`), Fukui and grid properties; surface/cluster helpers and legacy `optHf`/`evalHf` utilities
- **psi4.py** — Psi4 local + export (`Psi4Backend`), RESP/ESP, movie-to-batch input export; legacy `psi4resp` workflow functions retained
- **xtb.py** — GFN-xTB semiempirical (`XTBBBackend`), tblite or CLI fallback; capabilities: energy, relax, vibrations
- **gpaw.py** — GPAW plane-wave/LCAO DFT (`GPAWBackend`), slab builders, surface attach movies, density/ESP on grids; capabilities: energy, relax, vibrations, phonons, density, esp
- **mmff.py** — RDKit MMFF94 force field (`MMFFBackend`), fast local-only energy/relax/vibrations via numerical Hessian
- **__init__.py** — exports `CalculationBackend`
