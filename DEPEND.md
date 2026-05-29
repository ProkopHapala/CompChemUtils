# Dependencies, Environment, and Data Setup

This document describes the external dependencies, environment variables, and data paths required to run the examples and tests in this repository. **No large third-party datasets or binaries are stored in this repo.** All external data and compiled tools must be provided by the user and referenced via configuration files or environment variables.

---

## 1. Python Packages

Install with pip:

```bash
pip install mp-api pyyaml numpy matplotlib
```

| Package | Used by | Note |
|---------|---------|------|
| `mp-api` | `download_phonon_refs.py` | Materials Project API client (free API key required) |
| `pyyaml` | `plot_phonon_benchmark.py` | Read phonopy YAML band structures |
| `numpy` | All plotting scripts | Array math |
| `matplotlib` | `plot_phonon_benchmark.py` | Plotting |

Optional:
- `phonopy` — Required for DFTB+ phonon workflow (`setup_dftb_phonon.py`) and for processing phonondb data.

---

## 2. External Tools

These must be installed separately and their paths configured (see Section 3).

| Tool | Required by | Installation |
|------|-------------|--------------|
| **LAMMPS** | `setup_alamode_phonon.py` | Build from source or package manager. Must include MANYBODY package for SW/Tersoff, or MEAM package for MEAM potentials. |
| **DFTB+** | `setup_dftb_phonon.py` | Build from source or conda. Must have `dftb+` executable in PATH or configured. |
| **phonopy** | `setup_dftb_phonon.py` | `pip install phonopy` or conda. |
| **ALAMODE** | `setup_alamode_phonon.py` | Build from source. See https://alamode.readthedocs.io/ |

---

## 3. Configuration: User-Independent Paths

**Do not hard-code personal paths in scripts.** The repo provides a per-example JSON config pattern that each user copies and edits locally.

### Per-Example Config File

Each example subdirectory that needs external tools contains a template config file (e.g. `phonon_config.json`). Copy it and edit the paths for your machine:

```bash
cp phonon_config.json phonon_config.local.json
# edit phonon_config.local.json
```

Scripts accept the config file via `--config`:

```bash
python setup_alamode_phonon.py --config phonon_config.local.json ...
```

### Environment Variables (fallback)

If a config file is missing or a key is absent, scripts fall back to these environment variables:

| Variable | Purpose |
|----------|---------|
| `LAMMPS_BIN` | Path to `lmp_serial` or `lmp` |
| `DFTB_BIN` | Path to `dftb+` executable |
| `SLAKOS_DIR` | Directory containing DFTB+ SK table files |
| `PHONOPY_BIN` | phonopy command (default: `phonopy`) |
| `PHONONDB_DIR` | Path to extracted phonondb repository (see Section 4) |

Scripts should **fail loudly** if a required tool or data directory is not found.

---

## 4. External Data

Large third-party datasets must **not** be committed to this repository. Keep them in a separate directory on your system and point to them via config or environment variables.

### phonondb (WMD-group mirror)

Clone once outside this repo:

```bash
git clone https://github.com/WMD-group/phononDB.git /home/user/SIMULATIONS/phononDB_repo
```

Then set `PHONONDB_DIR` or point `phonon_config.json` → `phonondb_dir` to that path.

### SLAKOS (DFTB+ parameter files)

Download or build your SK table collection and set `SLAKOS_DIR`.

### LAMMPS Potentials

Standard potentials ship with the LAMMPS source in `potentials/`. The config file points to the exact files needed.

---

## 5. Quick Checklist for New Users

1. Install Python packages (`pip install -r requirements.txt` if available).
2. Install/build external tools (LAMMPS, DFTB+, ALAMODE, phonopy).
3. Download external datasets (phonondb, SLAKOS) to a directory **outside** this repo.
4. Copy example config templates and fill in your local paths.
5. Run a minimal test (e.g., LAMMPS single-point energy) to verify paths.
