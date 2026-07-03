# Machine-Specific Quantum Chemistry Setup

**Machine:** GTX3090 (Prokop's Desktop)  
**OS:** Ubuntu 24.04.2 LTS  
**CPU:** AMD Zen3 (8 physical cores, 16 threads)  
**GPU:** NVIDIA RTX 3090 (CUDA 12.2)  
**Last Updated:** June 14, 2026

This document contains machine-specific installation paths, environment variables, and configuration notes for quantum chemistry software on this system. For general usage tutorials, see `doc/CompChem_software_quick_cheatsheet.md`.

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
9. [Recent Installation Notes](#recent-installation-notes-june-14-2026)

---

## 1. System Specs

| Component | Specification |
|-----------|---------------|
| CPU | AMD Zen3, 8 cores / 16 threads |
| GPU | NVIDIA RTX 3090, 24 GB VRAM |
| CUDA | 12.2 |
| RAM | ~64 GB |
| OS | Ubuntu 24.04.2 LTS |
| Python (ML venv) | 3.12 |
| Python (p4env) | 3.12 |

---

## 2. Directory Structure

### Key Directories

```
/home/prokop/
├── Fireball/                          # Fireball DFT integral tables
│   ├── Fdata_HCNOS.tar               # HCNOS parameter set (384 MB)
│   └── Fdata_HCNOS_ext.tar          # Extended HCNOS (1.6 GB)
├── SIMULATIONS/                       # Central simulation data storage
│   ├── dftbplus/
│   │   ├── slakos/library/           # DFTB+ Slater-Koster parameters
│   │   │   ├── 3ob-3-1/              # Bio/organic set
│   │   │   └── mio-1-1/              # Simpler set
│   │   └── tests/                    # DFTB+ test data
│   ├── quick/                        # QUICK quantum chemistry calculations
│   ├── phononDB_repo/                # Phonon database mirror
│   ├── psi4/                         # Psi4 calculations
│   ├── cp2k/                         # CP2K calculations
│   └── ase/                          # ASE calculations
├── SW/                                # Software packages (binaries/AppImages)
│   ├── orca_6_1_1_linux_x86-64_shared_openmpi418/  # ORCA 6.1.1
│   ├── mopac-23.2.5-linux/           # MOPAC 23.2.5
│   ├── xtb-dist/                     # xtb (GFN-xTB)
│   ├── dftbplus/                     # DFTB+ binaries
│   ├── alamode/                      # ALAMODE phonon calculator
│   ├── g-xtb/                        # g-xtb (graphical xtb)
│   └── lammps-29Aug2024/             # LAMMPS source
└── git_SW/                           # Source code repositories
    ├── dftbplus/                     # DFTB+ source
    ├── cp2k/                         # CP2K source
    ├── lammps/                       # LAMMPS source
    ├── psi4/                         # Psi4 source
    ├── alamode/                      # ALAMODE source
    ├── QUICK/                        # QUICK quantum chemistry
    └── qmeq/                         # Quantum transport (qmeq)
```

---

## 3. Python Environments

### Conda Environments

```bash
# List available environments
conda env list

# Activate Psi4 environment
conda activate p4env

# Deactivate
conda deactivate
```

**Available environments:**
- `base` - Default miniconda3 environment
- `p4env` - Psi4 quantum chemistry environment

### Virtual Environments

```bash
# Activate ML environment (contains pySCF, GPAW, ASE, LAMMPS)
venvML
# or
activate_ml
```

**Available venvs:**
- `~/venvs/ML` - Machine learning and quantum chemistry environment

### ML venv Package List (`~/venvs/ML`, Python 3.12)

- `pyscf` 2.13.0
- `gpu4pyscf-cuda12x` 1.7.1 (GPU acceleration for RTX 3090)
- `pyscf-dispersion` 1.5.0
- `pyscf-semiempirical` 0.1.1
- `ase` 3.28.0
- `gpaw` 25.7.0
- `gpaw-data` 1.0.1
- `lammps` 2024.8.29 (Python package)
- `jupyterlab` 4.5.8
- `nglview` 4.0.1 (3D molecular viewer for Jupyter)
- `py3Dmol` 2.5.5 (3D molecular viewer for Jupyter)
- `ash` 0.95 (multiscale workflow wrapper)
- `easyxtb` 0.10.2 (Python xTB interface, used by avo_xtb plugin)
- `numpy`, `scipy`, `matplotlib`

### p4env Conda Package List (`p4env`, Python 3.12)

- `psi4` 1.9.1
- `resp` 1.0 (charge fitting)
- `dftd3` 3.2.1 (dispersion correction)

---

## 4. Software Installations

### pySCF

**Location:** `~/venvs/ML/lib/python3.12/site-packages/pyscf/`  
**Version:** 2.13.0  
**GPU Support:** gpu4pyscf-cuda12x 1.7.1 (for NVIDIA RTX 3090)

### DFTB+

**Binary:** `/home/prokop/git_SW/dftbplus/Build/app/dftb+/dftb+`  
**Source:** `/home/prokop/git_SW/dftbplus/`  
**Additional binaries in `/home/prokop/SW/dftbplus/bin/`:**
- `dftb+` - Main executable
- `waveplot` - Wavefunction plotting
- `modes` - Vibrational mode analysis
- `skderivs` - Slater-Koster derivative utilities

### CP2K

**Binary:** `/home/prokop/git_SW/cp2k/install/bin/cp2k.psmp`  
**Source:** `/home/prokop/git_SW/cp2k/`  
**Version:** 2026.1 (Development Version)  
**Build type:** psmp (MPI + OpenMP + Shared)  
**Note:** Built via Spack (NOT recommended for future - use conda instead)

### LAMMPS

**Binary:** `/home/prokop/bin/lmp_serial`  
**Source:** `/home/prokop/git_SW/lammps/`  
**Python package:** Installed in ML venv (version 2024.8.29)  
**Potentials:** `/home/prokop/git_SW/lammps/potentials/`

### GPAW

**Version:** 25.7.0 (in ML venv)  
**Data:** gpaw-data 1.0.1

### Psi4

**Version:** 1.9.1 (in p4env conda)  
**Source:** `/home/prokop/git_SW/psi4/`  
**Additional packages:** resp 1.0, dftd3 3.2.1

### ORCA

**System binary:** `/usr/bin/orca`  
**Additional installation:** `/home/prokop/SW/orca_6_1_1_linux_x86-64_shared_openmpi418/`  
**Version:** 6.1.1 (newer version in SW directory)  
**Features:** Extensive post-HF methods (CCSD, CCSD(T), CASSCF, etc.)

### xtb (GFN-xTB)

**Location:** `/home/prokop/SW/xtb-dist/bin/`  
**Binaries:**
- `xtb` - Main GFN-xTB executable
- `cpx` - CREST conformer search

### MOPAC

**Location:** `/home/prokop/SW/mopac-23.2.5-linux/`  
**Version:** 23.2.5  
**Type:** Semi-empirical quantum chemistry

### QUICK

**Source:** `/home/prokop/git_SW/QUICK/`  
**Type:** Quantum chemistry for large systems  
**Status:** Source code available, build directory exists

### g-xtb (Graphical xtb)

**Location:** `/home/prokop/SW/g-xtb/`  
**Type:** Graphical wrapper for xtb calculations

### qmeq

**Location:** `/home/prokop/git_SW/qmeq/` and `/home/prokop/git_SW/qmeq-examples/`  
**Type:** Quantum transport calculator (NEGF equations)

### sparrow

**Location:** `/home/prokop/git_SW/sparrow/` and `/home/prokop/git_SW/sparrow-old-2023/`  
**Type:** Fast semi-empirical quantum chemistry (part of SCINE toolkit)

### pyeff

**Location:** `/home/prokop/git_SW/pyeff/` and `/home/prokop/git_SW/pyeff-py2/`  
**Type:** Python effective fragment potential

### ALAMODE

**Source:** `/home/prokop/git_SW/alamode/` and `/home/prokop/SW/alamode/`  
**Type:** Anharmonic lattice dynamics and phonon calculations

### ASE

**Version:** 3.28.0 (in ML venv)

### JupyterLab + Molecular Visualization

**Location:** Installed in ML venv (`~/venvs/ML/`)  
**Packages:**
- `jupyterlab` 4.5.8 — Notebook server
- `nglview` 4.0.1 — 3D molecular viewer (renders ASE/pdb/xyz in notebooks)
- `py3Dmol` 2.5.5 — Alternative 3D viewer
- `ipywidgets` 8.1.8 — Interactive widgets

**Launch:** `venvML && jupyter lab --no-browser`

### ASH (Atomistic Simulation Hacky)

**Location:** Installed in ML venv (`~/venvs/ML/lib/python3.12/site-packages/ash/`)  
**Version:** 0.95 (git)  
**Purpose:** Python workflow wrapper for multiscale QM/MM, geometry optimization, and MD  
**Supports:** xTB, DFTB+, MOPAC, PySCF, ORCA, ASE

### Atomistica Desktop GUIs

**Location:** `/home/prokop/SW/atomistica/`  
**Binaries:**
- `xtb_GUI` — Standalone xTB GUI (GFN0/1/2, GFN-FF, MD, opt, freq)
- `atomistica_1_10_linux` — ORCA job launcher and monitor

**Status:** **BROKEN on Ubuntu 24.04** — The precompiled binaries bundle an older GTK/gdk-pixbuf that expects a separate `libpixbufloader-png.so`, which no longer exists in gdk-pixbuf 2.42+ (PNG support is now built-in). The GUI crashes with `gdk-pixbuf-error-quark` when loading icons. No safe system-level fix available without rebuilding the binaries from source.

### ASE-GUI

**Location:** Installed with ASE in ML venv  
**Usage:** `ase gui structure.xyz`  
**Purpose:** Lightweight viewer/editor for atomic structures and trajectories

### Quick Launch — Newly Installed Tools

| Tool | Version | Status | One-liner Command |
|------|---------|--------|-------------------|
| JupyterLab | 4.5.8 | Working | `venvML && jupyter lab --no-browser` |
| nglview | 4.0.1 | Working | `import nglview; nglview.show_ase(atoms)` (in notebook) |
| py3Dmol | 2.5.5 | Working | `import py3Dmol; view = py3Dmol.view()` (in notebook) |
| ASH | 0.95 | Working | `from ash import *` (in Python script) |
| easyxtb | 0.10.2 | Working | `import easyxtb` (Python xTB interface) |
| GPAW | 25.7.0 | Working | `venvML && gpaw info` (periodic DFT / PAW) |

---

## 5. Data and Parameter Sets

### Fireball DFT Integral Tables

**Location:** `/home/prokop/Fireball/`

- `Fdata_HCNOS.tar` (384 MB) - Standard HCNOS parameter set
- `Fdata_HCNOS_ext.tar` (1.6 GB) - Extended HCNOS parameter set

### DFTB+ Slater-Koster Parameters

**Location:** `/home/prokop/SIMULATIONS/dftbplus/slakos/library/`

- `3ob-3-1` - Bio/organic (Br-C-Ca-Cl-F-H-I-K-Mg-N-Na-O-P-S-Zn)
- `mio-1-1` - Simpler (H-C-N-O-S-P)

### LAMMPS Potentials

**Location:** `/home/prokop/git_SW/lammps/potentials/`

- `Si.sw` - Stillinger-Weber potential for Si
- `Si.tersoff` - Tersoff potential for Si
- `SiC.tersoff` - Tersoff potential for SiC
- MEAM library files

### Phonon Database

**Location:** `/home/prokop/SIMULATIONS/phononDB_repo/`

Mirror of WMD-group phonon database for reference phonon structures.

---

## 6. Environment Variables

### Current ~/.bashrc Configuration

```bash
# DFTB+
export DFTB_EXE=/home/prokop/git_SW/dftbplus/Build/app/dftb+/dftb+
export DFTB_SK_PATH=/home/prokop/SIMULATIONS/dftbplus/slakos/library/

# CP2K
export CP2K_HOME=/home/prokop/git_SW/cp2k
export PATH=$CP2K_HOME/install/bin:$PATH
export LD_LIBRARY_PATH=$CP2K_HOME/install/lib:$CP2K_HOME/spack/spack/opt/spack/view/lib64:$CP2K_HOME/spack/spack/opt/spack/view/lib:$CP2K_HOME/spack/spack/opt/spack/view/lib/python3.14/site-packages/torch/lib:$CP2K_HOME/spack/spack/opt/spack/view/lib/MiMiC:$LD_LIBRARY_PATH

# ML venv alias
alias activate_ml="source ~/venvs/ML/bin/activate"
alias venvML="source ~/venvs/ML/bin/activate"
```

### Recommended Additional Variables

These are available on the system but not currently in `~/.bashrc`:

```bash
# ORCA 6.1.1 (newer version in SW/)
export ORCA_6_1_1_HOME=/home/prokop/SW/orca_6_1_1_linux_x86-64_shared_openmpi418
export PATH=$ORCA_6_1_1_HOME:$PATH

# xtb
export XTBHOME=/home/prokop/SW/xtb-dist
export PATH=$XTBHOME/bin:$PATH

# MOPAC
export MOPAC_HOME=/home/prokop/SW/mopac-23.2.5-linux
export PATH=$MOPAC_HOME/bin:$PATH

# ALAMODE (if built)
# export ALAMODE_HOME=/home/prokop/SW/alamode
# export PATH=$ALAMODE_HOME/bin:$PATH

# Atomistica Desktop GUIs (BROKEN on Ubuntu 24.04 — see Notes below)
# export ATOMISTICA_HOME=/home/prokop/SW/atomistica
# alias xtb_gui="GDK_PIXBUF_MODULE_FILE=/usr/lib/x86_64-linux-gnu/gdk-pixbuf-2.0/2.10.0/loaders.cache $ATOMISTICA_HOME/xtb_GUI"
# alias orca_gui="GDK_PIXBUF_MODULE_FILE=/usr/lib/x86_64-linux-gnu/gdk-pixbuf-2.0/2.10.0/loaders.cache $ATOMISTICA_HOME/atomistica_1_10_linux"
```

### Notes on GTK Fix

The Atomistica binaries are precompiled with an older GTK stack. On Ubuntu 24.04 they crash with `gdk-pixbuf` loader errors. The root cause is that gdk-pixbuf 2.42+ has built-in PNG support and no longer provides `libpixbufloader-png.so` as a separate file, but the bundled GTK expects it. No safe workaround exists without rebuilding the binaries from source.

---

## 7. Additional Software

### Visualization and Analysis

- **VESTA** - `/home/prokop/SW/VESTA-x86_64/` - 3D visualization
- **OVITO** - `/home/prokop/SW/ovito-basic-3.11.3-x86_64/` - Atomistic analysis
- **VMD** - Listed at `~/SW/vmd-1.9.3/` but **directory missing** — needs reinstallation
- **Avogadro2** - `/home/prokop/SW/Avogadro2-x86_64.AppImage` - Molecular editor (install `avo_xtb` plugin inside for xTB integration)
- **Molsketch** - `/home/prokop/SW/Molsketch-0.8.1-src/` - 2D structure drawing

### Molecular Modeling

- **Marvin** - `/home/prokop/SW/marvin_linux_24.1.2.deb` - Chemical drawing and analysis
- **ChemDoodle** - `/home/prokop/SW/ChemDoodleWeb-11.0.0/` - Web-based chemical sketching

### General Tools

- **Blender** - `/home/prokop/SW/blender-4.5.1-linux-x64/` - 3D rendering and animation
- **FreeCAD** - `/home/prokop/SW/FreeCAD_0.20-1-conda-Linux-x86_64-py310.AppImage` - CAD
- **Inkscape** - `/home/prokop/SW/Inkscape-091e20e-x86_64.AppImage` - Vector graphics

### Other Scientific Software

- **feram** - `/home/prokop/SW/feram-0.26.05/` - Ferroelectric molecular dynamics
- **abalone** - `/home/prokop/SW/abalone/` - Biomolecular dynamics
- **standard_pso** - `/home/prokop/SW/standard_pso_2011_c/` - Particle swarm optimization
- **OpenBabel** - `/home/prokop/git_SW/openbabel/` - Chemical format conversion

---

## 8. Quick Reference

| Software | Environment | Activation Command | Binary/Import |
|----------|-------------|-------------------|---------------|
| pySCF | venv ML | `venvML` | `import pyscf` |
| DFTB+ | System | (env vars set) | `dftb+` |
| CP2K | System | (env vars set) | `cp2k.psmp` |
| LAMMPS | venv ML / System | `venvML` | `lmp_serial` / `import lammps` |
| GPAW | venv ML | `venvML` | `import gpaw` |
| Psi4 | conda p4env | `conda activate p4env` | `import psi4` |
| ORCA | System | - | `orca` or ORCA 6.1.1 |
| xtb | System | (add to PATH) | `xtb` |
| MOPAC | System | (add to PATH) | `mopac` |
| ASE | venv ML | `venvML` | `import ase` |
| QUICK | Source | (build required) | - |
| ALAMODE | Source | (build required) | - |
| g-xtb | System | (add to PATH) | `g-xtb` |
| qmeq | Source | (installable) | `import qmeq` |
| JupyterLab | venv ML | `venvML && jupyter lab` | `jupyter lab` |
| nglview/py3Dmol | venv ML | (in Jupyter) | `import nglview` |
| ASH | venv ML | `venvML` | `import ash` |
| ASE-GUI | venv ML | `venvML` | `ase gui <file>` |
| Atomistica xTB GUI | System | **BROKEN** (gdk-pixbuf) | `xtb_GUI` |
| Atomistica ORCA Launcher | System | **BROKEN** (gdk-pixbuf) | `atomistica_1_10_linux` |

---

## Example Scripts Location

### Phonon Calculations
- `examples/phonons/setup_dftb_phonon.py`
- `examples/phonons/phonon_backends.py`
- `examples/phonons/run_phonon.py`

### DFTB Examples
- `examples/dftb/compare_density_multizeta.py`
- `examples/dftb/compare_waveplot_lib.py`

### pySCF Examples
- `examples/tSiNCs/pyscf/test_adamantane.py`
- `examples/tSiNCs/pyscf/test_gpu.py`

### Psi4 Examples
- `examples/tPsi4resp/psi4resp.py`
- `examples/tPsi4resp/psi4scan.py`
- `examples/tPsi4resp/scan_2d.py`

### QUICK Examples
- `examples/tSiNCs/` - Si nanocrystal calculations

---

## Notes for Reproduction on Other Machines

1. **CP2K:** Do NOT use Spack build - use conda instead (saves hours and GB of space)
2. **DFTB+:** Build from source or use conda
3. **ORCA:** Use system package or download from ORCA forum
4. **xtb:** Download from xtb website or use conda
5. **Data directories:** Create similar structure for parameter sets
6. **Environment variables:** Adapt paths to new machine

## Recent Installation Notes (June 14, 2026)

### Newly Installed (Working)
- **JupyterLab 4.5.8**, **nglview 4.0.1**, **py3Dmol 2.5.5** — Interactive 3D molecular visualization in notebooks
- **ASH 0.95** — Multiscale QM/MM workflow wrapper (git install)
- **easyxtb 0.10.2** — Python xTB interface

### Newly Installed (Broken)
- **Atomistica Desktop GUIs** — `xtb_GUI` and `atomistica_1_10_linux` downloaded to `~/SW/atomistica/`, but **crash on launch** due to gdk-pixbuf version incompatibility (precompiled binary expects old separate PNG loader `.so`, Ubuntu 24.04 has PNG support built into gdk-pixbuf 2.42+). No workaround available.

### Known Issues
- **Gabedit:** Not installed yet — SourceForge download blocked; manual download needed from https://gabedit.sourceforge.net/
- **Avogadro2 `avo_xtb` plugin:** Requires manual install from inside Avogadro2 (Extensions → Plugin Downloader)
- **VMD:** Listed in directory tree but directory is missing on disk
- **QUICK / ALAMODE:** Source present but never compiled/built
