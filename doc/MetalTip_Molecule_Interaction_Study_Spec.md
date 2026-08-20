# Systematic Metal-Tip × Molecule Interaction Study — Design Spec

```yaml
---
type: DesignSpec
title: Systematic metal-tip + molecule interaction study
status: draft
date: 2026-08-20
tags: [surface, adatom, fcc111, gpaw, paw, relax, interaction-energy, fukui, metal-tip, coordination]
depends_on:
  - py/system_specific/MetalTips.py
  - py/geom_engine.py
  - py/tasks/relax.py
  - py/tasks/interaction_energy.py
  - py/tasks/scan.py
  - py/interfaces/gpaw.py
  - py/interfaces/pyscf.py
  - examples/fukui/fukui_backend.py
related:
  - doc/Fast_method_for_coordination_bonds_molecule_tip.md
  - examples/AgTip_CarboxAnhydride_bonds/DFTB_RELAXATION_AND_SCAN_REPORT.md
  - examples/fukui/REPORT_Fukui_Metals.md
---
```

## 1. Scientific principles & motivation

### 1.1 The central question: undercoordinated atom reactivity

**The single most important comparison in this project is bare surface vs. surface
with adatom.** An adatom is an undercoordinated metal atom — it has fewer
neighbours than a surface atom, so its d-band is narrower and higher, making it
more reactive. This is the physical basis of why AFM tips (which terminate in a
single adatom) bind molecules more strongly than flat surfaces.

**Bare-vs-adatom is the absolute priority**, more important than the comparison
across different metals or different molecules. We must see the difference in
reactivity caused by undercoordination. The metal × molecule grid is valuable,
but the bare-vs-adatom contrast is the heart of the project.

### 1.1a The primary observable

The central quantity of the study is the **undercoordination energy gain**:

```
ΔΔE_undercoord = E_ads^adatom − E_ads^bare
```

where `E_ads = E_complex − E_tip − E_mol` is the thermodynamic adsorption energy
(negative = binding). `ΔΔE_undercoord < 0` means the adatom binds the molecule
more strongly than the flat surface — this is the expected result and the quantity
we plot as the primary result (per metal, per molecule).

**Distinction**: the **thermodynamic adsorption energy** `E_ads` (at relaxed
equilibrium geometry) is different from the **mechanical dissociation curve**
`V(r) = E(r) − E(r_far)` (rigid scan, no relaxation). Both are computed: `E_ads`
for the trend table, `V(r)` for the force-curve / mechanochemistry analysis. The
`r` in the scan is the donor–metal distance; `E(r_far)` is the energy at the
largest scan distance (asymptotic non-interacting limit).

### 1.2 General trends, not material-specific accuracy

This is a **systematic trend study**. We intentionally neglect some material-specific
properties (magnetism, real crystallographic phase) to keep things simple and
comparable. We want to see how interaction energy varies across metals and
molecules, not to reproduce one experimental number for one surface.

### 1.3 Why smallest possible cells

Because we want trends across many systems, we use the smallest cell that fits the
molecule without significant periodic-image interaction. This keeps cost low enough
to sample the full grid. A fixed 3×3 lateral cell for all systems ensures
comparability.

### 1.4 Why Fukui functions (cheap, only for isolated fragments)

Fukui functions (f⁺, f⁻, f⁰) quantify local reactivity. We compute them **only for
the metal alone (bare + adatom) and the molecule alone** — never for the combined
system. This means the Fukui cost (3 single-points per fragment) is **negligible
compared to the relaxation cost**. Fukui is a cheap add-on that helps rationalize
trends: a metal adatom with high f⁺ (electrophilic) should bind a molecule site
with high f⁻ (nucleophilic / electron-pair donor).

### 1.5 Why frozen-core (PAW) calculations

We want cheap calculations without explicit core electrons. GPAW uses PAW
(projector augmented wave) by design — frozen-core PAW setups are shipped for all
relevant elements. This is the default.

## 2. Protocol

Fixed sequence. Every metal and every molecule goes through the same steps with
the same DFT parameters, so results are comparable.

### Step 1 — Build metal systems

For each metal M, build two periodic systems:
- **(i) bare surface**: M(111) 3×3×3 slab (3 layers).
- **(ii) surface + adatom**: same slab + 1 adatom on fcc hollow site.

Builder: `MetalTips.build_fcc111_adatom(metal, size=(3,3,3), …)`.

### Step 2 — Relax metal systems  ← THE PRIORITY STEP

Relax both (i) and (ii):
- **Frozen**: bottom 2 layers (bulk-like substrate).
- **Free**: top layer + adatom (case ii); top layer only (case i).
- Log total energy after relaxation (`E_tip_bare`, `E_tip_adatom`).

Constraint: `freeze_atoms(bottom_layer_indices(slab, n_layers=2))`.

**This is the key infrastructure we build once and reuse forever.** Properly
relaxed metal slabs (with and without adatom) are the foundation for all later
molecule work. Focus implementation effort here first.

### Step 3 — Compute Fukui functions for metal systems (cheap)

For each relaxed metal system (bare + adatom), compute f⁺, f⁻, f⁰ via 3
single-points (N, N+1, N−1 electrons) at the relaxed geometry. Store as `.cube`
+ `.npy`. Cost is negligible vs. Step 2.

