# Phonon Benchmark Toolkit

CLI scripts to download reference phonon data, set up ALAMODE+LAMMPS calculations,
and overlay/benchmark phonon dispersion curves for bulk Si and diamond.

## Files

### Modular Phonon Pipeline (NEW)

| File | Purpose |
|------|---------|
| `phonon_utils.py` | Core library: structure loading, QPath handling, PhononCalculator with caching |
| `phonon_backends.py` | Pluggable force calculators: DFTBBackend, LAMMPSBackend, MMFFBackend |
| `run_phonon.py` | Main CLI: compute phonon bands with any backend, supports q-path files and auto-generation |
| `plot_phonon_comparison.py` | Multi-method comparison plotter with strict q-path validation |
| `plot_bz_paths_3d.py` | 3D Brillouin zone path visualizer (matplotlib) |

### Legacy Workflows (still functional)

| File | Purpose |
|------|---------|
| `phonon_config.json` | Tool and potential path configuration (edit for your system) |
| `download_phonon_refs.py` | Download phonon data from MP, phonondb, Mendeley Data |
| `setup_alamode_phonon.py` | Generate ALAMODE + LAMMPS input files |
| `setup_dftb_phonon.py` | Generate DFTB+ + phonopy input files |
| `run_alamode_phonon.py` | ALAMODE + LAMMPS runner |
| `run_phonopy_phonon.py` | Original phonopy + DFTB/LAMMPS runner (reference) |
| `plot_phonon_benchmark.py` | Overlay and benchmark phonon dispersions |
| `plot_phonons.py` | Simple phonon band plotter |
| `plot_alamode_overlay.py` | ALAMODE-specific overlay plotter |
| `export_phonon_bands.py` | Export multi-method bands to single text file |
| `experimental_phonon_data.json` | Reference INS data points (Si & diamond) |

### Deprecated Files

| File | Status |
|------|--------|
| `run_phonon.py.bak` | Backup of original run_phonon.py (can delete) |
| `plot_phonon_comparison copy.py` | Duplicate (can delete) |
| `plot_comparison.py` | Superseded by plot_phonon_comparison.py |
| `plot_mp_diamond.py` | Superseded by plot_phonon_comparison.py |

## Quick Start

### Modular Phonon Pipeline (Recommended)

The new modular system (`phonon_utils.py`, `phonon_backends.py`, `run_phonon.py`) provides:
- **Backend-agnostic**: DFTB+, LAMMPS, or MMFF force calculators via pluggable backends
- **Caching**: Force constants cached by hash; only recomputed if structure/backend changes
- **Flexible q-paths**: Load from file (`--q-path-file`) or auto-generate (`--q-path-auto`)
- **Metadata**: Computed results save structure_file, method, program, basis_set for plotting

#### Compute phonon bands

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

# Molecular Vibrational Spectra (tSiNCs)

A consolidated caching and computation pipeline for molecular vibrational spectra using PySCF (analytical Hessian) and DFTB+ (finite-difference Hessian via ASE). Designed to avoid scattered JSON cache files and produce clean, reusable outputs.

## Files

| File | Purpose |
|------|---------|
| `../tSiNCs/vib_utils.py` | Core library: calculators, optimization, Hessian extraction, mode export |
| `../tSiNCs/run_vib_spectra.py` | Main runner: selects molecule & methods, orchestrates caching, exports modes, generates overlay plots |
| `../tSiNCs/plot_vib_spectra.py` | Standalone overlay plotter (auto-discovers cached `.npy` files) |

## Supported Methods

| Method | Calculator | Hessian source | Cost |
|--------|-----------|----------------|------|
| `pyscf_b3lyp` | PySCF B3LYP/cc-pVDZ | Analytical (exact) | High (O(N⁴) per gradient) |
| `dftb_mio` | DFTB+ `mio-1-1` SK | ASE finite-difference | Very low |
| `dftb_3ob` | DFTB+ `3ob-3-1` SK | ASE finite-difference | Very low |
| `dftb_matsci` | DFTB+ `matsci-0-3` SK | ASE finite-difference | Very low |
| `dftb_pbc` | DFTB+ `pbc-0-3` SK | ASE finite-difference | Very low |

