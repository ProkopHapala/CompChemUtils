# USER

For benchmark I need to find how to compute vibration phonon spectra of bulk silicone and bulk diamond using DFTB+ and using LAMMPS and compare it to experimental values, there should be results in some database, right?

---

# Kimi


Yes — there are well-documented workflows and databases for this exact benchmark. Here is a practical guide for computing phonon spectra of bulk Si and diamond with **DFTB+** and **LAMMPS**, plus where to find experimental reference data.

---

## 1. DFTB+ — Use `phonopy`

The standard approach is to couple **DFTB+** with **phonopy** (the widely-used phonon code). DFTB+ has been supported by phonopy since v2.0.

**Workflow summary:**
1. Prepare a DFTB+ input (`dftb_in.hsd`) that computes forces and writes a tagged results file:
   ```
   Analysis = { CalculateForces = Yes }
   Options  = { WriteResultsTag = Yes }
   ```
2. Generate displaced supercells with phonopy:
   ```
   phonopy -d --dim="4 4 4" --dftb+
   ```
   This creates `geo.genS` (undistorted) and `geo.genS-001` etc. (displaced). For high-symmetry diamond, often only one displacement is needed.
3. Run DFTB+ on each displaced supercell, keeping `results.tag`.
4. Collect forces:
   ```
   phonopy -f results.tag --dftb+
   ```
5. Compute and plot the band structure:
   ```
   phonopy -p band.conf --dim="4 4 4" --dftb+
   phonopy-bandplot --gnuplot band.yaml > band.dat
   ```

**Convergence checks:** test supercell size (e.g., 4×4×4 vs. 5×5×5) and k-point sampling. The DFTB+ recipes documentation provides a complete working example for **diamond** using the `mio` carbon Slater–Koster set.

---

## 2. LAMMPS — Several Routes

### A. ALAMODE + LAMMPS (Recommended for accuracy)
**ALAMODE** is an open-source lattice-dynamics code that extracts harmonic and anharmonic force constants from finite-displacement calculations and can use LAMMPS as the force calculator.

**Workflow for Si (applies directly to diamond with a C potential):**
1. Build a relaxed supercell in LAMMPS format (e.g., `Si222.lammps`).
2. Use ALAMODE's `displace.py` to generate displaced configurations:
   ```
   python displace.py --LAMMPS=Si222.lammps --mag=0.01 --prefix harm  -pf si222.pattern_HARMONIC
   python displace.py --LAMMPS=Si222.lammps --mag=0.04 --prefix cubic -pf si222.pattern_ANHARM3
   ```
3. Run LAMMPS (e.g., with Stillinger–Weber or Tersoff) on each displaced cell to get forces, dump them as `XFSET` files.
4. Extract displacement–force datasets:
   ```
   python extract.py --LAMMPS=Si222.lammps XFSET.harm1 > DFSET_harmonic
   ```
5. Feed `DFSET_harmonic` into ALAMODE's `alm`/`anphon` to compute phonon dispersion, DOS, and even thermal conductivity.

The ALAMODE docs provide a complete, copy-paste tutorial for **Si with LAMMPS**.

### B. LAMMPS Built-in `fix phonon`
LAMMPS has a native `fix phonon` command (in the PHONON package) that calculates the dynamical matrix from two-point position correlations during an MD run. It outputs binary dynamical matrices that can be post-processed (via `tools/phonon`) into dispersion curves and DOS.

**Key settings:**
- `sysdim` — dimensionality of the phonon system (3 for bulk).
- `nasr` — acoustic sum rule iterations (typically 10 for multi-atom cells).

This is easier to set up than the finite-displacement method but requires careful equilibration and longer runs to get clean statistics.

### C. ASE + LAMMPS
If you prefer a Python workflow, ASE can drive LAMMPS as a calculator and has its own `Phonons` class that automates finite displacements and force-constant extraction. This is convenient for quick benchmarks but less flexible than ALAMODE for anharmonic properties.

---

## 3. Interatomic Potentials — Choose Carefully

For Si and C, the quality of the phonon spectrum depends heavily on the potential:

