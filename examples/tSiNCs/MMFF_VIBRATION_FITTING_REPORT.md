# MMFF Molecular Vibration Fitting Report

## Objective

Tune MMFF bond and angle stiffness parameters to reproduce reference vibrational frequencies from quantum mechanical methods (pySCF/DFTB+) for hydrocarbon molecules.

**Molecules studied:**
- CH4 (methane) — benchmark molecule, all bonds are C-H
- C2H6 (ethane) — introduces C-C bonds and mixed angles
- Adamantane (C10H16) — cage hydrocarbon, tests parameter transferability

---

## Methodology

### 1. Force Field Setup

We use the **MMFF94** force field via FireCore's `pyBall.MMFF` Python bindings with the following interactions:

- **Bonds**: harmonic stretching with equilibrium length `l0` and stiffness `k`
- **Angles**: angular deformation around equilibrium angle `ang0`
- **No non-bonded interactions** (`NonBonded = -1`)
- **No torsions** (MMFF94 sp3 model does not capture torsional modes well)

Reference parameter files:
- `BondTypes.dat`: C-H `k=16.457`, C-C `k=10.082` (eV/Å²)
- `AngleTypes.dat`: `* C *` `ang0=109.5°`, `k=5.1` (eV/rad²)

### 2. Reusable MMFF Session

A custom `MMFFMolecularSession` class (`mmff_molecular_session.py`) was implemented to:

- Initialize MMFF **once** and reuse for multiple parameter sets (avoids reinit overhead)
- Extract the full 3N×3N Hessian via `getHessian3Nx3N()`
- Apply **in-place** parameter scaling on MMFF buffers (`bKs` for bonds, `apars[:,1]` for angles)
- Handle FireCore's internal **atom reordering** (nodes → caps) by building a position-based mapping
- Return frequencies in cm⁻¹ and mass-weighted normal modes

### 3. Per-Bond-Type Scaling

Critical fix: FireCore internally reorders atoms as **nodes (C) then caps (H)**. We scale bonds correctly by:

- **C-C bonds**: neighbor index `< nnode` (node-node)
- **C-H bonds**: neighbor index `≥ nnode` (node-cap)

This prevents scaling **all** bonds uniformly, which incorrectly stiffens C-C bonds in adamantane and produces unphysical ~4000 cm⁻¹ modes.

### 4. Frequency Calculation

1. Compute Hessian `H_ij = ∂²E/∂x_i∂x_j` via finite differences (dx=1e-4 Å)
2. Mass-weight: `H_mw = H / √(m_i m_j)`
3. Diagonalize: eigenvalues → frequencies
4. Select vibrational subspace: **drop 6 lowest modes** (translations + rotations)
5. Convert: `√λ → THz → cm⁻¹`

### 5. Fitting Criterion

**RMSE** over C-H stretch region (2000–3200 cm⁻¹) for C2H6 and adamantane, since MMFF cannot capture low-frequency torsional/bending modes.

---

## Results

### CH4 (Methane)

**Reference:** pySCF B3LYP/cc-pVDZ

| Parameter | Value |
|-----------|-------|
| Optimal C-H bond scale | **1.995** |
| Optimal H-C-H angle scale | **0.30** |
| C-H stretch RMSE | ~20 cm⁻¹ |

CH4 fitting confirms the C-H bond stiffness needs to be nearly doubled from the MMFF default to match QM C-H stretch frequencies (~3000 cm⁻¹).

### C2H6 (Ethane)

**Reference:** pySCF B3LYP/cc-pVDZ

| Parameter | Value |
|-----------|-------|
| Fixed C-H bond scale | **1.995** (from CH4) |
| Fitted C-C bond scale | **1.0** (default) |
| Fitted H-C-H angle scale | **0.30** |
| C-H stretch RMSE | ~25 cm⁻¹ |

C2H6 results show that:
- The CH4 C-H scale transfers well to C2H6
- C-C bonds can remain at default MMFF stiffness
- Angle stiffness must be reduced to ~30% of default

### Adamantane (C10H16)

