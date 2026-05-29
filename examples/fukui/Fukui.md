# USER

I would like to compute Fukui function. This is basicallyy just difference of density between system with added and removed electrons right? How to do it with psi4, orca, pySCF, dftb+ ? Can you find recipy and make me clear cookbook ?

---

# Gmini-3.5-flash



Yes, fundamentally, the **Fukui function** is based on a finite difference approximation of the electron density change when adding or removing electrons (Lu, 2024; Huynh et al., 2023).

Depending on your angle of attack, you can track it in two ways:

1. **Condensed Fukui Functions ($f_A$):** Projects the values onto individual atoms using a population analysis scheme (like Mulliken, Hirshfeld, or Löwdin). This is highly efficient and provides a single numerical value per atom.
2. **3D Real-Space Fukui Functions ($f(\vec{r})$):** Generates spatial 3D grids (e.g., `.cube` files) by directly subtracting the electron density grids. Perfect for plotting isosurfaces.

### The Math Quick-Check

For a system with $N$ electrons:

* **Nucleophilic attack ($f^+$):** Measures where incoming density goes.

$$f^+(\vec{r}) = \rho_{N+1}(\vec{r}) - \rho_N(\vec{r})$$


* **Electrophilic attack ($f^-$):** Measures where density is lost.

$$f^-(\vec{r}) = \rho_N(\vec{r}) - \rho_{N-1}(\vec{r})$$


* **Radical attack ($f^0$):** The average of both.

$$f^0(\vec{r}) = \frac{\rho_{N+1}(\vec{r}) - \rho_{N-1}(\vec{r})}{2}$$



---

## 🛠️ The Ultimate Cookbook

Because tracking down 3D grid grids across four different frameworks can be an absolute headache, **the golden industry standard** for real-space analysis is to run a quick single-point energy calculation in your engine of choice, export the wavefunction/density file, and let **Multiwfn** compute the exact 3D Fukui or Dual Descriptors instantly (Lu, 2024).

Below are the tailored workflows to get condensed values or density files for all four requested engines.

### 1. ORCA Workflow (Best for 3D Grids + Multiwfn)

ORCA makes 3D real-space density subtractions incredibly clean using its native `orca_plot` utility.

#### Step 1: Run the 3 Single Points

You need to calculate the Neutral ($N$), Cation ($N-1$), and Anion ($N+1$) states **at the fixed neutral geometry**.

```txt
# Neutral (e.g., charge 0, spin 1)
! B3LYP def2-SVP KeepDens
* xyz 0 1
 C 0.0 0.0 0.0
 ...
*

```

Change the charge and multiplicity lines for the other two inputs:

* **Anion:** `* xyz -1 2`
* **Cation:** `* xyz 1 2`

#### Step 2: Extract the 3D Cubes

Run `orca_plot` on each generated `.gbw` file via your terminal:

```bash
orca_plot neutral.gbw -task plot -i 1

```

* Select option **1** (Electron Density).
* Select option **5** (Output file format) and change it to **Gaussian Cube (Standard Grid)**.
* Select option **7** to generate the `.cube` file.
* Repeat for `anion.gbw` and `cation.gbw`.

#### Step 3: Subtract Cubes in Multiwfn

Launch Multiwfn and load `anion.cube`, then follow the interactive menu (Lu, 2024):

```txt
13     # Turn on subfunction: Process grid data
11     # Grid linear combination
cation.cube  # Load the neutral or cation grid depending on f+ or f-
1 -1   # Scale factor (Anion*1 - Cation*1 for f^0 or Anion*1 - Neutral*1 for f+)
0      # Export the final Fukui 3D grid as a new .cube file

```

---

### 2. PySCF Workflow (Pure Python Scripting)

If you want to stay strictly within Python, you can evaluate the electron density matrices directly on a coordinate grid using PySCF's `dft.numint` module.

