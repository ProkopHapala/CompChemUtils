# Machine-Specific Quantum Chemistry Setup

**Machine:** carbsisYoga (Prokop's Laptop)  
**OS:** Ubuntu 22.04.2 LTS  
**CPU:** Intel Core i5-12500H (12 cores / 16 threads)  
**GPU:** NVIDIA GeForce GTX 1650, 4 GB VRAM (CUDA 12.1, driver 530.41.03)  
**RAM:** 16 GB  
**Last Updated:** July 8, 2026

This document contains machine-specific installation paths, environment variables, and configuration notes for quantum chemistry software on this system. For general usage tutorials, see `doc/CompChem_software_quick_cheatsheet.md`.

**Environment policy:** prefer **one Python stack** — system `python3` + `pip install --user` into `~/.local/`. Avoid spawning extra conda/venv copies unless unavoidable (Psi4 is the one exception). New QC packages: `python3 -m pip install --user <pkg>`.

---

## Table of Contents

1. [System Specs](#1-system-specs)
2. [Directory Structure](#2-directory-structure)
3. [Python Environment](#3-python-environment)
4. [Software Installations](#4-software-installations)
5. [Data and Parameter Sets](#5-data-and-parameter-sets)
6. [Environment Variables](#6-environment-variables)
7. [Additional Software](#7-additional-software)
8. [Quick Reference](#8-quick-reference)
9. [Known Issues & Optional Fixes](#9-known-issues--optional-fixes)

---

## 1. System Specs

| Component | Specification |
|-----------|---------------|
| Hostname | `carbsisYoga` |
| CPU | Intel Core i5-12500H, 12 cores / 16 threads |
| GPU | NVIDIA GeForce GTX 1650, 4 GB VRAM |
| CUDA | 12.1 (driver 530.41.03) |
| RAM | 16 GB |
| Swap | None configured |
| OS | Ubuntu 22.04.2 LTS (kernel 5.19.0-41-generic) |
| **Primary Python** | 3.10.6 (`/usr/bin/python3`) + `~/.local` user packages (~9.8 GB) |
| Conda (legacy) | `~/miniconda3` (~6.7 GB); only needed for Psi4 |

---

## 2. Directory Structure

### Key Directories

```
/home/prokophapala/
├── opt/                               # Installed QC binaries (cmake install prefix)
│   ├── dftbplus/                      # ★ MAIN DFTB+ install (from ~/git/dftbplus fork)
│   ├── dftb-asi/                      # DFTB+ ASI (disabled in bashrc — do not use)
│   ├── dftb+/                         # Earlier DFTB+ build
│   └── asi/                           # ASI library (only for explicit ASI dev)
├── Fireball_Data/                     # Fireball Fdata (HCNOS, HCNOS_ext, HCNO)
├── SIMULATIONS/
│   ├── dftbplus/slakos/               # ★ Full Slater–Koster tree (sk_dir)
│   └── psi4/
├── git/
│   ├── CompChemUtils/
│   │   └── py/dftb/                   # ★ DFTBcore + Grid_dftb + LCAO_*.cl (ported from SPAMMM)
│   ├── dftbplus/                      # ★ Active fork
│   │   ├── _build/app/dftb+/dftb+    # Primary subprocess binary
│   │   └── tools/pythonapi/
│   ├── FireCore/                      # legacy pyBall.DFTB for old examples
│   ├── SPAMMM/                        # upstream of py/dftb port
│   ├── pyscf/, gpaw/, gpu4pyscf/, qmeq/
├── git_SW/                            # Older clones (lammps, etc.)
└── Desktop/CARBSIS/data/              # xTB / PM6 parameter sets (gfn0/1/2-xtb, pm6, …)
```

---

## 3. Python Environment

### Primary: system Python + pip --user

All main QC Python packages live in `~/.local/lib/python3.10/site-packages/`. No venv, no conda activation required for daily work.

```bash
# Install new packages (preferred)
python3 -m pip install --user <package>

# Verify
python3 -c "import pyscf, ase, gpaw, dftbplus, tblite; print('OK')"
```

| Package | Version | Install method |
|---------|---------|----------------|
| `pyscf` | 2.11.0 | `pip install --user` |
| `ase` | 3.28.0 | `pip install --user` |
| `gpaw` | 25.7.0 | `pip install --user` |
| `gpaw-data` | 1.0.1 | `pip install --user` |
| `dftbplus` | 0.1 (dev) | editable: `~/git/dftbplus/tools/pythonapi` |
| `tblite` | 0.6.0 | `pip install --user` (Jul 2026) |
| `numpy` | 1.26.4 | `pip install --user` |

**Not installed:** `gpu4pyscf` (source at `~/git/gpu4pyscf/`), `jupyterlab`, `ash`, `easyxtb`, standalone `xtb` binary.

### Legacy: conda (Psi4 only)

Miniconda exists but should **not** be used for new QC installs.

```bash
conda activate psi4env   # only when running Psi4
python -c "import psi4; print(psi4.__version__)"   # 1.7
```

`psi4env` is Python 3.9 — isolated from the main 3.10 stack. Keep it for Psi4 only; do not duplicate pySCF/GPAW there.

### CompChemUtils machine config

**Configured:** `machine_config.yaml` at repo root (git-ignored). Key paths:

| Key | Path |
|-----|------|
| `tools.dftb_bin` | `~/git/dftbplus/_build/app/dftb+/dftb+` (fork binary) |
| `tools.dftb_bin_installed` | `~/opt/dftbplus/bin/dftb+` (cmake install fallback) |
| `dftb.repo` | `~/git/dftbplus` |
| `dftb.libdftbcore` | `~/opt/dftbplus/lib/libdftbcore.so` → `py.dftb.DFTBcore` |
| `dftb.libdftbplus` | `~/opt/dftbplus/lib/libdftbplus.so` → pip `dftbplus` API |
| `dftb.wfc_data_dir` | `py/dftb/data` (wfc.*.hsd for grid projection) |
| `sk_dir` | `~/SIMULATIONS/dftbplus/slakos` |
| `paths.pyball` | `~/git/FireCore` (legacy `pyBall.DFTB` imports) |
| OpenCL kernels | in-repo `py/dftb/kernels/LCAO_grid.cl`, `LCAO_STM.cl` |

---

## 4. Software Installations

### DFTB+ — three layers on this machine

| Layer | Module / binary | Purpose |
|-------|-----------------|---------|
| **Subprocess** | `~/git/dftbplus/_build/app/dftb+/dftb+` | `DFTBPlusBackend`, relax, phonons |
| **In-process ctypes** | `~/opt/dftbplus/lib/libdftbcore.so` + `py.dftb.DFTBcore` | SCF, DM/H/S/eigenvector export |
| **OpenCL GPU** | `py/dftb/Grid_dftb.py` + `kernels/LCAO_*.cl` | Density/MO grid projection, STM |

**Do not use** `~/opt/dftb-asi/` — segfaults when mixed with other DFTB+ libs.

| Item | Value |
|------|-------|
| **Fork repo** | `~/git/dftbplus/` (commit `55050533` source; binary `f99ff8f3`) |
| **Subprocess binary** | `~/git/dftbplus/_build/app/dftb+/dftb+` (static MKL build) |
| **Installed libs** | `~/opt/dftbplus/lib/` — `libdftbcore.so`, `libdftbplus.so` |
| **Python API (pip)** | editable `~/git/dftbplus/tools/pythonapi` |
| **In-repo Python** | `CompChemUtils/py/dftb/` (ported from SPAMMM) |
| **WFC basis files** | `py/dftb/data/wfc.{3ob-3-1,mio-1-1}.hsd` |

```python
# Subprocess (task backend)
from py.interfaces.dftbplus import DFTBPlusBackend

# In-process + GPU
from py.dftb import DFTBcore, GridProjector
from py import config_loader as cfg
d = DFTBcore(libpath=cfg.dftbcore_lib())
```

**Rebuild note:** `cmake --build ~/git/dftbplus/_build --target dftbcore` currently fails on fork source (`exportSccDebug`); use `opt/dftbplus/lib/libdftbcore.so` until fixed.

### xTB / tblite

| Item | Value |
|------|-------|
| **Standalone `xtb` binary** | Not installed |
| **Python `tblite`** | 0.6.0 in `~/.local` (`pip install --user tblite`) |
| **tblite CLI** | `~/opt/dftbplus/bin/tblite` v0.3.0 (from DFTB+ build) |
| **CompChemUtils** | `XTBBBackend` auto mode → **tblite** (verified working) |
| **GFN via DFTB+** | `DFTBPlusBackend` with `method='GFN1-XTB'` / `'GFN2-XTB'` |

For GFN-FF or g-xTB (no tblite support): install standalone xtb binary to `~/SW/xtb-dist/` and add to PATH — no conda needed.

### pySCF

| Item | Value |
|------|-------|
| **Version** | 2.11.0 |
| **Location** | `~/.local/lib/python3.10/site-packages/` |
| **Source** | `~/git/pyscf/` |
| **Usage** | `python3 -c "import pyscf"` (no conda) |
| **GPU** | Not installed (`~/git/gpu4pyscf/` source only) |

### Psi4

| Item | Value |
|------|-------|
| **Version** | 1.7 |
| **Environment** | `conda activate psi4env` only |
| **Packages** | dftd3 3.2.1, libxc, libint2, pcmsolver |

### GPAW

| Item | Value |
|------|-------|
| **Version** | 25.7.0 |
| **Usage** | `python3 -c "import gpaw"` or `~/.local/bin/gpaw` |
| **Source** | `~/git/gpaw/` |

### ASE

| Item | Value |
|------|-------|
| **Version** | 3.28.0 |
| **CLI** | `~/.local/bin/ase` |
| **GUI** | `ase gui structure.xyz` |

### FireCore / Fireball

| Item | Value |
|------|-------|
| **Source** | `~/git/FireCore/` |
| **Fdata tables** | `~/Fireball_Data/` — `Fdata_HCNO`, `Fdata_HCNOS`, `Fdata_HCNOS_ext` (+ `.tar.gz` archives) |

### LAMMPS

| Item | Value |
|------|-------|
| **System** | `/usr/bin/lmp` (Sep 2021) |
| **Built** | `~/git_SW/lammps/Build/lmp` (Apr 2025) |

### ORCA

Not installed.

---

## 5. Data and Parameter Sets

### DFTB+ Slater–Koster Parameters

**Root:** `/home/prokophapala/SIMULATIONS/dftbplus/slakos/`

Full parameter tree with many sets in subdirectories:

| Subdir | Set | Notes |
|--------|-----|-------|
| `library/3ob-3-1/` | 3ob-3-1 | **DFTB_SK_PATH** target in bashrc |
| `mio/mio-1-1/` | mio-1-1 | Simple organic |
| `auorg/auorg-1-1/` | auorg-1-1 | Au-containing organic |
| `hyb/`, `pbc/`, `matsci-0-3/`, `borg-0-1/`, … | various | See slakos tree |

`DFTB_SK_PATH` currently points to `.../slakos/library/` (3ob only). HSD files can reference other sets by `Prefix`/`Suffix` if paths are set accordingly, or symlink/copy sets into `library/`.

### Fireball Integral Tables

**Location:** `/home/prokophapala/Fireball_Data/`

- `Fdata_HCNOS/` — standard HCNOS set
- `Fdata_HCNOS_ext/` — extended HCNOS
- `Fdata_HCNO/` — HCNO set

### xTB / Semi-Empirical Parameters (CARBSIS)

**Location:** `~/Desktop/CARBSIS/data/` — `gfn0-xtb`, `gfn1-xtb`, `gfn2-xtb`, `gfn-ff`, PM6 variants, etc.

---

## 6. Environment Variables

### Current ~/.bashrc (QC-relevant)

```bash
# CUDA
export PATH="/usr/local/cuda/bin/:$PATH"

# DFTB+ fork (subprocess) + installed libs (ctypes) + Python paths
export DFTB_REPO=/home/prokophapala/git/dftbplus
export DFTB_EXE=/home/prokophapala/git/dftbplus/_build/app/dftb+/dftb+
export DFTB_LIB_PATH=/home/prokophapala/opt/dftbplus/lib/libdftbplus.so
export DFTB_CORE_LIB=/home/prokophapala/opt/dftbplus/lib/libdftbcore.so
export DFTB_SK_PATH=/home/prokophapala/SIMULATIONS/dftbplus/slakos/library/
export PATH=$HOME/git/dftbplus/_build/app/dftb+:$HOME/opt/dftbplus/bin:$PATH
export PYTHONPATH=$HOME/git/FireCore:$HOME/git/dftbplus:$PYTHONPATH
export LD_LIBRARY_PATH=$HOME/opt/dftbplus/lib:$LD_LIBRARY_PATH
# dftb-asi / git_SW _build libs: keep disabled (segfault if mixed)

alias iqmol='BABEL_LIBDIR=/usr/lib/x86_64-linux-gnu/openbabel/3.1.1 \
  BABEL_DATADIR=/usr/share/openbabel/3.1.1 iqmol'
```

Open a **new terminal** (or `source ~/.bashrc`) for PATH changes to take effect.

### Standalone xtb (if installed later)

```bash
export XTBHOME=/home/prokophapala/SW/xtb-dist
export PATH=$XTBHOME/bin:$PATH
```

---

## 7. Additional Software

| Tool | Location |
|------|----------|
| VESTA | `~/SW/VESTA-gtk3/` |
| Avogadro2 | `~/SW/Avogadro2-x86_64.AppImage` |
| IQmol | `/usr/local/bin/iqmol` |
| VMD | `~/bin/vmd` |
| Blender | `~/SW/blender-4.5.1-linux-x64/` |
| PyOpenCL source | `~/SW/pyopencl-2025.2.6/` |

---

## 8. Quick Reference

| Software | How to run | Status |
|----------|------------|--------|
| **DFTB+ subprocess** | `$DFTB_EXE` or `machine_config` → fork binary | Working |
| **DFTBcore** | `from py.dftb import DFTBcore` + `cfg.dftbcore_lib()` | Working |
| **Grid_dftb / STM** | `from py.dftb import GridProjector` (OpenCL) | Working (GTX 1650) |
| DFTB+ Python API | `import dftbplus` | Working |
| xTB (GFN1/2) | `python3` + `tblite` / `XTBBBackend` | Working |
| xTB (GFN-FF, g-xTB) | needs standalone `xtb` binary | Not installed |
| pySCF | `python3 -c "import pyscf"` | Working (CPU) |
| GPAW | `python3 -c "import gpaw"` | Working |
| ASE | `python3 -c "import ase"` | Working |
| Psi4 | `conda activate psi4env` | Working (isolated) |
| Fireball Fdata | `~/Fireball_Data/` | Present |
| LAMMPS | `lmp` or `~/git_SW/lammps/Build/lmp` | Working |

---

## 9. Known Issues & Optional Fixes

| Issue | Notes | Fix |
|-------|-------|-----|
| PATH pointed to broken `dftb-asi` | Segfault from mixed libs | **Fixed** — disabled in bashrc |
| `DFTBPlusBackend` PATH mismatch | Used wrong `dftb+` | **Fixed** — `machine_config` + clean subprocess env |
| No in-repo DFTB grid/STM | Examples needed FireCore `Grid_dftb.cl` | **Fixed** — `py/dftb/` + SPAMMM `LCAO_*.cl` kernels |
| `libdftbcore` not in fork `_build` | `dftbcore` target compile error | Use `opt/dftbplus/lib/libdftbcore.so` until fork fixed |
| No standalone `xtb` | GFN-FF / g-xTB / CREST unavailable | Download binary to `~/SW/xtb-dist/` (no conda) |
| Two DFTB+ source trees | `~/git/dftbplus` (active fork) vs `~/git_SW/dftbplus` | Use `~/git/dftbplus` for dev; `~/opt/dftbplus` for production |
| Disk space | `~/.local` 9.8 GB + miniconda 6.7 GB | Keep single pip --user stack; avoid new conda envs |
| `phonondb_dir` | Not on this machine | Add to `machine_config.yaml` when needed |

### Verify setup

```bash
python3 -c "from py.dftb import DFTBcore, GridProjector; from py import config_loader as c; print('DFTB stack OK')"
python3 -c "from py.interfaces.dftbplus import DFTBPlusBackend; print('backend OK')"
ls ~/Fireball_Data/Fdata_HCNOS >/dev/null && echo "Fireball Fdata OK"
ls ~/SIMULATIONS/dftbplus/slakos/mio/mio-1-1 >/dev/null && echo "slakos OK"
```

---

## Example Scripts (CompChemUtils repo)

- DFTB examples: `examples/dftb/README.md` — prefer `from py.dftb import …` in new scripts
- pySCF: `examples/tSiNCs/pyscf/`
- Psi4: `examples/tPsi4resp/`
- Phonons: `examples/phonons/`
- Fukui: `examples/fukui/`
