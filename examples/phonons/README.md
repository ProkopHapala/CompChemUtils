# phonons

Bulk phonon dispersion toolkit — modular `run_phonon.py` pipeline (DFTB+, LAMMPS, MMFF) plus legacy ALAMODE/phonopy workflows. Config via `phonon_config.json` (copy from template).

**Molecular vibrations** (gas-phase Hessians) are in [`../tSiNCs/README.md`](../tSiNCs/README.md), not this folder.

Parent index: [`../README.md`](../README.md).

---

## File index

### Modular pipeline (preferred)

- **phonon_utils.py** — `PhononCalculator`, q-path handling, force-constant caching by structure hash
- **phonon_backends.py** — `DFTBBackend`, `LAMMPSBackend`, `MMFFBackend` force calculators
- **run_phonon.py** — CLI: compute bands (`--method`, `--supercell`, `--q-path-file` / `--q-path-auto`)
- **plot_phonon_comparison.py** — overlay multiple `.npz` band results with q-path validation
- **plot_bz_paths_3d.py** — 3D Brillouin-zone path visualization
- **export_phonon_html.py** — interactive HTML band comparison viewer
- **export_phonon_bands_json.py** — JSON export for web viewer
- **fit_mmff_phonon.py** / **grid_fit_mmff_phonon.py** — scale MMFF stiffness to match reference phonons
- **relax_dftb.py** — equilibrate lattice constant before phonon supercell build
- **test_diamond_phonon_bands.py** — standalone diamond bands via pyBall MMFF Bloch sum

### Legacy ALAMODE / phonopy

- **download_phonon_refs.py** — fetch reference bands (Materials Project, phonondb, Mendeley)
- **setup_alamode_phonon.py** / **run_alamode_phonon.py** — ALAMODE + LAMMPS displacement workflow
- **setup_dftb_phonon.py** / **run_phonopy_phonon.py** — DFTB+ + phonopy band workflow
- **plot_phonon_benchmark.py** / **plot_phonons.py** / **plot_alamode_overlay.py** — legacy overlays
- **export_phonon_bands.py** — multi-method bands → single text file

### Config & reference data