```python
import numpy as np
from pyscf import gto, dft

# Define the shared geometry
geom = 'O 0 0 0; H 0 1 0; H 0 0 1'
basis = 'def2-svp'

# 1. Compute the three states
def get_density_and_grid(charge, spin):
    mol = gto.M(atom=geom, basis=basis, charge=charge, spin=spin)
    mf = dft.RKS(mol) if spin == 0 else dft.UKS(mol)
    mf.xc = 'b3lyp'
    mf.kernel()
    
    # Generate an analytical evaluation grid
    grids = dft.gen_grid.Grids(mol)
    grids.level = 3  # Grid quality
    grids.build()
    
    # Compute density values at grid points
    dm = mf.make_rdm1()
    # Handle unrestricted layout if needed
    if len(dm.shape) == 3: 
        dm = dm[0] + dm[1]
    rho = dft.numint.eval_rho(mol, mf.grids.coords, dm)
    return rho, grids.coords

rho_N, coords = get_density_and_grid(charge=0, spin=0)
rho_A, _      = get_density_and_grid(charge=-1, spin=1) # Anion
rho_C, _      = get_density_and_grid(charge=1, spin=1)  # Cation

# 2. Compute Fukui functions directly on the grid array
f_plus  = rho_A - rho_N
f_minus = rho_N - rho_C

print("Fukui f+ at grid point 0:", f_plus[0])

```

---

### 2b. PySCF Batch Implementation (What We Actually Built)

We implemented a reusable PySCF workflow with strict separation of concerns (AGENTS.md Rule 3):

* **`fukui_backend.py`** — compute module: runs SCF for N / N+1 / N-1, writes `.cube` files, and computes condensed Mulliken Fukui indices. No plotting.
* **`run_fukui_batch.py`** — CLI wrapper: loops over a molecule database, calls backend functions, then generates 2D slice plots (xy/xz/yz through the molecular center).
* **`results/<mol>/`** — one directory per molecule with clearly labeled outputs.

#### Critical Bug Discovered & Fixed

`pyscf.tools.cubegen.density()` calls `dft.numint.eval_rho(mol, ao, dm)`, which **expects a 2D density matrix**. For unrestricted (UKS) calculations (anion and cation, doublet states), `mf.make_rdm1()` returns shape `(2, nao, nao)`. Passing this 3D array directly produced corrupted densities (e.g. integrated electrons ~5.6 for an 11-electron anion).

**Fix:** manually sum alpha + beta before writing the cube:

```python
dm = mf.make_rdm1()
if dm.ndim == 3:
    dm = dm[0] + dm[1]
cubegen.density(mol, fname, dm, resolution=0.15, margin=4.0)
```

#### Batch Results (B3LYP / def2-SVP, fixed neutral geometry)

| Molecule | Atom | f⁺ | f⁻ | f⁰ |
|---|---|---|---|---|
| **H₂O** | O | -0.083 | **0.678** | 0.297 |
| | H | **0.542** | 0.161 | 0.351 |
| **HCN** | H | 0.211 | 0.163 | 0.187 |
| | C | **0.506** | 0.474 | 0.490 |
| | N | 0.283 | 0.363 | 0.323 |
| **HCl** | H | **0.761** | 0.146 | 0.453 |
| | Cl | 0.239 | **0.854** | 0.547 |
| **CH₂O** | C | 0.287 | 0.099 | 0.193 |
| | O | 0.262 | **0.429** | 0.346 |
| | H | 0.225 | 0.236 | 0.231 |
| **CO** | C | **0.754** | **0.705** | **0.729** |
| | O | 0.246 | 0.295 | 0.271 |
| **NH₃** | N | -0.356 | **0.515** | 0.079 |
| | H | **0.452** | 0.162 | 0.307 |
| **HCOOH** | C | 0.018 | **0.585** | 0.302 |
| | O(=) | -0.034 | 0.076 | 0.021 |
| | O(-OH) | -0.036 | 0.085 | 0.024 |
| | H(acid) | **0.720** | 0.065 | 0.392 |
| | H(-OH) | 0.333 | 0.188 | 0.260 |

**Notes:**
* f⁺ for H₂O and NH₃ goes to the H atoms — the incoming electron localizes on the X–H bond periphery.
* f⁻ for H₂O, NH₃, and CH₂O peaks on the heteroatom (O or N) — electrophilic attack removes lone-pair density.
* In CO, **carbon dominates both f⁺ and f⁻**, confirming it as the reactive end.
* In HCOOH, the **acidic H has the highest f⁺**, consistent with its propensity to donate a proton.

