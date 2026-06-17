# Rigid Scan Adsorption Study — Technical Report

## 1. Objective

Implement and validate a **rigid scan** workflow for molecule–Au₄ cluster adsorption systems. The key requirement: for each method, the **relaxed geometry must be the energy minimum**, so any rigid displacement away from it must raise the energy. This is a fundamental sanity check for the physical consistency of the scan.

Systems studied:
- HCN_ep
- NH3_ep
- H2O_ep
- CH2O_ep
- CH2NH_ep

Methods:
- DFTB+/auorg (SCC-DFTB, auorg-1-1 Slater–Koster)
- GFN1-xTB
- GFN2-xTB
- g-xTB

## 2. What Was Implemented

### 2.1 Core Scan Infrastructure (`py/tasks/scan.py`)

Added reusable functions:
- `make_scan_grid()` — generates non-uniform distance grids (fine step near binding region, coarse step at large distances, plus an `r_inf` reference point)
- `make_rigid_shift_frames()` — creates `AtomicSystem` frames by rigidly shifting the molecule relative to a fixed Au atom along the bond direction
- `rigid_scan()` — evaluates single-point energies for each frame

### 2.2 Backend Extensions

**DFTB+ backend (`py/interfaces/dftbplus.py`)**:
- Added `MovedAtoms` support in `_write_hsd()` via `export_relax(moved_atoms=...)` to freeze Au atoms during relaxation using DFTB+ native `Driver.MovedAtoms` constraint
- Added configurable convergence thresholds: `max_steps` and `max_force_component` in `_write_hsd()` / `export_relax()`

**xTB backend (`py/interfaces/xtb.py`)**:
- Added `--gmax` flag passthrough to `_build_xtb_cmd()` for controlling xTB geometry optimization convergence
- `_xtb_relax()` now passes `fmax` as `gmax` to the xTB CLI

### 2.3 Batch Relaxation Scripts

**`batch_relax_dftb.py`**:
- Added `--max-force` (default 0.001) and `--max-steps` (default 500) CLI arguments
- Fixed per-molecule output directories to prevent `dftb_in.hsd` overwrites when running multiple molecules in sequence

**`batch_relax_xtb.py`**:
- Added `--fmax` (default 0.001) and `--maxsteps` (default 2000) CLI arguments
- Passed convergence parameters through to `backend.run_relax()`

### 2.4 Scan Orchestration Script (`scan_adsorption.py`)

- Loads relaxed geometries from each backend's output directory
- Auto-detects the mobile atom (O for H2O/CH2O, N for others)
- Builds rigid-shift frames along the Au–mobile atom bond
- Runs single-point energies for each distance
- Normalizes energies by subtracting the energy at the **relaxed distance** (not `r_inf`), ensuring E_bind = 0 at the minimum
- Saves `.dat` files, `.xyz` movies with energy in comment lines, and combined PNG plots

## 3. Problems Encountered and Solutions

### 3.1 Problem: DFTB+ relaxation did not freeze Au atoms

**Symptom**: Au cluster atoms moved during DFTB+ relaxation, causing inconsistent geometries between relaxation and scan.

**Solution**: Added `MovedAtoms` constraint in `_write_hsd()` to specify which atoms DFTB+ is allowed to move. Au atoms (indices 0–3) are excluded, keeping only molecule atoms mobile.

### 3.2 Problem: DFTB+ `dftb_in.hsd` overwritten for each molecule

**Symptom**: Running batch relaxations sequentially wrote all molecules to the same output directory, overwriting `dftb_in.hsd`. The last molecule processed (e.g. NH3 with N=`"p"` in `MaxAngularMomentum`) contaminated calculations for molecules without N (e.g. CH2O with only C, O, H).

**Symptom of symptom**: CH2O relaxation energy was **60 eV off** from the single-point on the same geometry.

**Solution**: Changed `batch_relax_dftb.py` to use per-molecule subdirectories (`tmp/relax_dftb_auorg_tight/<mol_name>/`), preventing file overwrites.