### Step 4 — Relax molecules and compute their Fukui functions

For each molecule: relax isolated in a box, compute Fukui (3 SPs). Same DFT
params as metals for comparability. Cost negligible vs. metal relaxation.

### Step 5 — Attach molecule to relaxed metal tip

Take the **relaxed** metal systems (bare + adatom) and place each molecule
facing the metal by its electron-pair donor atom. Reuse
`geom_engine.export_surface_movie_from_molecule_frames`.

### Step 6 — Relax combined systems

Relax molecule+metal: bottom 2 metal layers frozen, rest free. Log `E_complex`.

### Step 7 — Rigid radial scan (break the coordination bond)

Take the relaxed complex, pull molecule away along donor–metal axis,
**single-points only** (no relaxation). Compute `V(r) = E(r) − E(r_far)` (mechanical
dissociation curve) and `E_bind(r) = E(r) − E_tip − E_mol` (binding energy curve).
Extract `E_bind_min`, `r_eq`.

**Speed: reuse wavefunctions** between adjacent scan points — each SP uses the
previous point's wavefunctions as the initial guess. This significantly speeds up
SCF convergence for the ~15 scan points.

**Orientation sampling**: the molecule's lone-pair orientation relative to the
metal matters. Do a small canonical sampling (e.g. 3 orientations: lone-pair
along surface normal, tilted +20°, tilted −20°) for at least one metal+ molecule
to check that orientation doesn't masquerade as a metal trend. If the orientation
effect is small (<0.05 eV), use a single orientation for the full sweep.

## 3. Scope — metals

### 3.1 Why FCC(111) for all, even hypothetical phases

**The key principle**: to isolate the *chemical* trend (d-band filling,
electronegativity) from the *structural* trend (surface geometry, coordination
number), we use the **same crystallographic surface for every metal**.

FCC(111) is the natural choice:
1. Close-packed hexagonal surface — densest-packed surface of any cubic metal.
2. Experimentally stable for the noble metals (Cu, Ag, Au, Pt, Pd, Ni, Al) — the majority.
3. Same surface atom coordination, adatom site geometry, layer stacking for all
   metals → only variable is element identity.

If we mixed FCC(111), BCC(110), HCP(0001), the surface atom coordination
(9 for FCC(111), ~6-8 for BCC(110), 9 for HCP(0001)), hollow-site geometry, and
layer stacking all differ. A trend across such a mixed set would conflate
electronic and structural effects — **not apples-to-apples**.

**Trade-off**: for non-FCC metals (Ti, V, Cr, Mn, Fe, Co, Zn, Mo, W), FCC(111) is
a hypothetical structure. But: several have known high-T FCC phases (γ-Fe, β-Co,
γ-Mn); for the rest we estimate the FCC lattice constant by volume preservation;
and since we relax the top layer, the starting value is not critical. This is the
standard computational strategy for cross-element trend studies.

**BCC(110) and HCP(0001) may be added later** (Stage 3) to compare
hypothetical-FCC vs real-surface binding for non-FCC metals.

### 3.2 Metal table — crystallographic phases and FCC lattice constants

⚠️ **The lattice constants below must be verified in the literature** (at least
Wikipedia / elemental crystal tables) before use. The lattice constant is a
critical input parameter. Values marked "vol-preserving" are estimates and
should ideally be replaced by a **DFT bulk FCC equation-of-state fit** (Phase 0,
see §13) — a 1-atom FCC EOS with dense k-points is nearly free and gives a
self-consistent non-magnetic PBE FCC lattice constant for the model.

⚠️ **Bug in current `MetalTips.py`**: the `_LATTICE_A` dict puts BCC constants
(`Fe: 2.866, W: 3.165, Mo: 3.147`) in the **same table** that
`build_fcc111_adatom()` treats as FCC constants. Calling
`build_fcc111_adatom('Fe')` would use a=2.866 Å (BCC) as if it were FCC — wrong
by ~0.7 Å. **Must fix**: separate FCC and BCC lattice constant tables, or use
distinct keys (e.g. `Fe_fcc: 3.57`). The Phase 0 EOS replaces all hypothetical
values with self-consistent DFT values anyway.