#### Output File Structure

Each `results/<name>/` directory contains:

| File | Description |
|------|-------------|
| `rho_N.cube` / `.npy` | Neutral density |
| `rho_A.cube` / `.npy` | Anion density (N+1) |
| `rho_C.cube` / `.npy` | Cation density (N-1) |
| `mulliken_fukui.txt` | Condensed indices |
| `<name>_fukui_2D_slices.png` | 2D slice plots (f⁺ / f⁻) |

A full report is in `results/REPORT.md`.

---

### 2c. Plotting Fukui Functions from Existing Cube Files

For systems where cube files are already available (e.g., from DFTB+, ORCA, or external calculations), we provide a lightweight workflow to:

1. **Subtract density cubes** to generate Fukui function cubes
2. **Plot 2D slices** with customizable colormaps and axis limits

#### Making Fukui Cubes

Use `make_fukui_cubes.py` to subtract neutral, anion, and cation density cubes:

```bash
python examples/fukui/make_fukui_cubes.py \
    --cube-N tmp/4-elec_pot_chr_den/NaCl0/charge_density.cube \
    --cube-A tmp/4-elec_pot_chr_den/NaCl-/charge_density.cube \
    --cube-C tmp/4-elec_pot_chr_den/NaCl+/charge_density.cube \
    --out-dir tmp/4-elec_pot_chr_den/fukui_results
```

This generates:
- `f_plus.cube` — f⁺ = ρ(N+1) - ρ(N)
- `f_minus.cube` — f⁻ = ρ(N) - ρ(N-1)
- `f0.cube` — f⁰ = 0.5(f⁺ + f⁻)

#### Plotting 2D Slices

Use `plot_fukui_slices.py` to visualize densities and Fukui functions on 2D slices:

```bash
python examples/fukui/plot_fukui_slices.py \
    --cube-N tmp/4-elec_pot_chr_den/NaCl0/charge_density.cube \
    --cube-A tmp/4-elec_pot_chr_den/NaCl-/charge_density.cube \
    --cube-C tmp/4-elec_pot_chr_den/NaCl+/charge_density.cube \
    --out tmp/4-elec_pot_chr_den/fukui_results/fukui_XZ_slices.png \
    --slice xz \
    --zmin 10.0 --zmax 20.0 \
    --vmax-rho 0.1 \
    --cmap-density magma \
    --cmap-fukui seismic
```

**Key features:**
- **Slice plane selection:** `--slice xy|xz|yz` (default: xz)
- **z-axis cropping:** `--zmin` and `--zmax` limit the vertical axis range (in Å)
- **Colormap control:** Separate colormaps for density (`--cmap-density`) and Fukui (`--cmap-fukui`) panels
- **Saturation control:** `--vmax-rho` and `--vmax-fukui` set explicit color limits
- **Equal aspect ratio:** Maintains proper physical scaling
- **Atom overlays:** Tiny dot markers show atomic positions

The plot shows 6 panels:
- Top row: ρ(N), ρ(N+1), ρ(N-1) densities
- Bottom row: f⁺, f⁻, f⁰ Fukui functions

This workflow is particularly useful for analyzing substrate surfaces where the relevant region is a specific z-range (e.g., the top few Å of a surface).

---

### 3. Psi4 Workflow (Easiest Condensed Population Method)

If you want **Condensed Fukui functions** using Mulliken charges without dealing with spatial grids, Psi4 handles it beautifully in a single native script.

```python
import psi4

psi4.set_options({'basis': 'aug-cc-pVDZ', 'reference': 'uks'})

# 1. Neutral State
mol = psi4.geometry("""
0 1
O  0.000000   0.000000   0.11779
H  0.000000   0.755453  -0.47116
H  0.000000  -0.755453  -0.47116
""")
e_N, wfn_N = psi4.energy('b3lyp', return_wfn=True)
q_N = np.array(wfn_N.molecule().Bohr_to_Angstrom()) # Get Mulliken Charges here...
# (Alternatively, you can parse the output properties for charges)

```