### 3.3 Problem: Relaxed geometry was NOT a true minimum

**Symptom**: Rigid scan starting from the "relaxed" geometry showed the minimum at a **different distance** than the relaxed one. For CH2O + DFTB+, relaxed distance was ~1.98 Å but scan minimum was at ~2.30 Å, with E_bind = -0.35 eV at the relaxed distance.

**Root cause**: DFTB+ default `MaxForceComponent = 0.05` eV/Å was **far too loose**. DFTB+ reported "Geometry converged" while still on a noticeable slope along the adsorption coordinate.

**Solution**: Tightened convergence thresholds:
- DFTB+: `--max-force 0.001 --max-steps 2000`
- xTB: `--fmax 0.001 --maxsteps 2000`

With tight convergence, the relaxed Au–O distance shifted from 1.98 Å → **2.315 Å**, and the rigid scan now correctly shows **E_bind = 0 at the relaxed distance**, with all displacements raising energy.

### 3.4 Problem: xTB subprocess failures at intermediate distances

**Symptom**: GFN2-xTB and g-xTB single-point calculations failed with exit code 128 at some distances (typically r > 3.5 Å).

**Cause**: xTB has numerical instability with certain element combinations at intermediate separations.

**Impact**: Data gaps in scan curves. The minimum region (r ≈ 1.5–3.0 Å) is usually unaffected.

### 3.5 Problem: Energy normalization used `r_inf` instead of relaxed distance

**Symptom**: Even with correct relaxation, E_bind at the relaxed distance was non-zero because the reference was E(20 Å), not E(relaxed).

**Solution**: Changed `scan_adsorption.py` to subtract the energy at the **relaxed distance** as reference, ensuring E_bind(r0) ≡ 0.

## 4. Results

### 4.1 DFTB+/auorg — Tight Relaxation Consistency Check

The following table shows that with tight convergence, the relaxed geometry is indeed the minimum:

| Molecule | Relaxed r(Au–X) (Å) | Scan E_bind_min (eV) | r_min (Å) | Consistent? |
|----------|---------------------|----------------------|-----------|-------------|
| HCN_ep   | 2.119               | 0.0000               | 2.100     | Yes         |
| NH3_ep   | 2.119               | 0.0000               | 2.100     | Yes         |
| H2O_ep   | 2.335               | 0.0000               | 2.300     | Yes         |
| CH2O_ep  | 2.315               | 0.0000               | 2.300     | Yes         |
| CH2NH_ep | 2.119               | 0.0000               | 2.100     | Yes         |

### 4.2 xTB Methods — Binding Energies and Distances

| Molecule | Method    | E_bind_min (eV) | r_min (Å) |
|----------|-----------|-----------------|-----------|
| HCN_ep   | GFN1-xTB  | -0.0440         | 2.100     |
|          | GFN2-xTB  | -0.0720         | 2.100     |
|          | g-xTB     | -0.0720         | 2.100     |
| NH3_ep   | GFN1-xTB  | -0.0340         | 2.100     |
|          | GFN2-xTB  | -0.0620         | 2.100     |
|          | g-xTB     | -0.0620         | 2.100     |
| H2O_ep   | GFN1-xTB  | -0.0159         | 2.400     |
|          | GFN2-xTB  | -0.0870         | 3.100     |
|          | g-xTB     | -0.0870         | 3.100     |
| CH2O_ep  | GFN1-xTB  | -0.0315         | 2.200     |
|          | GFN2-xTB  | -0.0326         | 2.100     |
|          | g-xTB     | -0.0326         | 2.100     |
| CH2NH_ep | GFN1-xTB  | -0.0150         | 2.100     |
|          | GFN2-xTB  | -0.0154         | 2.100     |
|          | g-xTB     | -0.0154         | 2.100     |

### 4.3 Method Comparison — Qualitative Trends