- **phonon_config.json** / **phonon_config_pbc.json** / **phonon_config.template.json** — tool and potential paths
- **phonons_ref.md** / **phonons_fitting.md** / **MMFF_phonon_PBC_report.md** / **GIT_NOTES.md** — notes
- **diamond_fcc_path.dat** / **Si_qpath_ref.dat** / **plots/** — q-path and plot artifacts

---

## Quick Start (modular pipeline)

```bash
# Primitive cell with Tersoff potential, auto-generated FCC path
python run_phonon.py \
    --structure ../../data/crystals/diamond_primitive.cif \
    --method tersoff \
    --supercell 3 3 3 \
    --q-path-auto fcc_mp \
    --outdir test_primitive

# Primitive cell with DFTB+, custom q-path file
python run_phonon.py \
    --structure ../../data/crystals/Si_primitive.cif \
    --method dftb \
    --supercell 3 3 3 \
    --q-path-file Si_qpath_ref.dat \
    --slakos-dir /home/prokop/SIMULATIONS/dftbplus/slakos/pbc-0-3 \
    --outdir test_primitive

# Force recompute (skip cache)
python run_phonon.py --structure ... --method ... --force-recompute
```

#### Available q-path presets

| Preset | High-symmetry points | Description |
|--------|---------------------|-------------|
| `fcc_mp` | Γ → X → K → Γ → L → X → W → K | Materials Project standard for FCC |
| `diamond_standard` | Γ → X → W → K → Γ → L → U → W | Standard diamond dispersion path |

#### Compare multiple methods

```bash
python plot_phonon_comparison.py \
    --calc test_primitive/diamond_primitive_tersoff_3x3x3/phonon_bands.npz \
    --calc test_primitive/diamond_primitive_dftb_3x3x3/phonon_bands.npz \
    --ref mp_diamond_phonon_bands.dat \
    --ref-label "DFT reference (MP)" \
    --output plots/diamond_comparison.png
```

**Key features:**
- Strict q-path validation: skips calculations with mismatched q-points
- Auto-labels: `program/method/basis` (e.g., `lammps/tersoff`, `dftb+/pbc-0-3`)
- Single structure title: derived from input filename
- Multi-method reference support: extracts specific method columns from multi-column .dat files

#### Visualize k-point paths in 3D

```bash
python plot_bz_paths_3d.py \
    --cell ../../data/crystals/diamond_primitive.cif \
    --path diamond_fcc_path.dat --name "FCC standard" \
    --path mp_diamond_phonon_bands.dat --name "MP reference" \
    --output plots/bz_paths_diamond.png
```

#### Output files

| File | Contents |
|------|----------|
| `{structure}_{method}_{NxNxN}/force_constants.npz` | Cached force constants (hash-based) |
| `{structure}_{method}_{NxNxN}/phonon_state.json` | Cache state (structure/backend hash) |
| `{structure}_{method}_{NxNxN}/phonon_bands.npz` | qpts, distances, frequencies, labels, metadata |
| `{structure}_{method}_{NxNxN}/band.yaml` | Phonopy-compatible band structure |
| `{structure}_{method}_{NxNxN}/band.dat` | Text format (qpts, dists, freqs) |
| `{structure}_{method}_{NxNxN}/band.png` | Quick single-method plot |

### Legacy Workflows (ALAMODE + Phonopy)

#### 0. Configure tool paths (legacy workflows only)

Copy or edit `phonon_config.json` to point to your installed tools:

```json
{
  "tools": {
    "lammps_bin": "/path/to/lammps/src/lmp_serial",
    "dftb_bin": "/path/to/dftb+/dftb+",
    "slakos_dir": "/path/to/slakos",
    "phonopy_bin": "phonopy",
    "alamode_displace": "displace.py",
    "alamode_extract": "extract.py",
    "alamode_alm": "alm",
    "alamode_anphon": "anphon"
  },
  "potentials": {
    "si_sw": "/path/to/Si.sw",
    "si_tersoff": "/path/to/SiCGe.tersoff",
    "c_tersoff": "/path/to/SiC.tersoff"
  }
}
```

Alternatively, set environment variables (scripts will use config file if present):
- `LAMMPS_BIN`
- `DFTB_BIN`
- `SLAKOS_DIR`
- `PHONOPY_BIN`

### 1. Install dependencies

```bash
pip install mp-api pyyaml numpy matplotlib
```

### 2. Download reference data

**Materials Project** (computed DFT phonons — free API key required):
```bash
# Get API key from https://materialsproject.org/api
python download_phonon_refs.py mp --api-key YOUR_KEY --material-id mp-149 --outfile si_mp.json
python download_phonon_refs.py mp --api-key YOUR_KEY --material-id mp-66  --outfile diamond_mp.json
```

**phonondb** (Atsushi Togo's phonon database):
```bash
python download_phonon_refs.py phonondb --material-id mp-149 --outdir ./phonondb_si
python download_phonon_refs.py phonondb --material-id mp-66  --outdir ./phonondb_diamond
```

**Mendeley Data** (MTP machine-learning potential for Si/diamond):
```bash
python download_phonon_refs.py mendeley --doi 10.17632/6tjhd74t5r --outdir ./mtp_data
```

### 3. Set up calculations

**DFTB+ + phonopy** (recommended if DFTB+ is available):
```bash
python setup_dftb_phonon.py --material Si --supercell 2 2 2 --outdir dftb_si_2x2x2
python setup_dftb_phonon.py --material diamond --supercell 2 2 2 --outdir dftb_diamond_2x2x2
```

**ALAMODE + LAMMPS** (requires ALAMODE installation):
```bash
# Note: Your LAMMPS binary must have MANYBODY package for SW/Tersoff, or MEAM package for MEAM
python setup_alamode_phonon.py --material Si --potential sw --supercell 2 2 2
python setup_alamode_phonon.py --material Si --potential tersoff --supercell 2 2 2
python setup_alamode_phonon.py --material diamond --potential tersoff --supercell 2 2 2
python setup_alamode_phonon.py --material Si --potential mtp --mtp-file ./mtp_data/Si_diamond.mtp --supercell 2 2 2
```

This generates:
- `<prefix>.lammps` — LAMMPS structure file
- `<prefix>_force.in` — LAMMPS input template
- `<prefix>.alamode.in` — ALAMODE `alm` input
- `<prefix>.anphon.in` — ALAMODE `anphon` input
- `run_displace.sh`, `run_lammps_forces.sh`, `run_extract.sh`, `run_alamode.sh` — workflow scripts

For DFTB+ + phonopy, this generates:
- `dftb_in.hsd` — DFTB+ input file
- `band.conf` — phonopy band structure configuration
- `run_phonopy.sh` — Master script for the phonopy + DFTB+ workflow

### 4. Run calculations

**DFTB+ + phonopy:**
```bash
cd dftb_si_2x2x2
bash run_phonopy.sh
```

**ALAMODE + LAMMPS:**
```bash
cd Si_sw_2x2x2
bash run_alamode.sh
```

Follow the generated `run_alamode.sh` script. The typical steps are:

```bash
# 1. Generate displaced structures
bash run_displace.sh

# 2. Run LAMMPS on displaced structures, then extract forces
bash run_lammps_forces.sh
bash run_extract.sh

# 3. Compute force constants
alm Si_sw_2x2x2.alamode.in

# 4. Compute phonon dispersion
anphon Si_sw_2x2x2.anphon.in
```

The `anphon` output is typically `Si_sw_2x2x2.band.dat`.

### 5. Plot benchmark

```bash
python plot_phonon_benchmark.py \
    --material Si \
    --dftb dftb_band.yaml \
    --alamode Si_sw_2x2x2.band.dat \
    --mp si_mp.json \
    --phonondb ./phonondb_si/mp-149/band.yaml \
    --experimental experimental_phonon_data.json \
    --output si_benchmark.png
```

This overlays all curves and prints RMS errors against the experimental points.

## Recommended Methods & Potentials

| Code | Method | Best cheap option | Notes |
|------|--------|-------------------|-------|
| **DFTB+** | `matsci-0-3` or `pbc-0-3` SK tables | Free, tested for solids | Use with phonopy |
| **LAMMPS** | Lenosky MEAM (Si) | Best classical Si phonons | From NIST repo |
| **LAMMPS** | Tersoff (Si, C) | Fast but overestimates | Built into LAMMPS |
| **LAMMPS** | MTP (Si/diamond) | ML accuracy, open data | Download from Mendeley DOI 10.17632/6tjhd74t5r |

## Experimental Data Sources

The `experimental_phonon_data.json` contains approximate inelastic neutron scattering
(INS) reference points:
- **Si**: Dolling (1963) + Nilsson & Nelin (1972)
- **Diamond**: Warren et al. (1967) + Kulda et al.

These are approximate values for benchmarking. For publication-quality work, consult
the original papers and neutron scattering databases (e.g., IAEA EXFOR for some
cross-section data, though phonon dispersions are primarily in the literature).

## Notes

- **Materials Project**: The `mp-api` client is the official Python interface. An API key
  is free with registration.
- **phonondb**: The original Kyoto University website is closed. This script uses the
  WMD-group GitHub mirror, which scrapes the 2018-04-17 snapshot.
- **Mendeley Data**: Public datasets can be accessed via the REST API without authentication
  for metadata; file downloads may require a token if the dataset is restricted.
- **ALAMODE**: Must be installed separately. See https://alamode.readthedocs.io/
- **phonopy**: Must be installed for DFTB+ phonon calculations and for reading phonondb data.
- **LAMMPS packages**: Ensure your LAMMPS binary has the required packages:
  - MANYBODY package for Stillinger-Weber and Tersoff potentials
  - MEAM package for MEAM potentials
  - Rebuild LAMMPS with appropriate packages if needed

---

## Molecular vibrations

See [`../tSiNCs/README.md`](../tSiNCs/README.md) for gas-phase Hessians (PySCF, DFTB+, MMFF) via `vib_spectra.py`.

---

## Deprecation

## Files for Git

### NEW files (add to git)

```
phonon_utils.py
phonon_backends.py
plot_phonon_comparison.py
plot_bz_paths_3d.py
diamond_fcc_path.dat
```

### MODIFIED files (commit changes)

```
run_phonon.py
README.md
```

### DEPRECATED files (safe to delete)

```
run_phonon.py.bak
plot_phonon_comparison copy.py
plot_comparison.py
plot_mp_diamond.py
```

### LEGACY files (keep — still functional)

```
download_phonon_refs.py
setup_alamode_phonon.py
setup_dftb_phonon.py
run_alamode_phonon.py
run_phonopy_phonon.py
plot_phonon_benchmark.py
plot_phonons.py
plot_alamode_overlay.py
export_phonon_bands.py
experimental_phonon_data.json
phonon_config.json
phonon_config.template.json
phonon_config_pbc.json
```

### Data files (keep)

```
mp_diamond_phonon_bands.dat
Si_phonon_bands.dat
Si_qpath_ref.dat
diamond_phonon_bands.dat
```

### Test directories (keep)

```
test_primitive/  # Results from modular pipeline tests
phonon_results/  # Legacy ALAMODE results
phonon_results_pbc/  # Legacy DFTB results
alamode_results/  # Legacy ALAMODE results
benchmarks/  # Benchmark data
plots/  # Generated plots
```

---

## Summary of Implementation

The modular phonon pipeline ([phonon_utils.py](cci:7://file:///home/prokop/git/CompChemUtils/examples/phonons/phonon_utils.py:0:0-0:0), [phonon_backends.py](cci:7://file:///home/prokop/git/CompChemUtils/examples/phonons/phonon_backends.py:0:0-0:0), [run_phonon.py](cci:7://file:///home/prokop/git/CompChemUtils/examples/phonons/run_phonon.py:0:0-0:0)) provides:

1. **Backend-agnostic force calculation**: DFTB+, LAMMPS, MMFF via pluggable backends
2. **Hash-based caching**: Force constants cached; only recomputed if structure/backend changes
3. **Flexible q-paths**: Load from file or auto-generate from presets (`fcc_mp`, `diamond_standard`)
4. **Metadata preservation**: `structure_file`, `method`, `program`, `basis_set` saved for plotting
5. **3D BZ visualization**: [plot_bz_paths_3d.py](cci:7://file:///home/prokop/git/CompChemUtils/examples/phonons/plot_bz_paths_3d.py:0:0-0:0) for comparing k-point paths
6. **Rigorous comparison**: [plot_phonon_comparison.py](cci:7://file:///home/prokop/git/CompChemUtils/examples/phonons/plot_phonon_comparison.py:0:0-0:0) validates q-path matching and extracts specific method columns from multi-method reference files

The README has been updated with full usage documentation.