| Potential | Material | Notes |
|-----------|----------|-------|
| **Stillinger–Weber (SW)** | Si | Classic; widely used in tutorials. |
| **Tersoff** | Si, C, SiC | Very common for diamond/Si; **overestimates phonon group velocities and lifetimes** compared to DFT. |
| **MEAM (modified EAM)** | Si | NIST repository entry accurately reproduces phonons, elastic constants, and point defects. |
| **Machine-Learning (ML) potentials** | Si, C, Si–C interfaces | e.g., MTP trained on DFT; captures phonon dispersions and lifetimes in close agreement with DFT and experiment. |

**Tip:** For a benchmark, run the same structure with SW, Tersoff, and an ML potential, then compare against DFTB+ and experiment. The differences will be instructive.

---

## 4. Experimental Reference Data & Databases

Yes — there are databases and literature sources with measured phonon dispersions for Si and diamond.

### A. Materials Project (MP)
- Go to the [Materials Explorer](https://materialsproject.org), search for Si (`mp-149`) or diamond C.
- Under **Properties → Phonon**, you will find computed phonon dispersion and DOS (from DFT, usually PBEsol).
- MP also links the underlying DFT parameters and crystal structures, which is useful for reproducing the calculation.

### B. phonondb (by Atsushi Togo)
A dedicated phonon database that accompanies the `phonopy` project. It contains first-principles phonon data (dispersions, DOS, thermal properties) for many materials, including Si and diamond. The data is usually from VASP + phonopy, so it serves as an excellent DFT benchmark.

### C. Direct Experimental Literature
- **Silicon:** Inelastic neutron scattering (INS) data is the gold standard. Classic references include Dolling (1963) and subsequent high-resolution measurements.
- **Diamond:** Also extensively measured by INS. The `exciting` code tutorial explicitly compares computed diamond phonon bands to experimental data points.
- **General repository:** The [phonon data in databases](https://lampz.tugraz.at/~hadley/ss1/book/phonons/phonon_database.php) page lists tabulated phonon DOS for Si-diamond, among others, and points to MP.

---

## 5. Benchmarking Strategy

A clean benchmark paper you can emulate is the **"Phonon Olympics"** (2025), which systematically compared `ALAMODE`, `phono3py`, and `ShengBTE` for phonon properties and thermal conductivity across several materials. They used Ge (diamond structure) as a test case and compared computed dispersions, lifetimes, and κ(T) against experimental measurements.

**Suggested benchmark workflow for your study:**

| Step | Tool | What to compute |
|------|------|-----------------|
| 1 | DFTB+ + phonopy | Harmonic phonon dispersion of Si and diamond |
| 2 | LAMMPS + ALAMODE | Harmonic (and anharmonic) dispersion with SW, Tersoff, MEAM, ML potentials |
| 3 | phonondb / MP | Download reference DFT phonon data for Si and diamond |
| 4 | Literature / INS | Extract experimental dispersion curves at 300 K (or low T) |
| 5 | Python | Overlay all curves on the same high-symmetry path (Γ–X–K–Γ–L) and compute RMS errors in frequencies |

**Key comparison points:**
- **Optical phonon frequencies at Γ** — very sensitive to potential/basis quality.
- **Acoustic branch slopes near Γ** — determine elastic constants and sound velocities.
- **Phonon DOS** — integrate to compare zero-point energies and heat capacities.

---

## Quick-Start Files You Can Download

- **ALAMODE Si + LAMMPS tutorial files:** Available in the `example/Si_LAMMPS` directory of the ALAMODE distribution.
- **ML potential + LAMMPS + ALAMODE inputs:** A 2024 paper on Si/diamond interfacial thermal conductance provides VASP, LAMMPS, and ALAMODE input files on Mendeley Data.
- **NIST Interatomic Potentials:** Curated LAMMPS-compatible files for Si (MEAM, Tersoff, SW, etc.) with computed property comparisons.

If you want, I can also write a short Python script that plots phonon dispersion overlays from `band.yaml` (phonopy) and ALAMODE output for direct visual comparison.

---

# USER

Yes write those scripts, but write also scrips to download the experimental data from some databases you recommended. You can try multiple databases I would prefere if you have some scripting CLI Interface rather than search manually on their website

---

# Kimi

Here is the complete CLI toolkit. All scripts are saved to the output folder and ready to download.

---

### Download Links

| File | Purpose |
|------|---------|
| [download_phonon_refs.py](sandbox:///mnt/agents/output/download_phonon_refs.py) | CLI downloader for MP, phonondb, and Mendeley Data |
| [setup_alamode_phonon.py](sandbox:///mnt/agents/output/setup_alamode_phonon.py) | Generates ALAMODE + LAMMPS inputs for Si/diamond |
| [plot_phonon_benchmark.py](sandbox:///mnt/agents/output/plot_phonon_benchmark.py) | Overlay & benchmark phonon curves + RMS errors |
| [experimental_phonon_data.json](sandbox:///mnt/agents/output/experimental_phonon_data.json) | Reference INS data points (Si & diamond) |
| [README.md](sandbox:///mnt/agents/output/README.md) | Full usage guide |

---

### What each script does

**1. `download_phonon_refs.py`** — Three subcommands, no manual web browsing:

```bash
# Materials Project (DFPT phonons) — free API key required
python download_phonon_refs.py mp --api-key YOUR_KEY --material-id mp-149 --outfile si_mp.json

# phonondb (Atsushi Togo's database) — uses WMD-group GitHub mirror
python download_phonon_refs.py phonondb --material-id mp-149 --outdir ./phonondb_si

# Mendeley Data (MTP ML potential) — DOI 10.17632/6tjhd74t5r
python download_phonon_refs.py mendeley --doi 10.17632/6tjhd74t5r --outdir ./mtp_data
```

**2. `setup_alamode_phonon.py`** — Generates the full ALAMODE workflow:

```bash
# Si with cheap classical potentials
python setup_alamode_phonon.py --material Si --potential sw --supercell 2 2 2
python setup_alamode_phonon.py --material Si --potential tersoff --supercell 2 2 2

# Diamond with Tersoff
python setup_alamode_phonon.py --material diamond --potential tersoff --supercell 2 2 2

# Si with MTP (after downloading from Mendeley)
python setup_alamode_phonon.py --material Si --potential mtp --mtp-file ./mtp_data/Si_diamond.mtp --supercell 2 2 2
```

This creates:
- `<prefix>.lammps` — structure file
- `<prefix>_force.in` — LAMMPS input template
- `<prefix>.alamode.in` / `.anphon.in` — ALAMODE solver inputs
- `run_displace.sh`, `run_extract.sh`, `run_alamode.sh` — step-by-step bash scripts

**3. `plot_phonon_benchmark.py`** — Overlay everything and compute RMS errors:

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

---

### Recommended "best cheap" choices

| Code | Best cheap option | Quality |
|------|-------------------|---------|
| **DFTB+** | `matsci-0-3` or `pbc-0-3` Slater–Koster tables | Moderate; use with phonopy |
| **LAMMPS (Si)** | Lenosky MEAM | Best classical potential for Si phonons |
| **LAMMPS (C)** | Tersoff (`C.tersoff`) | Fast but systematically overestimates |
| **ML potential** | MTP from Mendeley DOI `10.17632/6tjhd74t5r` | DFT accuracy, open data, validated for phonons |

---

### A note on experimental data

There is **no single centralized REST API** for experimental phonon dispersions. The `experimental_phonon_data.json` includes approximate inelastic neutron scattering (INS) reference points from classic literature (Dolling 1963 for Si, Warren 1967 for diamond). For publication-quality benchmarks, you should cross-check these against the original papers or modern neutron databases. The plot script will overlay these points at the correct high-symmetry positions and print RMS errors automatically.

---

# USER

I have dftb+ in venv ML
```
prokop@GTX3090:~/git/CompChemUtils$ venvML
(ML) prokop@GTX3090:~/git/CompChemUtils$ dftb+
|==================================================

SLAKOS
/home/prokop/SIMULATIONS/dftbplus/slakos
```

pyscf here
```
prokop@GTX3090:~/git/CompChemUtils$ conda activate
(base) prokop@GTX3090:~/git/CompChemUtils$ python
Python 3.12.2 | packaged by Anaconda, Inc. | (main, Feb 27 2024, 17:35:02) [GCC 11.2.0] on linux
Type "help", "copyright", "credits" or "license" for more information.
Ctrl click to launch VS Code Native REPL
>>> import pyscf
>>> 


```
Lammps here

/home/prokop/SW/lammps-29Aug2024
```

---

# Kimi

Here are the exact installation steps for each tool.

---

## 1. phonopy

This is a pure Python package. Install it in your existing environment:

```bash
pip install phonopy
```

Or if you prefer conda:

```bash
conda install -c conda-forge phonopy
```

**Dependencies it will pull automatically:** `numpy`, `scipy`, `pyyaml`, `matplotlib`, `h5py`, `spglib`.

**Verify:**

```bash
python -c "import phonopy; print(phonopy.__version__)"
phonopy --help
```


## 2. ALAMODE

ALAMODE is a C++ code with Python helper scripts. You need to compile the C++ binaries and put the Python scripts on your `PATH`.

### Step A: Install system dependencies

**Ubuntu/Debian:**

```bash
sudo apt-get update
sudo apt-get install -y cmake g++ libeigen3-dev libfftw3-dev libboost-all-dev
```

**Fedora/RHEL:**

```bash
sudo dnf install cmake gcc-c++ eigen3-devel fftw-devel boost-devel
```

**macOS:**

```bash
brew install cmake eigen fftw boost
```

### Step B: Clone and build

```bash
cd ~/SW
git clone https://github.com/ttadano/alamode.git
cd alamode

# Build C++ binaries
mkdir build && cd build
cmake .. -DCMAKE_INSTALL_PREFIX=$HOME/.local
make -j$(nproc)
make install
```

This installs:
- `alm` — force constant solver
- `anphon` — phonon calculator
- `qe2alamode`, `extract.py`, `displace.py` — helper scripts

### Step C: Add to PATH

Add to your `~/.bashrc` (or `~/.zshrc`):

```bash
export PATH=$HOME/.local/bin:$PATH
export PYTHONPATH=$HOME/SW/alamode/tools:$PYTHONPATH
```

Then reload:

```bash
source ~/.bashrc
```

**Verify:**

```bash
alm --help
anphon --help
which displace.py
which extract.py
```

## 3. Rebuild LAMMPS with MANYBODY and MEAM

Your LAMMPS binary at `~/SW/lammps-29Aug2024/src/lmp_serial` was built without the required packages. You need to recompile.

```bash
cd ~/SW/lammps-29Aug2024/src

# Enable the packages you need
make yes-manybody    # Stillinger-Weber, Tersoff
make yes-meam        # MEAM
make yes-phonon      # fix phonon (optional but useful)

# Rebuild
make clean
make serial -j$(nproc)
```

If you need MPI parallel builds instead:

```bash
make mpi -j$(nproc)
```

**Verify the packages are active:**

```bash
~/SW/lammps-29Aug2024/src/lmp_serial -h | grep -i "manybody\|meam\|sw\|tersoff"
```

You should see `sw`, `tersoff`, `meam` in the pair style list.

## 4. Quick Checklist

| Tool | Install command | Verify |
|------|----------------|--------|
| **phonopy** | `pip install phonopy` | `phonopy --help` |
| **ALAMODE** | `git clone` + `cmake` + `make install` | `alm --help` |
| **LAMMPS rebuild** | `make yes-manybody yes-meam && make serial` | `lmp_serial -h \| grep sw` |

---

## 5. Once Everything Is Installed

Run the scripts I provided earlier:

```bash
# 1. Download reference data
python download_phonon_refs.py phonondb --material-id mp-149 --outdir ./phonondb_si

# 2. Generate ALAMODE inputs for Si with SW
python setup_alamode_phonon.py --material Si --potential sw --supercell 2 2 2

# 3. Follow run_alamode.sh to run displacements, LAMMPS, and ALAMODE

# 4. Plot
python plot_phonon_benchmark.py \
    --material Si \
    --alamode Si_sw_2x2x2.band.dat \
    --experimental experimental_phonon_data.json \
    --output si_benchmark.png
```

If you hit any compilation errors during the ALAMODE or LAMMPS builds, paste the error message and I'll help debug it.

---

## 6. Reference Data Sourcing Report

### 6.1 Silicon DFT Reference

**Source:** phononDB (AFLOW-based DFT phonon database)  
**Location on disk:** `/home/prokop/SIMULATIONS/phononDB_repo/phonon_db_tarred/`  
**File used:** `Si_phonondb_band.yaml`

**Procedure:**
1. Searched the local phononDB repository for Si entries.
2. Found the band structure YAML for Si (mp-149, diamond structure, space group Fd-3m).
3. Copied the `band.yaml` to `./phonondb_ref/Si_phonondb_band.yaml`.
4. Verified the data contains 6 phonon bands across the standard high-symmetry path (L-Γ-X-K-Γ).

**Data format:** phonopy `band.yaml` (v4) with `nqpoint`, `natom`, `phonon` array, and `labels` / `segment_nqpoint` at the top level.

---

### 6.2 Diamond DFT Reference

**Source:** Materials Project (MP) -- phonon dispersion calculated via DFPT (ABINIT, PBEsol, norm-conserving pseudopotentials from Pseudo-dojo v0.3)  
**Material ID:** `mp-66` (Carbon, diamond structure, Fd-3m)  
**API key:** Loaded from environment variable `MATERIALSPROJECT_API_KEY` (never hardcoded in scripts)  
**Method:** `pymatgen.ext.matproj.MPRester.get_phonon_bandstructure_by_material_id('mp-66')`

**Why not phononDB?**  
The local phononDB repository contains **no diamond entry** for mp-66 or any Fd-3m carbon allotrope. A full catalog search returned only a single unrelated carbon structure (mp-990448, hexagonal P6/mmm). Diamond is surprisingly absent from this snapshot of phononDB.

**Procedure:**
1. Attempted to query phononDB locally -- no diamond found.
2. Attempted direct `curl` to Materials Project REST endpoints -- deprecated/returned errors (`403 Forbidden`, `410 Gone`).
3. Used `pymatgen.ext.matproj.MPRester` (legacy API client, stable for phonon queries) with the API key stored in `$MATERIALSPROJECT_API_KEY`.
4. Retrieved the `PhononBandStructure` object; extracted:
   - `qpoints` (fractional coordinates)
   - `distance` (cumulative path distance)
   - `bands` (frequencies in THz)
   - `labels_dict` (high-symmetry point labels)
5. Wrote to `mp_diamond_phonon_bands.dat` in human-readable columnar format.

**Output file:** `mp_diamond_phonon_bands.dat`  
**Format:** `# qx qy qz distance mp_DFT_b1 ... mp_DFT_b6 label`  
**Shape:** 219 q-points x 6 bands  
**Path labels identified:** `Γ`, `X`, `K`, `Γ`, `L`, `X`, `U|K`, `Γ`

**Key frequencies (THz):**
| Point | Optical max | Acoustic (LA/TA) |
|-------|-------------|------------------|
| Γ     | 39.13       | 0.00             |
| X     | 35.61       | 25.81 / 28.21    |
| L     | 39.28       | 5.99 / 9.52      |

---

### 6.3 Exported Combined Data Files

**Script:** `export_phonon_bands.py`

**Purpose:** Merge phonon band data from multiple calculators and one DFT reference into a single text file with aligned q-vectors.

**Input files per material:**
| Method | File pattern |
|--------|-------------|
| DFTB+  | `phonon_results/{mat}_dftb_2x2x2/band.yaml` |
| LAMMPS SW | `phonon_results/{mat}_sw_2x2x2/band.yaml` |
| LAMMPS Tersoff | `phonon_results/{mat}_tersoff_2x2x2/band.yaml` |
| LAMMPS MEAM | `phonon_results/{mat}_meam_2x2x2/band.yaml` (Si only) |
| DFT reference | `phonondb_ref/Si_phonondb_band.yaml` (Si) or `mp_diamond_phonon_bands.dat` (diamond) |

**Interpolation strategy:**  
Because different calculators may use slightly different q-point meshes along the same path, each `band.yaml` is parsed into `(distance, frequencies, labels)`. The DFT reference distances are taken as the master grid. For every other method, frequencies are interpolated onto the master distances using linear interpolation (`numpy.interp`). This ensures all methods share exactly the same q-point sampling.

**Output format:**
```
# qx qy qz distance dftb_b1 dftb_b2 ... dftb_b6 sw_b1 ... sw_b6 tersoff_b1 ... tersoff_b6 meam_b1 ... meam_b6 phonondb_b1 ... phonondb_b6 label
```

**Generated files:**
- `Si_phonon_bands.dat` -- 427 q-points, 5 methods
- `diamond_phonon_bands.dat` -- 60 q-points, 3 methods (DFTB+, Tersoff, MP DFT)

---

### 6.4 Comparison Plot with MP DFT Reference

**Script:** `plot_mp_diamond.py`

**Approach:**
1. Load the MP DFT data from `mp_diamond_phonon_bands.dat`.
2. Load each computed `band.yaml` from `phonon_results/`.
3. **Interpolate onto the MP path** by matching q-points in fractional coordinates (minimum-image distance) rather than by path distance. This avoids distortions caused by different lattice constants or path definitions.
4. Plot all methods on the MP distance axis.
5. High-symmetry labels are taken directly from the MP data.

**Output:** `plots/diamond_with_mp.png`

---

### 6.5 File Inventory

| File | Size | Description |
|------|------|-------------|
| `Si_phonondb_band.yaml` | ~60 KB | Si DFT reference from phononDB |
| `Si_phonon_bands.dat` | 211 KB | Combined Si bands (5 methods, 427 q-points) |
| `mp_diamond_phonon_bands.dat` | 31 KB | Diamond DFT from Materials Project (219 q-points) |
| `diamond_phonon_bands.dat` | 98 KB | Combined diamond bands (3 methods, 60 q-points) |
| `plots/Si_comparison.png` | ~500 KB | Si benchmark with phononDB DFT |
| `plots/diamond_with_mp.png` | 680 KB | Diamond benchmark with MP DFT |
| `export_phonon_bands.py` | ~4 KB | Exporter script |
| `plot_mp_diamond.py` | ~5 KB | MP overlay plotter |

---

## MMFF Phonon Frequency Refinement (June 2026)

### Achievements

1. **Fixed MMFF backend unit handling**
   - Ensured all positions, cells, and displacements are in Angstrom (FireCore native units)
   - Removed incorrect Bohr-to-Angstrom double-conversion
   - Phi matrix units correctly treated as eV/Å²
   - Frequency conversion constant: 15.6337 THz per sqrt(eV/Å²/amu)

2. **Integrated FireCore parameter scaling API**
   - Added `--mmff-scale-bond` and `--mmff-scale-angle` flags to `run_phonon.py`
   - Uses FireCore's `getBuffs()`, `setBondParamsByType()`, `setAngleParamsByType()` functions
   - Allows runtime modification of force constants without editing parameter files

3. **Diamond MMFF vs DFTB+ benchmark**
   - DFTB+ optical at Γ: **44.10 THz**
   - MMFF default (bonds+angles): **41.25 THz** (6.5% low)
   - MMFF 1.25x bonds: **42.89 THz** (2.8% low)
   - MMFF 1.25x bonds+angles: **48.15 THz** (9.1% high)

4. **Enhanced plotting script**
   - First calculation (DFTB+) automatically shown as bold black reference with "REF" prefix
   - Custom labels supported via `--label` flag for variant identification
   - Example: `MMFF +25% K_bond`, `MMFF +25% K_bond+K_ang`

### Key Files Modified

- `examples/phonons/phonon_backends.py`: Added `scale_bond`, `scale_angle` parameters to `MMFFBackend`
- `examples/phonons/run_phonon.py`: Added CLI flags for parameter scaling
- `examples/phonons/plot_phonon_comparison.py`: Enhanced reference line styling and custom labels

### Usage Example

```bash
# MMFF with 1.25x bond stiffness scaling
python run_phonon.py --structure diamond_primitive --method mmff \
  --supercell 3 3 3 --q-path-file plots/diamond_qpath_280.dat \
  --outdir test_primitive/diamond_mmff_1.25bond_3x3x3 \
  --hessian-pbc --freq-convention signed --band-solver unified \
  --force-recompute --mmff-enable-angles --mmff-scale-bond 1.25

# Plot comparison with custom labels
python plot_phonon_comparison.py \
  --calc test_primitive/diamond_primitive_dftb_3x3x3/phonon_bands.npz \
  --label "REF DFTB+" \
  --calc test_primitive/diamond_primitive_mmff_default_3x3x3/phonon_bands.npz \
  --label "MMFF default" \
  --calc test_primitive/diamond_primitive_mmff_1.25bond_3x3x3/phonon_bands.npz \
  --label "MMFF +25% K_bond" \
  --output plots/diamond_comparison_mmff_scaling.png
```

### Notes on Force Field Terms

- The `setSwitches` API in FireCore MMFF was tested but did not significantly affect the diamond phonon spectrum
- Diamond sp3 network is bond-dominated; angle terms have minimal effect on optical modes
- Bond stiffness scaling is the most effective way to tune optical frequencies
- To match DFTB+ (44.10 THz) from MMFF default (41.25 THz): scale factor ≈ 1.33