| Metal | RT phase | RT lattice (Å) | FCC a (Å) | FCC source | Valence | Group |
|-------|----------|----------------|-----------|------------|---------|-------|
| Ti | HCP | a=2.95, c=4.68 | 4.13 | vol-preserving ⚠️ verify | 3d²4s² | 4 |
| V | BCC | 3.02 | 3.81 | vol-preserving ⚠️ verify | 3d³4s² | 5 |
| Cr | BCC | 2.88 | 3.63 | vol-preserving ⚠️ verify | 3d⁵4s¹ | 6 |
| Mn | α-Mn (complex cubic) | 8.91 | 3.59 | γ-Mn (HT FCC) ⚠️ verify | 3d⁵4s² | 7 |
| Fe | BCC (α-Fe) | 2.866 | 3.57 | γ-Fe (HT FCC) ⚠️ verify | 3d⁶4s² | 8 |
| Co | HCP | a=2.51, c=4.07 | 3.54 | β-Co (HT FCC) ⚠️ verify | 3d⁷4s² | 9 |
| Ni | FCC | 3.524 | 3.524 | stable FCC | 3d⁸4s² | 10 |
| Cu | FCC | 3.615 | 3.615 | stable FCC | 3d¹⁰4s¹ | 11 |
| Zn | HCP | a=2.66, c=4.95 | 3.93 | vol-preserving ⚠️ verify | 3d¹⁰4s² | 12 |
| Mo | BCC | 3.147 | 3.96 | vol-preserving ⚠️ verify | 4d⁵5s¹ | 6 |
| W | BCC | 3.165 | 3.99 | vol-preserving ⚠️ verify | 5d⁴6s² ⚠️ verify | 6 |
| Al | FCC | 4.050 | 4.050 | stable FCC | 3s²3p¹ | 13 |
| Pd | FCC | 3.891 | 3.891 | stable FCC | 4d¹⁰ | 10 |
| Ag | FCC | 4.086 | 4.086 | stable FCC | 4d¹⁰5s¹ | 11 |
| Pt | FCC | 3.924 | 3.924 | stable FCC | 5d⁹6s¹ | 10 |
| Au | FCC | 4.078 | 4.078 | stable FCC | 5d¹⁰6s¹ | 11 |

**16 metals total.** Volume-preserving estimate: a_FCC = (V_atom × 4)^(1/3).
For BCC: V_atom = a³/2. For HCP: V_atom = a²c√3/4.

- **Stable FCC at RT** (7): Ni, Cu, Al, Pd, Ag, Pt, Au — real surfaces.
- **High-temp FCC phase known** (3): Fe, Co, Mn — experimentally characterized.
- **Hypothetical FCC** (6): Ti, V, Cr, Zn, Mo, W — computational constructs.

### 3.3 The d-band filling motivation

The 3d series Ti→Zn (groups 4–12) fills the d-band from d² to d¹⁰. In the
Hammer-Nørskov d-band model, adsorption strength correlates with the d-band
center. Our FCC(111) study across this series tests this model for coordination
bonds. The 4d/5d metals (Mo, W, Pd, Ag, Pt, Au) test cross-period trends at fixed
geometry.

### 3.4 Magnetism — deliberately neglected (see §5.5)

**All metals are treated as non-magnetic** (`spinpol=False`) to keep the study
simple and comparable. This is a deliberate simplification. See §5.5 for the
consideration of what errors this may introduce.

## 4. Scope — molecules (staged)

### Stage 1 — simple neutral closed-shell (do first)

| Molecule | Donor | In `data/xyz/`? | Notes |
|----------|-------|-----------------|-------|
| H₂O | O | ✅ | |
| NH₃ | N | ✅ | |
| CH₂O | O | ✅ | |
| CH₂NH | N | ✅ | |
| H₂S | S | ❌ create | trivial |
| PH₃ | P | ❌ create | trivial |

**6 molecules, all neutral, closed-shell, no radicals, no charges.** This is the
first sweep.

### Stage 2 — larger / aromatic (after Stage 1 validated)

CO (C-donor, ⚠️ PBE overbinding — see §5.4), thiophene (S, aromatic), thiol CH₃SH
(S), pyridine (N, aromatic), furan/fural (O, aromatic), **acetonitrile CH₃CN**
(N, nitrile — small closed-shell N lone-pair donor, complementary to NH₃/imine/
pyridine, without charged-cyanide complications).

### Stage 3 — charged species (later, needs careful handling)

Thiolate RS⁻, cyanate OCN⁻, thiocyanate SCN⁻. See §5.2.

### Removed from the set

**NO** — open-shell radical, would complicate everything (spinpol, multiplicity
in Fukui N/N+1/N−1). Removed to keep Stage 1 clean.

## 5. Technical concerns

### 5.1 Dipole correction — critical for small cells

A slab with an adatom (and later a molecule) on **one side** creates a dipole
normal to the surface. In a periodic cell this produces a spurious sawtooth
potential and artificial field across the vacuum. **Dipole correction is
mandatory** for all slab calculations.

GPAW provides `DipoleCorrection` (wraps a Poisson solver). In GPAW's PW mode the
correction is a sawtooth-like potential associated with the **non-periodic cell
boundary** (z = 0 / z = L_z), not an arbitrarily chosen z₀ plane. Therefore the
correct approach is to place the **lower z boundary in clean vacuum below the
slab**, with all electron density well away from it. The slab + molecule sit in
the upper part of the cell; the vacuum below the slab is where the correction
discontinuity lives.

```
   z ↑
     |
     |   · · · vacuum (top) · · ·
     |
     |      molecule (donor → adatom)
     |        ↓ ↓ ↓
     |      adatom
     |     top layer  ← free
     |     middle     ← free
     |     bottom     ← FROZEN
     |     bottom     ← FROZEN
     |
     |   · · · vacuum (below slab) · · ·
     |
     |  ═══════════════════════════════  ← dipole correction plane HERE
     |                                    (in vacuum, below all density)
     |   · · · vacuum · · ·
     |
     +──────────────────────────────→ cell bottom (z=0)
```

**Cell height in z**: must be large enough that the cell boundary (where the
dipole correction lives) sits in a region of zero density. Start with ~4–6 Å
clear vacuum below the slab and ~4–6 Å above the slab (for relax). **Test
4/5/6 Å clearance on Cu** by inspecting the planar-averaged density, potential,
forces, and energy — choose the smallest clearance where these are converged.
Do not prescribe a fixed "21 Å"; let the test determine it.