### DFTB+ Slater-Koster sets

The DFTB+ calculator expects SK files under `/home/prokop/SIMULATIONS/dftbplus/slakos/`:
- `mio-1-1/` — organic molecules (C, H, N, O, S)
- `3ob-3-1/` — improved organic/organo-metallic parameters
- `matsci-0-3/` — materials science (Si, C, …)
- `pbc-0-3/` — periodic/bulk parameters

If your SK directory differs, edit `SK_PATHS` in `vib_utils.py`.

## How It Works

### 1. Consolidated caching (no scattered JSON)

ASE's `Vibrations` class normally writes hundreds of small `cache.*.json` files to disk. Our pipeline:
1. Redirects ASE displacement data to a **temporary directory** (`/tmp/asevib_*`)
2. Extracts the Hessian matrix (`vib.H`) and frequencies immediately after the run
3. Saves them as single binary `.npy` files
4. **Deletes the temp directory** — no scattered files remain

On cache reload, modes are reconstructed directly from the saved Hessian using mass-weighted diagonalization (`_modes_from_hessian_ase`), eliminating any dependency on ASE's JSON cache.

### 2. PySCF analytical Hessian

PySCF does not need finite differences. The pipeline:
1. Optimizes geometry via ASE BFGS (using a thin `PySCFCalc` wrapper that calls PySCF gradients)
2. Builds a fresh PySCF `mol`/`mf` at the optimized geometry
3. Computes `mf.Hessian().kernel()` — fully analytical
4. Extracts frequencies and normal modes via `pyscf.hessian.thermo.harmonic_analysis`

### 3. Output formats

For every `(molecule, method)` combination, the pipeline produces:

| File | Format | Contents |
|------|--------|----------|
| `<mol>_<method>_relaxed.xyz` | XYZ | Optimized geometry |
| `<mol>_<method>_hessian.npy` | NumPy binary | `(3N, 3N)` Hessian matrix |
| `<mol>_<method>_freq.npy` | NumPy binary | Complex frequency array `(3N,)` in cm⁻¹ |
| `<mol>_<method>_modes.txt` | ASCII | Human-readable mode table (freq + displacement vectors) |
| `<mol>_<method>_all_modes.xyz` | Multi-frame XYZ | All real modes as displaced geometries (view in Jmol/VMD) |
| `<mol>_vib_overlay.png` | PNG | Stick + Gaussian-broadened overlay spectra |

## Usage

### Compute vibrational spectra

```bash
cd ../tSiNCs

# Small molecules (fast — includes PySCF)
python run_vib_spectra.py CH4 --workdir results --plot
python run_vib_spectra.py SiH4 --workdir results --plot

# Larger molecules (DFTB+ only by default; add --methods for PySCF)
python run_vib_spectra.py adamantane --workdir results --plot
python run_vib_spectra.py Si10_H --workdir results --plot

# Force PySCF on larger molecules (long — ~30–60 min each)
python run_vib_spectra.py adamantane --methods pyscf_b3lyp --workdir results --plot
```

The `--workdir` flag controls where all cached `.npy`/`.xyz`/`.txt`/`.png` files are written.

### Plot cached results

`plot_vib_spectra.py` auto-discovers cached `.npy` files — no hardcoded method lists:

```bash
python plot_vib_spectra.py CH4 --workdir results --xmax 3500
python plot_vib_spectra.py adamantane --workdir results --xmax 3200
python plot_vib_spectra.py Si10_H --workdir results --xmax 2200 --noshow
```

### Load cached data programmatically

```python
import numpy as np

freqs = np.load('results/CH4_pyscf_b3lyp_cc-pVDZ_freq.npy')
hess  = np.load('results/CH4_pyscf_b3lyp_cc-pVDZ_hessian.npy')
# freqs is complex: imag part → imaginary modes (rotation/translation)
real_freqs = freqs[freqs.imag == 0].real
```