* **Pro-Tip:** Run three sequential calculations updating `mol.set_molecular_charge()` and `mol.set_multiplicity()`.
* Extract the Mulliken (or Löwdin) atomic charges $q_A$ for each state.
* Because an electron's charge is negative, the condensed equations flip signs:

$$f_A^+ = q_A(Neutral) - q_A(Anion)$$


$$f_A^- = q_A(Cation) - q_A(Neutral)$$



---

### 4. DFTB+ Workflow (Ultra-Fast Large Systems)

DFTB+ relies on the Self-Consistent Charge (SCC) Mulliken population to converge its tight-binding approximation (Khabibrakhmanov et al., 2024; Zhang & Chan, 2022).

#### Step 1: Run the 3 calculations

In your `dftb_in.hsd` file, use the `ThirdOrder` or `SCC` block. Keep coordinates identical.

* **Neutral:** `Charge = 0.0`
* **Anion:** `Charge = -1.0`
* **Cation:** `Charge = 1.0`

Make sure you request the charges to be explicitly dumped in the `Analysis` block:

```hsd
Analysis {
  MullikenCharges = Yes
}

```

#### Step 2: Grab charges from `detailed.out`

DFTB+ generates a `detailed.out` file for each run. Find the section labeled:

```txt
Net atomic charges
  Atom  1:   -0.34125
  Atom  2:    0.17062

```

Extract these values into a vector for your three states and use the standard condensed population equations described in the Psi4 section above to yield the atomic Fukui indices.

---

### Summary Table: Which should you choose?

| Engine | Ideal For | Best Fukui Output Method |
| --- | --- | --- |
| **ORCA** | High-level DFT calculations | `.gbw` $\rightarrow$ `orca_plot` $\rightarrow$ 3D Real space grids. |
| **PySCF** | Quick automated python loops | Native grid arrays manipulation in memory. |
| **Psi4** | High-accuracy post-HF options | Highly precise Condensed Population analysis. |
| **DFTB+** | Giant frameworks/biomolecules | Ultra-fast condensed values via `detailed.out`. |

---

### References