**For the scan (Step 7)** the molecule is pulled far from the surface (up to ~6 Å
bond + molecule size), so the top vacuum must be larger. See §5.1b.

### 5.1b Two-cell strategy: small cell for relax, large-z cell for scan

**Relaxation** (Steps 2, 4, 6): use the **smallest z-cell** that still allows the
dipole correction plane to sit in vacuum below the slab. This minimizes the number
of grid points and speeds up relaxation (the dominant cost).

**Scan** (Step 7): the molecule is pulled away to ~6 Å + molecule size, so the top
vacuum must be much larger. Use a **larger z-cell for scan single-points**. Since
scans are single-points (no ionic relaxation), the larger cell is affordable.

| Purpose | z-cell | Top vacuum | Bottom vacuum | Why |
|---------|--------|------------|---------------|-----|
| Relax (metal, molecule, complex) | ~18–21 Å | ~10 Å | ~5 Å | minimal, dipole plane fits |
| Scan (complex, rigid pull) | ~28–32 Å | ~18–20 Å | ~5 Å | room for molecule at max pull distance |

The relaxed geometry from the small cell is used as the starting point for the
scan in the large cell (just rescale the cell z, keep atomic positions, add vacuum
on top).

### 5.2 Charged species (Stage 3, later)

Anions (RS⁻, OCN⁻, SCN⁻) in a periodic cell get a uniform background charge →
artifacts. Options: (a) neutral protonated forms (RSH, HOCN, HSCN); (b) GPAW
charge compensation (ok for isolated, less for interaction); (c) counter-ion.
**Defer to Stage 3.** Stage 1 uses only neutral molecules.

### 5.3 Open-shell species

**NO removed from the set** (§4). No open-shell molecules in Stage 1. All
calculations are spin-restricted.

### 5.4 CO / PBE overbinding — what is the proper method?

PBE is known to overbind CO on metals by ~0.5–1 eV (the "CO puzzle"). This is a
self-interaction error: PBE places CO 2π* antibonding states too low, over-stabilizing
the metal–CO bond. **We cannot trust the CO binding trend from PBE.**

Options for a proper treatment of CO (and CO-like C-donors):
- **RPBE** (Hammer-Hansen-Nørskov): reparameterized PBE that reduces CO overbinding
  by ~0.5 eV. Cheap (same cost as PBE). Standard fix in surface science.
- **B3LYP / PBE0 hybrids**: self-interaction correction via exact exchange. More
  accurate for CO, but ~10–100× more expensive — not viable for the full grid.
- **HSE06**: screened hybrid, cheaper than full PBE0 but still expensive.
- **DFT+U on the metal d-band**: can help but introduces a tunable parameter.

**Recommendation for Stage 2**: a method hierarchy for CO (and CO-like C-donors):
1. **PBE+D4 and RPBE+D4 for all CO cases** — RPBE is essentially free (same cost
   as PBE) and was developed specifically to improve chemisorption energetics.
   Run both and report both. The trend across metals may differ — that itself is
   informative. Note: **D4 does not cure the CO problem** because dispersion is
   not the origin of the donation/back-donation/self-interaction error.
2. **HSE06 spot checks** for Cu/Ag/Au (bare + adatom) — a screened hybrid gives
   a self-interaction-corrected reference for a few systems. More expensive but
   affordable for ~6 calculations.
3. **RPA** — only as a literature/reference-level benchmark; far too costly for
   this survey, but RPA performs much more consistently for transition-metal
   adsorption (see Schimka et al., JPCC 2018).

Flag CO results as method-dependent in the report. Do not include CO in a
PBE-only trend comparison alongside O/N/S/P donors.

### 5.5 Magnetism — deliberately neglected: is this a problem?

**Decision: all metals non-magnetic (`spinpol=False`).** This is a deliberate
simplification for a systematic trend study. But it raises a question:

**Question / consideration**: how much error does neglecting magnetism introduce
into **binding energies** and **mechanochemistry** (force curves from the scan)?

- For **non-magnetic metals** (Ti, V, Cu, Zn, Mo, W, Al, Pd, Ag, Pt, Au): no error.
- For **magnetic metals** (Cr, Mn, Fe, Co, Ni): the non-magnetic treatment gives
  the wrong bulk lattice constant (e.g. Fe: non-magnetic FCC a≈3.46 Å vs
  magnetic/paramagnetic ≈3.57 Å) and wrong d-band position. However:
  - **Binding energy** is a *difference* (E_complex − E_tip − E_mol). If the
    magnetic error is similar in the complex and the bare tip, it may partially
    cancel. This is plausible but unverified.
  - **Mechanochemistry / force curves** depend on the curvature of E(r) near
    equilibrium, which is more local and may be less sensitive to the bulk
    magnetic state than to the local adatom electronic structure.
  - The **adatom** is the reactive site; its local d-band (narrowed by
    undercoordination) may be more important than the bulk magnetic ordering.

**This is an open question to revisit**: after Stage 1, compare magnetic vs
non-magnetic binding for Fe or Ni on one molecule to quantify the error. If it's
small (<0.1 eV), the non-magnetic trend study is justified. If large, add spinpol
for the 5 magnetic metals.