## Known Issues & Fixes

### DFTB+ `results.tag` parsing bug

ASE's DFTB calculator fails when parsing `results.tag` eigenvalue blocks with wrapped lines. Fixed by monkey-patching `calc.read_eigenvalues = lambda: None` in `make_dftb_calc` — eigenvalues are not needed for force/energy calculations.

### Missing `ase.calculators.pyscf`

ASE does not ship a PySCF calculator. We provide a minimal `PySCFCalc` class in `vib_utils.py` that wraps `pyscf.grad.rks.Gradients` (or `rhf.Gradients` for HF) and returns forces as `-gradient`.

### mol2 format

ASE cannot read `.mol2` natively. `run_vib_spectra.py` includes a `read_mol2()` helper that uses OpenBabel to convert to XYZ before loading.

## Results

### CH₄ (5 atoms)

| Method | Modes | Frequencies (cm⁻¹) |
|--------|-------|-------------------|
| **PySCF B3LYP/cc-pVDZ** | 9 | 1309 (×3), 1531 (×2), 3030, 3152 (×3) |
| **DFTB+ mio-1-1** | 9 | 1323 (×3), 1503 (×2), 2956, 3157 (×3) |
| **DFTB+ 3ob-3-1** | 9 | 1296 (×3), 1475 (×2), 2860, 3050 (×3) |

PySCF and mio-1-1 agree within ~5 % on stretch frequencies; 3ob-3-1 underestimates C–H stretches by ~3–4 %.

### SiH₄ (5 atoms)

| Method | Modes | Frequencies (cm⁻¹) |
|--------|-------|-------------------|
| **PySCF B3LYP/cc-pVDZ** | 9 | 908 (×3), 971 (×2), 2205, 2217 (×3) |
| **DFTB+ matsci-0-3** | 9 | 775 (×3), 881 (×2), 2205, 2210 (×3) |
| **DFTB+ pbc-0-3** | 9 | 740 (×3), 878 (×2), 2162, 2171 (×3) |

DFTB+ Si–H stretches are within ~1–2 % of PySCF, but bending modes are underestimated by ~15–20 %.

### Adamantane C₁₀H₁₆ (26 atoms)

| Method | Modes | Low (cm⁻¹) | Mid (cm⁻¹) | C–H stretch (cm⁻¹) |
|--------|-------|-----------|-----------|-------------------|
| **DFTB+ mio-1-1** | 72 | 314–1455 | 2889–2995 | 2900–3000 |
| **DFTB+ 3ob-3-1** | 72 | 308–1433 | 2919–3002 | 2920–3002 |

PySCF B3LYP/cc-pVDZ was attempted but killed after ~80 s/gradient — estimated total time ~30–60 min. Rerun with `python run_vib_spectra.py adamantane --methods pyscf_b3lyp` if needed.

### Si₁₀H₁₆ (26 atoms)

| Method | Modes | Low (cm⁻¹) | Si–H stretch (cm⁻¹) |
|--------|-------|-----------|-------------------|
| **DFTB+ matsci-0-3** | 72 | 86–1449 | 2051–2088 |
| **DFTB+ pbc-0-3** | 72 | 77–832 | 1995–2050 |

Both SK sets agree within ~2 % on Si–H stretches; pbc-0-3 produces slightly softer low-frequency modes.

## Performance Notes

| Molecule | N_atoms | PySCF B3LYP/cc-pVDZ (grad) | DFTB+ (full vib) |
|----------|---------|---------------------------|-----------------|
| CH₄ | 5 | ~3 s | ~10 s |
| SiH₄ | 5 | ~4 s | ~10 s |
| Adamantane | 26 | ~98 s | ~2 min |
| Si₁₀H₁₆ | 26 | not timed (killed) | ~2 min |

PySCF scales steeply with system size; for >15 atoms consider running overnight or using a cheaper basis (e.g., `sto-3g` for quick tests). DFTB+ remains fast enough for interactive use up to ~50 atoms.

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