**Reference:** DFTB+ mio-1-1 (no pySCF reference available)

| Parameter | Value |
|-----------|-------|
| C-H bond scale | **1.995** (from CH4) |
| C-C bond scale | **1.0** (default, unchanged) |
| Angle scale | **0.30** (from C2H6) |

| Method | Max Freq (cm⁻¹) | C-H Stretches (2800–3200) | Mean C-H Stretch |
|--------|-----------------|---------------------------|------------------|
| DFTB+ mio-1-1 | 2995 | 16 modes | 2935.6 |
| MMFF (default) | 2243 | 0 modes | — |
| MMFF scaled (C-H=1.995, angle=0.30) | **3136** | 16 modes | **3099** |
| Difference vs DFTB+ | — | — | **+5.4%** |

**Key observations:**
- Scaled MMFF now produces 16 C-H stretch modes (matches DFTB+ count)
- Mean C-H stretch is ~5.4% higher than DFTB+ (acceptable given MMFF approximations)
- No more unphysical ~4000 cm⁻¹ modes (fixed by proper atom ordering)
- Low-frequency cage modes (< 500 cm⁻¹) are still missing or poorly described (MMFF fundamental limitation)

---

## File Inventory

### Core Library

| File | Purpose |
|------|---------|
| `mmff_molecular_session.py` | Reusable MMFF session with per-bond-type scaling and correct atom ordering |
| `vib_utils.py` | ASE calculators, geometry optimization, vibration utilities (modified MMFFCalc for per-bond scaling) |
| `vib_store.py` | Hierarchical data storage for frequencies, Hessians, modes |
| `vib_match.py` | Mode matching and projection matrices |

### Fitting Scripts

| File | Purpose |
|------|---------|
| `fit_mmff_ch4.py` | Grid search for CH4 bond/angle scales |
| `fit_mmff_c2h6.py` | Grid search for C2H6 (fixed C-H, fit C-C and angles) |

### Analysis Scripts

| File | Purpose |
|------|---------|
| `analyze_ch4_modes.py` | CH4 mode analysis, comparison plots, projection matrices |
| `analyze_c2h6_modes.py` | C2H6 mode analysis with scaled MMFF method |
| `analyze_adamantane_modes.py` | Adamantane mode analysis (DFTB+ reference) |
| `plot_modes_arrows.py` | Visualize vibrational modes with displacement arrows and XYZ export |

### Results (generated, do not commit)

- `results/CH4/`
- `results/C2H6/`
- `results/adamantane/`
- `results/*/plots/`

---

## Recommended Git Commit

Commit the following scripts to version control:

```bash
git add examples/tSiNCs/mmff_molecular_session.py
git add examples/tSiNCs/fit_mmff_ch4.py
git add examples/tSiNCs/fit_mmff_c2h6.py
git add examples/tSiNCs/analyze_ch4_modes.py
git add examples/tSiNCs/analyze_c2h6_modes.py
git add examples/tSiNCs/analyze_adamantane_modes.py
git add examples/tSiNCs/plot_modes_arrows.py
```

**Do not commit** the `results/` directories (large binary `.npy` files and plots).

Add to `.gitignore` if not already present:
```gitignore
examples/tSiNCs/results/
```

---

## Known Limitations

1. **Angle types**: `AngleTypes.dat` only provides one generic sp3 carbon angle type (`* C *`). We cannot separately scale H-C-H, C-C-H, and C-C-C angles without extending the parameter table or FireCore code.
2. **Torsional modes**: MMFF94 sp3 model does not capture torsional/barrier modes (missing in all molecules).
3. **Non-bonded**: Disabled in current setup; vdW interactions may matter for larger molecules.
4. **Mode count mismatch**: MMFF often yields fewer modes than QM because it misses low-frequency collective motions.

## Future Work

- Extend angle parameter table in `AngleTypes.dat` for per-angle-type scaling
- Fit C-C bond scale independently for strained cage systems (e.g., adamantane may need slight C-C adjustment)
- Add pySCF reference for adamantane if computationally feasible
- Test parameter transferability on other hydrocarbons (propane, cyclohexane)

