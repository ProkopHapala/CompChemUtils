# Machine-Specific Quantum Chemistry Setup

**Machine:** carbsisYoga (Prokop's Laptop)  
**OS:** Ubuntu 22.04.2 LTS  
**CPU:** Intel Core i5-12500H (12 cores / 16 threads)  
**GPU:** NVIDIA GeForce GTX 1650, 4 GB VRAM (CUDA 12.1, driver 530.41.03)  
**RAM:** 16 GB  
**Last Updated:** July 7, 2026

This document contains machine-specific installation paths, environment variables, and configuration notes for quantum chemistry software on this system. For general usage tutorials, see `doc/CompChem_software_quick_cheatsheet.md`.

**Compared to the GTX3090 desktop:** this laptop has less RAM (16 vs 64 GB), a much smaller GPU (GTX 1650 vs RTX 3090), and several key packages are missing or only partially installed — notably **standalone xTB**, **gpu4pyscf**, and a working **CompChemUtils xTB backend** (see gaps below).

---

## Table of Contents

1. [System Specs](#1-system-specs)
2. [Directory Structure](#2-directory-structure)
3. [Python Environments](#3-python-environments)
4. [Software Installations](#4-software-installations)
5. [Data and Parameter Sets](#5-data-and-parameter-sets)
6. [Environment Variables](#6-environment-variables)
7. [Additional Software](#7-additional-software)
8. [Quick Reference](#8-quick-reference)
9. [Gaps vs Desktop & Recommended Fixes](#9-gaps-vs-desktop--recommended-fixes)

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
| Python (system) | 3.10.6 (`/usr/bin/python3`) |
| Python (conda base) | 3.10.11 |
| Python (psi4env) | 3.9.16 |

---

## 2. Directory Structure

### Key Directories

```
/home/prokophapala/
├── opt/                               # Built QC binaries
│   ├── dftbplus/                      # DFTB+ (main build, May 2025)
│   ├── dftb-asi/                      # DFTB+ with ASI interface (in PATH)
│   ├── dftb+/                         # Earlier DFTB+ build
│   └── asi/                           # ASI library for dftb-asi
├── SIMULATIONS/                       # Central simulation data storage
│   ├── dftbplus/
│   │   └── slakos/library/            # DFTB+ Slater-Koster parameters
│   │       └── 3ob-3-1/             # Bio/organic set
│   └── psi4/                          # Psi4 calculation data
├── SW/                                # Software packages (AppImages, tools)
│   ├── VESTA-gtk3/                    # 3D crystal/molecule visualization
│   ├── Avogadro2-x86_64.AppImage      # Molecular editor
│   ├── blender-4.5.1-linux-x64/       # 3D rendering
│   ├── pyopencl-2025.2.6/             # PyOpenCL source
│   └── Inkscape-*.AppImage            # Vector graphics
├── git/                               # Active development repos
│   ├── CompChemUtils/                 # This repository
│   ├── dftbplus/                      # DFTB+ source + Python API
│   ├── pyscf/                         # PySCF source
│   ├── gpu4pyscf/                     # GPU PySCF source (NOT installed)
│   ├── gpaw/                          # GPAW source
│   ├── FireCore/                      # Fireball DFT
│   └── qmeq/                          # Quantum transport
├── git_SW/                            # Additional source builds
│   ├── dftbplus/                      # DFTB+ source (alternate clone)
│   ├── dftbplus-asi/                  # DFTB+ ASI variant
│   ├── lammps/                        # LAMMPS source (Build/lmp)
│   └── asi/                           # ASI library source
└── Desktop/CARBSIS/data/              # Semi-empirical parameter sets
    ├── gfn0-xtb/
    ├── gfn1-xtb/
    ├── gfn2-xtb/
    └── gfn-ff/
```

---

## 3. Python Environments

### Conda Environments

```bash
# List available environments
conda env list

# Activate Psi4 environment
conda activate psi4env

# Activate base (pySCF, GPAW, ASE, dftbplus Python API)
conda activate base

# Deactivate
conda deactivate
```

**Available environments:**
- `base` — Main QC environment (Python 3.10.11); pySCF, GPAW, ASE, dftbplus Python API
- `psi4env` — Psi4 quantum chemistry (Python 3.9.16)

**Note:** No dedicated `~/venvs/ML` virtualenv like on the GTX3090 desktop. QC packages are split between conda `base` and `~/.local` pip user installs.

### base Conda + pip User Packages (Python 3.10)

| Package | Version | Location |
|---------|---------|----------|
| `pyscf` | 2.11.0 | `~/.local/lib/python3.10/site-packages/` (pip --user) |
| `ase` | 3.28.0 | conda-forge |
| `gpaw` | 25.7.0 | pip |
| `gpaw-data` | 1.0.1 | pip |
| `dftbplus` | 0.1 (dev) | `~/git/dftbplus/tools/pythonapi` (editable install) |

**Not installed (present on GTX3090 desktop):**
- `gpu4pyscf` / `gpu4pyscf-cuda12x` — source at `~/git/gpu4pyscf/` but not built/installed
- `pyscf-dispersion`, `pyscf-semiempirical`
- `lammps` Python package (pip list shows 2021.9.29 but `import lammps` fails in base)
- `jupyterlab`, `nglview`, `py3Dmol`, `ash`, `easyxtb`
- `tblite` Python package (needed for CompChemUtils xTB backend)

### psi4env Conda Package List (Python 3.9)

| Package | Version |
|---------|---------|
| `psi4` | 1.7 |
| `dftd3` | 3.2.1 |
| `libxc` | 5.2.3 |
| `libint2` | 2.7.1 |
| `pcmsolver` | 1.2.1.1 |
| `qcelemental` | 0.25.1 |
| `qcengine` | 0.26.0 |

**Note:** pySCF is **not** in psi4env.

---

## 4. Software Installations

### pySCF

| Item | Value |
|------|-------|
| **Version** | 2.11.0 |
| **Install location** | `~/.local/lib/python3.10/site-packages/pyscf/` |
| **Source** | `~/git/pyscf/` |
| **Environment** | `conda activate base` |
| **GPU support** | **NOT installed** — `gpu4pyscf` source at `~/git/gpu4pyscf/` but `import gpu4pyscf` fails |
| **Test** | `conda activate base && python -c "import pyscf; print(pyscf.__version__)"` |

### xTB (GFN-xTB) — **NOT INSTALLED as standalone**

| Item | Status |
|------|--------|
| **Standalone `xtb` binary** | **Missing** — not in PATH, no `~/SW/xtb-dist/` |
| **`cpx` (CREST)** | **Missing** |
| **`tblite` CLI** | Present at `~/opt/dftbplus/bin/tblite` (v0.3.0), bundled with DFTB+ build |
| **`tblite` Python** | **Missing** — `import tblite` fails |
| **Parameter data** | `~/Desktop/CARBSIS/data/gfn{0,1,2}-xtb/`, `gfn-ff/` |
| **CompChemUtils backend** | `XTBBBackend` auto mode **will fail** — needs `pip install tblite` or standalone xtb in PATH |

**Workaround options:**
1. Install standalone xtb: download to `~/SW/xtb-dist/` and add to PATH (see GTX3090 doc)
2. Install Python tblite: `pip install tblite` (enables GFN1/2 without xtb binary)
3. Use DFTB+ internal xTB mode (`method='GFN1-XTB'` / `'GFN2-XTB'` in `DFTBPlusBackend`)

### DFTB+

Three separate builds exist under `~/opt/`:

| Build | Binary | Notes |
|-------|--------|-------|
| **dftb-asi** | `~/opt/dftb-asi/bin/dftb+` | **Currently in PATH**; ASI interface enabled; prints linker warning about symbol size mismatch |
| **dftbplus** | `~/opt/dftbplus/bin/dftb+` | Referenced by `DFTB_EXE` in `~/.bashrc`; commit 4f9d5821; includes tblite, dftd4, phonons |
| **dftb+** | `~/opt/dftb+/bin/dftb+` | Earlier build (May 2, 2025) |

**Additional binaries in `~/opt/dftbplus/bin/`:**
- `dftb+`, `waveplot`, `modes`, `phonons`, `skderivs`, `setupgeom`
- `tblite` (v0.3.0), `dftd4` (v3.6.0), `s-dftd3`, `mctc-convert`

**Source repositories:**
- `~/git/dftbplus/` — active clone with Python API (`tools/pythonapi/`)
- `~/git_SW/dftbplus/` — alternate clone (commit 06c041d2)
- `~/git_SW/dftbplus-asi/` — ASI variant

**Python API:** editable install from `~/git/dftbplus/tools/pythonapi` → `import dftbplus`

**Known issue:** PATH points to `dftb-asi` binary but `DFTB_EXE` env var points to `dftbplus` binary — inconsistent. CompChemUtils subprocess calls use `dftb+` from PATH (dftb-asi).

### Psi4

| Item | Value |
|------|-------|
| **Version** | 1.7 |
| **Environment** | `conda activate psi4env` |
| **Test** | `conda activate psi4env && python -c "import psi4; print(psi4.__version__)"` |

### GPAW

| Item | Value |
|------|-------|
| **Version** | 25.7.0 |
| **Environment** | `conda activate base` |
| **Binary** | `~/.local/bin/gpaw` |
| **Source** | `~/git/gpaw/` |
| **Data** | gpaw-data 1.0.1 |

### LAMMPS

| Item | Value |
|------|-------|
| **System binary** | `/usr/bin/lmp` (29 Sep 2021) |
| **Built binary** | `~/git_SW/lammps/Build/lmp` (2 Apr 2025) |
| **Source** | `~/git_SW/lammps/` |
| **Python package** | Listed in pip (2021.9.29) but not importable in conda base |

### ASE

| Item | Value |
|------|-------|
| **Version** | 3.28.0 |
| **Environment** | `conda activate base` |
| **CLI** | `ase` in `~/.local/bin/` |
| **GUI** | `ase gui structure.xyz` |

### FireCore (Fireball DFT)

| Item | Value |
|------|-------|
| **Source** | `~/git/FireCore/` |
| **Status** | Source present; `Fdata` integral tables **not found** on this machine |

### ORCA

**Not installed.** `which orca` returns nothing; no `~/SW/orca_*` directory.

### qmeq

| Item | Value |
|------|-------|
| **Source** | `~/git/qmeq/` |
| **Status** | Source present; install status not verified |

---

## 5. Data and Parameter Sets

### DFTB+ Slater-Koster Parameters

**Location:** `/home/prokophapala/SIMULATIONS/dftbplus/slakos/library/`

- `3ob-3-1` — Bio/organic parameter set (also archived as `3ob-3-1.tar.xz`)
- **Missing on laptop vs desktop:** `mio-1-1` set

**Env var:** `DFTB_SK_PATH=/home/prokophapala/SIMULATIONS/dftbplus/slakos/library/`

### xTB / Semi-Empirical Parameters (CARBSIS)

**Location:** `/home/prokophapala/Desktop/CARBSIS/data/`

- `gfn0-xtb`, `gfn1-xtb`, `gfn2-xtb`, `gfn-ff`
- `pm6`, `pm6-d3`, `pm6-d3h4`, `pm6-dh2`, `pm6-dhp`, `pm6-ml`, `pm7`
- `DFT-b3lyp`, `DFT-wb97m`, `dftbp`

### LAMMPS Potentials

**Source tree:** `~/git_SW/lammps/potentials/` (if built from source)

### Psi4 Calculation Data

**Location:** `~/SIMULATIONS/psi4/` — example inputs and reference data

---

## 6. Environment Variables

### Current ~/.bashrc Configuration (QC-relevant only)

```bash
# CUDA
export PATH="/usr/local/cuda/bin/:$PATH"

# DFTB+ ASI build (in PATH — this is what `which dftb+` resolves to)
export LD_LIBRARY_PATH=$HOME/opt/dftb-asi/lib:$LD_LIBRARY_PATH
export LD_LIBRARY_PATH=$HOME/opt/asi/lib:$LD_LIBRARY_PATH
export ASI_LIB_PATH=$HOME/opt/asi/lib/libasidftbp.so
export PATH=$HOME/opt/dftb-asi/bin:$PATH

# DFTB+ main build (used by CompChemUtils via DFTB_EXE, but NOT in PATH)
export DFTB_EXE=/home/prokophapala/opt/dftbplus/bin/dftb+
export DFTB_LIB_PATH=/home/prokophapala/opt/dftbplus/lib/libdftbplus.so
export DFTB_SK_PATH=/home/prokophapala/SIMULATIONS/dftbplus/slakos/library/
export LD_LIBRARY_PATH=/home/prokophapala/opt/dftbplus/lib:$LD_LIBRARY_PATH

# DFTB+ source build libs (for development)
export LD_LIBRARY_PATH=/home/prokophapala/git_SW/dftbplus/_build/src/dftbp:...:$LD_LIBRARY_PATH

# IQmol (molecular viewer)
alias iqmol='BABEL_LIBDIR=/usr/lib/x86_64-linux-gnu/openbabel/3.1.1 BABEL_DATADIR=/usr/share/openbabel/3.1.1 iqmol'
```

### Recommended Additional Variables (not yet in ~/.bashrc)

```bash
# xtb — NOT INSTALLED; add after downloading to ~/SW/xtb-dist/
# export XTBHOME=/home/prokophapala/SW/xtb-dist
# export PATH=$XTBHOME/bin:$PATH

# Consistent DFTB+ binary — pick ONE build and align PATH with DFTB_EXE:
# Option A: use dftbplus build (recommended for CompChemUtils)
# export PATH=/home/prokophapala/opt/dftbplus/bin:$PATH
# Option B: keep dftb-asi for ASI workflows, update DFTB_EXE to match
```

---

## 7. Additional Software

### Visualization and Analysis

| Tool | Location | Status |
|------|----------|--------|
| **VESTA** | `~/SW/VESTA-gtk3/` | Installed |
| **Avogadro2** | `~/SW/Avogadro2-x86_64.AppImage` | Installed |
| **IQmol** | `/usr/local/bin/iqmol` | Installed (alias in bashrc) |
| **VMD** | `~/bin/vmd` | Present |
| **Blender** | `~/SW/blender-4.5.1-linux-x64/` | Installed |

### Development / GPU

| Tool | Location | Status |
|------|----------|--------|
| **PyOpenCL** | `~/SW/pyopencl-2025.2.6/` | Source |
| **CUDA toolkit** | `/usr/local/cuda/` | Installed (12.1) |

### Missing vs GTX3090 Desktop

- ORCA, MOPAC, CP2K, QUICK, ALAMODE, g-xtb
- JupyterLab + nglview + py3Dmol
- ASH, easyxtb
- Atomistica GUIs, OVITO
- Fireball Fdata integral tables

---

## 8. Quick Reference

| Software | Environment | Activation | Binary/Import | Status |
|----------|-------------|------------|---------------|--------|
| pySCF | conda base | `conda activate base` | `import pyscf` | Working (CPU only) |
| pySCF GPU | — | — | `import gpu4pyscf` | **Not installed** |
| DFTB+ | System | (env vars set) | `dftb+` | Working (dftb-asi in PATH; linker warning) |
| DFTB+ Python API | conda base | `conda activate base` | `import dftbplus` | Working (editable) |
| xTB standalone | — | — | `xtb` | **Not installed** |
| tblite CLI | System | — | `~/opt/dftbplus/bin/tblite` | Present (not in PATH) |
| tblite Python | — | — | `import tblite` | **Not installed** |
| Psi4 | conda psi4env | `conda activate psi4env` | `import psi4` | Working |
| GPAW | conda base | `conda activate base` | `import gpaw` | Working |
| ASE | conda base | `conda activate base` | `import ase` | Working |
| LAMMPS | System / built | — | `lmp` / `~/git_SW/lammps/Build/lmp` | Working |
| ORCA | — | — | — | **Not installed** |
| FireCore | Source | — | — | Source only, no Fdata |

---

## 9. Gaps vs Desktop & Recommended Fixes

### Critical for CompChemUtils workflows

| Gap | Impact | Fix |
|-----|--------|-----|
| No standalone `xtb` binary | `XTBBBackend` fails in auto mode | `pip install tblite` **or** download xtb to `~/SW/xtb-dist/` |
| No Python `tblite` | Same as above | `conda activate base && pip install tblite` |
| DFTB+ PATH vs `DFTB_EXE` mismatch | Subprocess uses dftb-asi, env var points to dftbplus | Align PATH: `export PATH=/home/prokophapala/opt/dftbplus/bin:$PATH` |
| dftb-asi linker warning | Symbol size mismatch on every `dftb+` run | Rebuild dftb-asi against current ASI lib, or use dftbplus build |
| No `mio-1-1` SK set | Some DFTB+ examples may fail | Copy from desktop or download from dftb.org |

### Nice to have

| Gap | Fix |
|-----|-----|
| No gpu4pyscf | `pip install gpu4pyscf-cuda12x` (GTX 1650 4 GB is tight for large systems) |
| No JupyterLab/nglview | `pip install jupyterlab nglview py3Dmol` |
| No ORCA | Download from ORCA forum or use PySCF/Psi4 instead |
| Psi4 1.7 vs desktop 1.9.1 | `conda update -n psi4env psi4` when needed |
| pySCF 2.11.0 vs desktop 2.13.0 | `pip install --upgrade pyscf` |

### Verify after fixes

```bash
conda activate base
python -c "import pyscf; print('pyscf', pyscf.__version__)"
python -c "import tblite.interface; print('tblite OK')"   # after install
which xtb && xtb --version                                 # after xtb install
dftb+ --version
python -c "from py.interfaces.xtb import XTBBBackend; b=XTBBBackend(); print(b._select_backend())"
python -c "from py.interfaces.dftbplus import DFTBPlusBackend; print('DFTB+ backend OK')"
```

---

## Example Scripts Location (CompChemUtils repo)

Same as GTX3090 desktop — see `examples/` in this repository:

- DFTB: `examples/dftb/`
- pySCF: `examples/tSiNCs/pyscf/`
- Psi4: `examples/tPsi4resp/`
- Phonons: `examples/phonons/`
- Fukui: `examples/fukui/`