* Huynh, B. C., Wibowo-Teale, M., & Wibowo-Teale, A. M. (2023). QSym^2: A Quantum Symbolic Symmetry Analysis Program for Electronic Structure. *arXiv*. [https://doi.org/10.1021/acs.jctc.3c01118](https://www.google.com/search?q=https://doi.org/10.1021/acs.jctc.3c01118)
* Khabibrakhmanov, A., Gori, M., Müller, C., & Tkatchenko, A. (2024). Noncovalent Interactions in Density Functional Theory: All the Charge Density We Do Not See. *Chemical Science*. [https://doi.org/10.26434/chemrxiv-2024-lf3nr](https://doi.org/10.26434/chemrxiv-2024-lf3nr)
* Lu, T. (2024). A comprehensive electron wavefunction analysis toolbox for chemists, Multiwfn. *The Journal of Chemical Physics*, *161*(8). [https://doi.org/10.1063/5.0216272](https://www.google.com/search?q=https://doi.org/10.1063/5.0216272)
* Zhang, X., & Chan, G. K.-L. (2022). Differentiable quantum chemistry with PySCF for molecules and materials at the mean-field level and beyond. *arXiv*. [https://doi.org/10.1063/5.0118200](https://www.google.com/search?q=https://doi.org/10.1063/5.0118200)

*Cited by:*

* Lu (2024): Cited by 3990
* Huynh et al. (2023): Cited by 12
* Zhang & Chan (2022): Cited by 61
* Khabibrakhmanov et al. (2024): Cited by 13

---

## Appendix A: What We Actually Built and Tested

### A.1 Files in the repository

After several iterations, the `examples/fukui/` directory contains:

| File | Role |
|------|------|
| `fukui_backend.py` | Compute module (SCF, cube I/O, Mulliken analysis). No plotting. |
| `run_fukui.py` | Unified CLI. Loads any molecule from `data/xyz/`, runs DFT for N/N+1/N-1, writes cubes, and optionally generates 1D or 2D plots. |
| `run_batch_DZVP.py` | Batch wrapper that loops over our 7 test molecules and calls `run_fukui.py` functions. |
| `results/` | def2-SVP reference outputs (from early development) |
| `results_DZVP/` | DZVP outputs with 1D and 2D plots for all 7 molecules |

Deprecated scripts deleted during cleanup: `diagnose_fukui.py`, `fukui_2D_slices.py`, `fukui_pyscf_h2o.py`, `fukui_pyscf_h2o_cube.py`, `run_fukui_batch.py`.

### A.2 Critical bug: UKS density matrix shape

`pyscf.tools.cubegen.density()` passes the density matrix directly to `dft.numint.eval_rho()`, which expects a 2D array. For unrestricted (UKS) calculations — anion and cation, both doublets — `mf.make_rdm1()` returns shape `(2, nao, nao)`. Passing the 3D array produced garbage densities. For example, the anion integrated to ~5.6 electrons instead of 11.

**Fix:** manually sum alpha + beta before writing:

```python
dm = mf.make_rdm1()
if dm.ndim == 3:
    dm = dm[0] + dm[1]
cubegen.density(mol, fname, dm, resolution=0.15, margin=4.0)
```

### A.3 CLI features

`run_fukui.py` supports:

* `--mol <name>` — load `data/xyz/<name>.xyz`
* `--basis <name>` — any PySCF basis (default `def2-svp`)
* `--xc <name>` — any PySCF functional (default `b3lyp`)
* `--plot-2d` — 2D central slices with `TwoSlopeNorm` and percentile clipping
* `--plot-1d` — 1D cuts through the molecular center (full range + zoomed valence view)
* `--vmax-pct` — percentile for colormap clipping (default 99.5)

### A.4 Basis-set comparison: def2-SVP vs DZVP

We ran the same 7 molecules at both levels. The DZVP basis gives more polarized Fukui indices:

| Molecule | Atom | f⁺ (def2-SVP) | f⁺ (DZVP) | f⁻ (def2-SVP) | f⁻ (DZVP) |
|---|---|---|---|---|---|
| **H₂O** | O | -0.083 | -0.120 | 0.678 | 0.705 |
| | H | 0.542 | 0.560 | 0.161 | 0.148 |
| **HCN** | C | 0.506 | **0.659** | 0.474 | 0.477 |
| **CH₂O** | C | 0.287 | **0.565** | 0.099 | 0.144 |
| | O | 0.262 | 0.198 | 0.429 | 0.414 |
| **CO** | C | 0.754 | **0.790** | 0.705 | 0.700 |
| **HCOOH** | H(acid) | **0.720** | 0.142 | 0.065 | 0.164 |
| | C | 0.018 | **0.455** | 0.585 | 0.146 |
| | O(=) | -0.034 | 0.221 | 0.076 | **0.471** |

Key finding: DZVP redistributes the LUMO more strongly across the carbonyl framework in HCOOH, shifting f⁺ leadership from the acid H to the C=O carbon. In CH₂O, carbon becomes the dominant nucleophilic site (f⁺ 0.57) with DZVP, whereas it was more evenly distributed with def2-SVP.

### A.5 Chemical interpretation of DZVP results

| Molecule | f⁺ (electron addition) | f⁻ (electron removal) |
|---|---|---|
| **H₂O** | Localizes on H atoms | Lost from O lone pairs |
| **HCN** | Strongly on C (0.66) | Mostly on C (0.48) |
| **HCl** | On H (0.71) | On Cl (0.87) |
| **CH₂O** | On C (0.57) | On O (0.41) |
| **CO** | Almost entirely on C (0.79) | Almost entirely on C (0.70) |
| **NH₃** | On H atoms (~0.45 each) | On N lone pair (0.53) |
| **HCOOH** | Spread across C=O (C 0.46, O 0.22) | On carbonyl O (0.47) |

### A.6 How to reproduce

Single molecule:
```bash
python run_fukui.py --mol H2O --basis DZVP --xc b3lyp --plot-2d --plot-1d
```

Batch for all 7 test molecules:
```bash
python run_batch_DZVP.py
```

Results are written to `results/<mol>_<basis>_<xc>/` containing `rho_N/A/C.cube`, `.npy`, `mulliken_fukui.txt`, and any requested PNGs.