---

*Report generated: 2026-06-11*

---

# GPT-5.2-medium

## Root cause (why 4000 happened)
FireCore/MMFF internally **reorders atoms** as:

- **nodes** (heavy atoms, e.g. C)
- then **caps** (H)

But we were doing the mass-weighting (and mode reshaping) assuming the *input XYZ order*.

For CH4/C2H6 the XYZ ordering was “nice enough” that this didn’t explode, but for adamantane (interleaved C/H) the **mass vector was applied to the wrong atoms**, which can inflate eigenfrequencies badly (that’s where the ~4000 came from).

I fixed this in [MMFFMolecularSession.compute_frequencies()](cci:1://file:///home/prokop/git/CompChemUtils/examples/tSiNCs/mmff_molecular_session.py:144:4-183:37) by:
- Building a **unique internal↔input atom mapping** from `MMFF.apos` vs input positions
- Reordering **masses into internal order** before mass-weighting
- Reordering **modes + Hessian back** into input order on output
- Selecting vibrational subspace as **(3N-6)** modes (dropping the first 6 eigenmodes), instead of the old “freq threshold hack”

After this fix, adamantane no longer has those bogus high modes.

## Bond/angle scaling (what is actually being scaled now)
You’re also right that we must scale the *right* interactions:

### Bonds ([BondTypes.dat](cci:7://file:///home/prokop/git/FireCore/cpp/common_resources/BondTypes.dat:0:0-0:0))
- **C–H**: `k = 16.457`
- **C–C**: `k = 10.082`

I updated [MMFFMolecularSession.set_scales_per_bond_type()](cci:1://file:///home/prokop/git/CompChemUtils/examples/tSiNCs/mmff_molecular_session.py:118:4-166:109) to scale **exactly**:
- node–cap neighbors → **C–H**
- node–node neighbors → **C–C**

(using `MMFF.neighs` and `MMFF.nnode`)

### Angles ([AngleTypes.dat](cci:7://file:///home/prokop/git/FireCore/cpp/common_resources/AngleTypes.dat:0:0-0:0))
Right now your [AngleTypes.dat](cci:7://file:///home/prokop/git/FireCore/cpp/common_resources/AngleTypes.dat:0:0-0:0) basically only provides `*  C  *   109.5   5.1`, i.e. **one generic sp3 carbon angle**.
So in the current FireCore buffer model we can only scale *all carbon-centered angles together* (we can’t separate H–C–H vs C–C–H vs C–C–C unless FireCore exposes per-angle-type identity, or we extend the parameter tables / code).

### Non-bonded terms
We are still running with:
- `NonBonded: -1`  (disabled)

So it’s bonds+angles only (plus whatever internal MMFF bookkeeping does), not vdW.

## Current state (what you should see now)
I overwrote the adamantane frequency files and regenerated the plot. Now:

- `results/adamantane/mmff_angles/freq.npy` max is **~2243 cm⁻¹** (unscaled)
- `results/adamantane/mmff_angles_ch1.995_cc1.0_angle0.30/freq.npy` max is **~3136 cm⁻¹** (scaled)
- No more ~4000 cm⁻¹ artifacts

And I regenerated:
- `results/adamantane/plots/mode_analysis.png`

## What’s still open
- If you want **separate** angle scaling for:
  - **H–C–H**
  - **C–C–H**
  - **C–C–C**
  
  then we need either:
  - add more explicit angle types into [AngleTypes.dat](cci:7://file:///home/prokop/git/FireCore/cpp/common_resources/AngleTypes.dat:0:0-0:0) *and make sure FireCore assigns them distinctly*, or
  - modify FireCore so it exposes/uses per-angle-type IDs we can scale selectively.

If you tell me which route you prefer (edit `.dat` only vs small FireCore change), I’ll proceed accordingly.

## Status
- **Fixed** the incorrect 4000 cm⁻¹ issue (mass/order mismatch).
- **Fixed** bond-type scaling to truly separate **C–H vs C–C**.
- **Regenerated** adamantane comparison plot with corrected data.