### 5.6 Fukui for periodic metals — charge states

Adding/removing an electron from a metallic slab uses uniform background
compensation. For metals this is acceptable (screening). Use Fermi-Dirac smearing
(0.05 eV), same k-grid for N, N+1, N−1. Existing `run_ag111_adatom_gpaw.py`
handles this. **Cost negligible** (single-points on relaxed geometry, not relaxations).

**⚠️ Odd-electron Fukui states**: even for closed-shell molecules, the N+1 and
N−1 charge states have an **odd number of electrons** → they are open-shell
(doublet). The Fukui single-points for N±1 must use `spinpol=True` (UKS) even
though the neutral molecule is closed-shell. For metals this is handled by the
smearing; for isolated molecules in a box, explicitly set spinpol for the N±1 SPs.

### 5.6b Reactive metals — reconstruction and dissociation risk

Early transition metals (Ti, V, Cr) are highly reactive. When a molecule
approaches, the adatom may **reconstruct** (shift off the fcc hollow) or the
molecule may **dissociate** (e.g. O–H bond breaking on Ti). This is physically
real but complicates the systematic comparison. **Detection**: after each complex
relaxation, check:
- adatom displacement from initial fcc hollow (>0.5 Å = reconstruction),
- molecule bond lengths vs isolated molecule (>0.2 Å change = dissociation/activation),
- any atom that has left the molecule fragment.