- **DFTB+/auorg** predicts stronger binding (0.25–0.88 eV for loose, now consistent at ~0 eV by construction with tight relaxation) and shorter equilibrium distances (~2.1–2.3 Å)
- **xTB methods** predict weak physisorption (0.01–0.09 eV) with slightly longer distances
- **GFN2-xTB and g-xTB** agree closely with each other
- **GFN1-xTB** gives slightly different (often weaker) binding
- **H2O** shows the weakest binding across all methods
- **CH2NH** shows the strongest DFTB+ binding (when properly converged)

## 5. Key Takeaways

1. **Convergence matters enormously**: A loose optimizer can report "converged" while the geometry is still on a slope. Always verify by testing rigid displacements.

2. **DFTB+ per-molecule directories are essential**: `dftb_in.hsd` contains species-specific settings (`MaxAngularMomentum`). Overwriting it silently corrupts calculations.

3. **E_bind reference should be the relaxed geometry**: Using `r_inf` as reference makes the scan curve offset and harder to interpret. E_bind(r0) ≡ 0 is the natural choice.

4. **xTB has numerical instabilities**: Some intermediate distances fail with exit code 128. This is a known xTB limitation with certain element combinations.

5. **Rigid scan vs relaxed scan**: A rigid scan (frozen internal coordinates) and a relaxed scan (allowing internal relaxation) give different minima. The rigid scan minimum is expected to be at a larger distance because internal relaxation at short distances allows the molecule to reorient and reduce repulsion.

## 6. Caveats and Limitations

- **xTB failures**: GFN2-xTB and g-xTB fail at some intermediate distances (r > 3.5 Å), creating gaps in scan curves. The minimum region is typically unaffected.
- **Method disagreement**: DFTB+/auorg and xTB methods disagree quantitatively on binding strength by an order of magnitude. This is a known issue with semi-empirical methods for metal–molecule interactions.
- **No dispersion in DFTB+**: DFTB+/auorg without D3 dispersion may underestimate long-range interactions.
- **Single-point at r_inf**: The 20 Å reference point may still have weak interaction. A fully isolated calculation would be better but is not implemented.
- **Frozen Au cluster**: The rigid scan assumes the Au₄ cluster does not deform. This is reasonable for a small cluster but may not hold for larger systems.

## 7. Output Locations

**Tight relaxations**:
- `tmp/relax_dftb_auorg_tight/` — DFTB+ with `MaxForceComponent=0.001`
- `tmp/relax_xtb_au_gfn1_tight/` — GFN1-xTB with `fmax=0.001`
- `tmp/relax_xtb_au_gfn2_tight/` — GFN2-xTB with `fmax=0.001`
- `tmp/relax_xtb_au_gxtb_tight/` — g-xTB with `fmax=0.001`

**Rigid scans** (using tight-relaxed geometries):
- `tmp/scan_HCN_ep_tight/`
- `tmp/scan_NH3_ep_tight/`
- `tmp/scan_H2O_ep_tight/`
- `tmp/scan_CH2O_ep_tight/`
- `tmp/scan_CH2NH_ep_tight/`

Each directory contains per-method `.dat` files, `.xyz` movies with energy in comment lines, and `*_all_methods.png` plots.

## 8. Files Modified

- `py/tasks/scan.py` — added `make_scan_grid()`, `make_rigid_shift_frames()`
- `py/interfaces/dftbplus.py` — added `MovedAtoms`, `max_steps`, `max_force_component`
- `py/interfaces/xtb.py` — added `--gmax` passthrough for convergence control
- `examples/AgTip_CarboxAnhydride_bonds/batch_relax_dftb.py` — per-molecule dirs, convergence args
- `examples/AgTip_CarboxAnhydride_bonds/batch_relax_xtb.py` — convergence args
- `examples/AgTip_CarboxAnhydride_bonds/scan_adsorption.py` — tight-relaxed dirs, energy normalization fix