If dissociation/reconstruction occurs, flag it in the report. These systems may
need separate treatment (they're not simple coordination bonds anymore).

### 5.6c One-time cell-size and layer convergence checks

Before the full sweep, do **one-time** checks on a single system (Cu + NH₃):
- **3×3 vs 4×4 lateral cell**: check ΔE_bind < 0.02 eV. If 3×3 is not enough,
  bump to 4×4 for all (doubles cost).
- **3 vs 4 layers**: check ΔE_bind < 0.02 eV. If 3 layers is not enough, add a
  4th layer (frozen) for all.

These are done once, not per system. Record the decision in the report.

### 5.7 Convergence parameters — reasonable defaults, refine later

We do not over-optimize convergence parameters. Use reasonable defaults, **start
fast**, refine later if needed.

| Parameter | Initial (fast) | Refine later | Notes |
|-----------|----------------|--------------|-------|
| XC functional | PBE | — | standard |
| Dispersion | D4 (default params) | — | we care about chemical bonds, not physisorption; D4 is enough |
| PW cutoff | 400 eV | verify 500 eV on one system | |
| **k-points** | **gamma (1×1×1)** | **recalculate with 2×2×1 or 3×3×1** | ⚠️ **critical for cost** — see §5.8 |
| Smearing | FermiDirac 0.05 eV | — | metals need smearing |
| fmax | 0.05 eV/Å | — | |
| Vacuum z (relax) | ~18–21 Å | — | §5.1b, dipole plane must fit |
| Vacuum z (scan) | ~28–32 Å | — | §5.1b |
| Dipole correction | yes, plane below slab | — | §5.1 |
| Spinpol | **False (all)** | revisit for magnetic metals | §5.5 |

### 5.8 ⚠️ K-point sampling and cost reduction — THE dominant cost factor

**Relaxation is the dominant cost.** Everything else (Fukui SPs, scan SPs) is
cheaper per step and there are fewer of them relative to the relaxation effort
(50–100 ionic steps × SCF each).

**Strategy: two-tier k-point approach.**
1. **Initial relaxation: gamma-point only (1×1×1).** This is the fastest. For a
   3×3 lateral cell, gamma-point is often adequate because the cell is large
   enough that k-point sampling has a small effect on forces. Do all 32 metal
   relaxations (16 metals × 2) at gamma-point first.
2. **Refinement: recalculate with denser k-mesh (2×2×1 or 3×3×1).** After the
   gamma-point relaxation converges, do a single relaxation restart (or just a
   few steps) at the denser k-mesh from the gamma-relaxed geometry. This is much
   cheaper than relaxing from scratch at dense k-mesh.

**We must not forget to do the refinement step.** The gamma-point relaxation is a
fast first pass; the dense-k refinement gives the production-quality geometry and
energy. Record which k-mesh was used for each result.

**This two-tier approach applies to all relaxation steps** (metal, molecule,
complex). Scan single-points should use the same k-mesh as the refined relaxation
for consistency.

### 5.9 PAW setup availability

GPAW ships PAW setups for all elements in our set (Ti, V, Cr, Mn, Fe, Co, Ni, Cu,
Zn, Mo, W, Al, Pd, Ag, Pt, Au, H, C, N, O, S, P). Verify with `gpaw info`. Early
3d metals (Ti, V, Cr) have `_sv` (semi-core in valence) setups — test whether
these matter for surface properties on one system; if yes, use consistently.

### 5.10 Missing molecule geometries

H₂S, PH₃ (Stage 1) are trivial to build. Molecule geometry generation is **not a
priority** — focus on metal relaxation infrastructure first (§6).

## 6. Priority and implementation focus

### 6.1 Absolute priority: metal relaxation infrastructure

**The metal slab relaxation (with and without adatom) is the reusable
infrastructure we will use for every future molecule study.** Building proper
relaxed metal geometries is the key deliverable of the first phase. Once we have
relaxed slabs for all 16 metals (×2 = bare + adatom), attaching any molecule is
a cheap follow-up.

**Implementation focus:**
1. `MetalTips.py`: FCC lattice constants for all 16 metals + layer-index helpers.
2. `gpaw.py`: dipole correction + two-cell (small/large-z) support.
3. `metal_tip.py`: `relax_metal_system()` — the core function.
4. Benchmark on Cu (bare + adatom), local GPAW, gamma-point — **measure time**.
5. Run all 16 metals × 2 at gamma-point.
6. Refine with denser k-mesh.

**Do not implement molecule attach / scan / driver until the metal relaxation
pipeline is solid and benchmarked.**

### 6.2 Start with coinage metals

For the very first validation, use **Cu, Ag, Au** (3 metals × 2 = 6 relaxations).
These are non-magnetic, stable FCC, well-benchmarked in the existing reports.
Verify the pipeline end-to-end on these before scaling to all 16.

### 6.3 Bare-vs-adatom is the key comparison

Every metal gets **two** systems. The difference in Fukui f⁺ and in binding
energy between bare surface and adatom tip is the central result. Do not skip the
bare-surface calculation.

## 7. Cost estimation

### 7.1 Approach: measure, don't guess

The first Cu (bare + adatom) relaxation at gamma-point serves as the benchmark.
Time it. Extrapolate.

### 7.2 Rough estimate (to be replaced by measurement)

3×3×3 FCC slab = 27 atoms + 1 adatom = 28 metal atoms. GPAW PBE, PW 400 eV,
gamma-point:

- Relaxation (gamma): ~28 atoms, ~50–100 ionic steps → **~10–30 min** (8 cores).
  This is the dominant cost.
- Fukui 3×SP: ~15–45 min per fragment (negligible vs. total relax cost).
- Scan 15×SP: ~1–4 h per system (single-points, no relaxation).

**Stage 1 grid** (16 metals × 2 surfaces × 6 molecules):
- 32 metal relaxes: ~10 h (gamma) + refinement
- 6 molecule relaxes: ~2 h
- 192 complex relaxes: ~60 h (gamma) + refinement
- 192 scans × 15 SPs: ~300 h

→ **~400 core-hours** (gamma-point, very rough). Refinement with dense k-mesh
adds ~30–50%. 4d/5d metals ~1.5–2× more expensive. **Must run on Metacentrum.**

### 7.3 Action

Implement `--benchmark` mode: Cu bare + adatom, local GPAW, gamma-point, timed.
Print extrapolated total cost.

## 8. Slab-vs-cluster parity check

### 8.1 Motivation

The full study uses periodic GPAW slabs (3×3×3, ~28 metal atoms + molecule). This
is expensive. A **cluster model** — cut a small metal cluster from the slab
(adatom + its nearest neighbours) and run with PySCF (molecular code, no
periodicity) — could be **much faster** and may give similar interaction energies
for the localized coordination bond.

If the cluster approach gives interaction energies within an acceptable tolerance
of the slab result, we could use it for rapid screening and reserve the full slab
for final validation. This would dramatically reduce cost.

### 8.2 Test system

**Cu + NH₃** (one metal, one molecule). Run both approaches with the **same
functional (PBE)** and comparable basis/accuracy:

| Approach | Code | System | Atoms | Method |
|----------|------|--------|-------|--------|
| **Slab** | GPAW (periodic) | 3×3×3 Cu(111) + adatom + NH₃, freeze bottom 2 | ~31 | PBE, PW 400 eV, gamma-point, dipole correction |
| **Cluster** | PySCF (molecular) | Cu adatom + 3 base neighbours (M₄) + NH₃ | 8 | PBE, def2-svp (or def2-tzvp), no periodicity |

Cluster sizes to test (in order of increasing cost):
- **M₁**: just the adatom + NH₃ (1 Cu + 4 atoms = 5 atoms) — crude but fastest.
- **M₄**: adatom + 3 base atoms (tetrahedron, `build_tetrahedron`) + NH₃ = 4 Cu + 4 atoms = 8 atoms.
- **M₇**: adatom + 6 nearest neighbours (bipyramid, `build_bipyramid`) + NH₃ = 7 Cu + 4 atoms = 11 atoms.
- **M₁₃**: adatom + 12 neighbours (two-layer cluster) + NH₃ — larger, test convergence.

The M₄ and M₇ builders already exist in `MetalTips.py` (`build_tetrahedron`,
`build_bipyramid`). The cluster atoms are **frozen** at their slab-relaxed positions
(only adatom + NH₃ relax) to mimic the slab constraint.

### 8.3 What to compare

| Metric | Slab (GPAW) | Cluster (PySCF) | Tolerance |
|--------|-------------|-----------------|-----------|
| E_bind at r_eq (eV) | reference | compare | Δ < 0.1–0.2 eV? |
| r_eq (Å) | reference | compare | Δ < 0.1 Å? |
| Scan curve shape | reference | compare | qualitative match? |
| **Wall-clock time** (relax) | measure | measure | — |
| **Wall-clock time** (scan, 15 pts) | measure | measure | — |

### 8.4 Expected outcome (hypothesis)

- **PySCF cluster is much faster** — no k-points, no vacuum, no dipole correction,
  smaller system. Possibly 10–100× faster per single-point.
- **E_bind may differ** — the cluster lacks the extended metallic d-band and
  image-charge screening of the slab. The cluster E_bind could be too weak
  (less screening) or too strong (narrower d-band → higher d-band center). The
  error likely **decreases with cluster size** (M₄ → M₇ → M₁₃).
- If M₇ or M₁₃ gives E_bind within ~0.1 eV of the slab, the cluster model is
  viable for screening.

### 8.5 Implementation

This is a **validation experiment**, not part of the main pipeline. Place it as a
test script:
```
test/test_slab_vs_cluster.py    # Cu + NH3: GPAW slab vs PySCF cluster, compare E_bind + time
```

Reuse:
- `MetalTips.build_fcc111_adatom` (slab) + `build_tetrahedron` / `build_bipyramid` (cluster).
- `py/interfaces/gpaw.py` (slab relax + scan).
- `py/interfaces/pyscf.py` (cluster relax + scan).
- `py/tasks/scan.py` (rigid scan grid, same for both).

Run this **after** the Cu slab benchmark (§10.1) is working, so we have the slab
reference. The cluster runs can proceed in parallel since PySCF is independent of
GPAW.

### 8.6 Decision point

If the cluster model is accurate enough and much faster:
- Use **PySCF clusters for the full metal × molecule screening sweep** (16 × 2 × 6
  = 192 systems, fast).
- Use **GPAW slabs for validation** on a subset (e.g., Cu, Ag, Au × NH₃, H₂O = 12
  systems) to confirm the cluster trends hold.

If the cluster model is not accurate enough:
- Stick with GPAW slabs for everything (more expensive but defensible).
- The cluster comparison still documents *why* we chose slabs.

## 9. Inventory of existing code (do not rebuild)

| Capability | Location | Reuse? |
|---|---|---|
| FCC(111) + adatom builder | `py/system_specific/MetalTips.py:build_fcc111_adatom` | yes — extend with layer helpers |
| Lattice constants (Cu,Ag,Au,Pt,Pd,Ni,Al; BCC Fe,W,Mo) | `MetalTips.py:_LATTICE_A` | yes — add Ti,V,Cr,Mn,Co,Zn FCC entries (§3.2) |
| M₄ / M₇ cluster builders | `MetalTips.py:build_tetrahedron`, `build_bipyramid` | yes — slab-vs-cluster test (§8) |
| `pick_fcc_hollow_base3` | `MetalTips.py` | yes |
| ASE↔AtomicSystem converter | `MetalTips.py:slab_to_arrays` | yes |
| `freeze_atoms(indices)` → `GeomConstraint` | `py/geom_engine.py:34` | yes |
| `relax(geom, backend, method, constraints=…)` | `py/tasks/relax.py` | yes |
| GPAW `run_relax` with `FixAtoms`, spinpol, PW mode | `py/interfaces/gpaw.py:290,376` | yes — add dipole correction, two-cell |
| PySCF backend | `py/interfaces/pyscf.py` | yes — slab-vs-cluster test (§8) |
| Molecule→tip attach / orientation movie | `geom_engine.export_surface_movie_from_molecule_frames` | yes (later) |
| Interaction energy task | `py/tasks/interaction_energy.py` | yes (later) |
| Rigid scan task | `py/tasks/scan.py` | yes (later) |
| Periodic Fukui (GPAW, surfaces) | `examples/fukui/run_ag111_adatom_gpaw.py` | yes — generalize to all metals |
| Molecular Fukui (PySCF) | `examples/fukui/fukui_backend.py` | **not comparable** — need GPAW molecule Fukui |
| Metacentrum PBS tooling | `examples/metacentrum/`, `test/gpaw_h2o_test.pbs`, `test/job_env.{json,sh}` | yes |
| Molecule XYZs (4 of 6 Stage-1) | `data/xyz/{H2O,NH3,CH2O,CH2NH}.xyz` | yes — 2 more (H₂S, PH₃) trivial |

## 10. What is missing (to be implemented)

### 10.1 `py/system_specific/MetalTips.py` (priority)

- Add FCC lattice constants for all 16 study metals (§3.2). For non-FCC metals,
  use the hypothetical/HT-FCC values. Keep BCC entries separate for future work.
- `bottom_layer_indices(slab, n_layers)` — z-cluster, return indices of lowest N layers.
- `top_layer_indices(slab, exclude_adatom=True)` — highest layer excluding adatom.

### 10.2 `py/interfaces/gpaw.py` (priority)

- Add **dipole correction** option to `GPAWBackend` (plane below slab, §5.1).
- Support **two-cell mode**: small z-cell for relax, large z-cell for scan (§5.1b).
- Verify gamma-point path works and is fast.

### 10.3 `py/tasks/metal_tip.py` (NEW, priority)

- `relax_metal_system(metal, with_adatom, size, n_frozen, backend, kpts, cell_z, …)`
  → relaxed geometry + E. **This is the core function.**

### 10.4 Later (after metal relaxation is solid)

- `compute_fukui_periodic(geom, backend, …)` — adapt `run_ag111_adatom_gpaw.py`.
- `relax_molecule()` + `compute_fukui_molecule()` (GPAW in a box).
- `attach_molecule_to_tip()` + `relax_complex()`.
- `rigid_scan()` — reuse `scan.py` grid, large-z cell.
- `run_systematic.py` driver.
- PBS export mode.

## 11. Validation plan (per AGENTS.md Rule 4)

1. **Benchmark**: Cu bare + adatom, local GPAW PBE, 3×3×3, gamma-point, dipole
   correction, freeze bottom 2. **Measure time.** Verify:
   - relax converges, adatom stays on fcc hollow,
   - frozen atoms do not move (max displacement < 1e-4 Å),
   - dipole correction plane is in vacuum (inspect z-density profile),
   - Fukui f⁺ localized on adatom (physically sensible).
2. **Bare-vs-adatom**: compare Fukui f⁺ max and (later) binding energy for Cu
   bare vs Cu+adatom. The adatom must show higher reactivity. **This is the key
   validation of the whole project concept.**
3. **k-point refinement**: gamma vs 2×2×1 on Cu — check ΔE and geometry change.
4. **Coinage sweep**: Cu, Ag, Au (bare + adatom) — verify trends match existing
   DFTB+ report (Cu strongest, Au/Ag weaker).
5. **Numerical sanity**: no NaN/inf; frozen-index displacement check.
6. **Reactive-metal check**: for Ti, V, Cr — detect adatom reconstruction or
   molecule dissociation after complex relaxation (§5.6b). Flag if found.
7. **Slab-vs-cluster parity** (see §8): compare GPAW slab vs PySCF cluster
   interaction energy and runtime for Cu + NH₃.
8. **Orientation check**: for one metal+molecule, verify 3 lone-pair orientations
   give ΔE_bind < 0.05 eV (§Step 7).

## 12. File / directory plan

```
py/system_specific/MetalTips.py        # + 16 FCC lattice constants, + layer-index helpers
py/interfaces/gpaw.py                  # + dipole correction, + two-cell mode
py/tasks/metal_tip.py                  # NEW: relax_metal_system() (priority), later: fukui, attach, scan
examples/MetalTip_Molecule_interaction/
  README.md
  run_systematic.py                    # thin CLI driver (later)
  REPORT.md                            # generated (later)
data/xyz/                              # + H2S.xyz, PH3.xyz (trivial)
doc/MetalTip_Molecule_Interaction_Study_Spec.md   # this file
test/test_metal_tip_benchmark.py       # Cu bare+adatom validation
test/test_slab_vs_cluster.py           # Cu + NH3: GPAW slab vs PySCF cluster (§8)
```

## 13. Implementation order

### Phase 0 — bulk FCC lattice constants (cheap, do first)

0. **Bulk FCC EOS for all 16 metals**: 1-atom FCC cell, PBE, dense k-mesh
   (e.g. 16×16×16), fit Birch-Murnaghan EOS → equilibrium a_FCC. This is nearly
   free (~minutes per metal) and gives self-consistent non-magnetic PBE FCC
   lattice constants. **Replaces** the vol-preserving estimates and literature
   values in §3.2 for all metals (even stable-FCC ones — gives the DFT equilibrium,
   which may differ slightly from experimental RT). Fix the `MetalTips.py` BCC/FCC
   table bug (§3.2) at the same time.

### Phase 1 — metal relaxation infrastructure (PRIORITY)

1. `MetalTips.py`: add all 16 FCC lattice constants (from Phase 0 EOS) + layer-index helpers.
2. `gpaw.py`: add dipole correction (cell boundary below slab) + two-cell support.
3. `metal_tip.py`: `relax_metal_system()`.
4. Benchmark: Cu bare + adatom, local GPAW, gamma-point — **measure time**, verify
   frozen atoms, verify dipole plane in vacuum (test 4/5/6 Å clearance).
5. One-time checks: 3×3-vs-4×4 cell, 3-vs-4 layers (§5.6c).
6. Run Cu, Ag, Au (bare + adatom) — validate bare-vs-adatom Fukui difference.
7. Run all 16 metals (bare + adatom) at gamma-point.
8. Refine with denser k-mesh (2×2×1).

### Phase 2 — slab-vs-cluster test + molecules

9. Slab-vs-cluster test: Cu + NH₃, GPAW slab vs PySCF cluster (§8) — compare
   E_bind and runtime. **This determines whether we screen with clusters or slabs.**
10. Create H₂S, PH₃ XYZs (trivial).
11. `metal_tip.py`: `relax_molecule()` + `compute_fukui_molecule()`.
12. `metal_tip.py`: `attach_molecule_to_tip()` + `relax_complex()`.
13. `metal_tip.py`: `rigid_scan()` (large-z cell, wavefunction reuse, orientation check).
14. `run_systematic.py` driver.
15. Stage 1 sweep: 16 metals × 2 surfaces × 6 molecules.
16. PBS export + Metacentrum submission.
17. Generate `REPORT.md` — ΔΔE_undercoord (key result) + metal × molecule grid.

### Phase 3 — Stage 2/3 molecules, magnetic-metals check

18. Add CO (with PBE+D4/RPBE+D4/HSE06 hierarchy, §5.4), thiophene, thiol, pyridine,
    furan, CH₃CN.
19. Add charged species (Stage 3, §5.2).
20. Revisit magnetism: compare magnetic vs non-magnetic for Fe or Ni (§5.5).
