# MMFF periodic phonons — session report (Jun 2026)

This document records work on diamond primitive phonons with the FireCore MMFF backend, orchestrated from `CompChemUtils/examples/phonons/`. It is written for the next phase: **force-field fitting and PBC Hessian repair**, where most code changes will live in **`/home/prokop/git/FireCore/cpp/`**, while **`/home/prokop/git/CompChemUtils/`** remains the read-only reference, parity harness, and plotting layer.

---

## 1. Goal and physics context

**Goal:** compute bulk phonon bands for diamond (2-atom primitive, 3×3×3 supercell workflow) using MMFF, compare against DFTB+ and LAMMPS references, and fix the path that produced **negative frequencies at finite k** on the cluster (non-PBC) Hessian workflow.

**Key physics (agreed during debugging):**

| Observation | Interpretation |
|-------------|----------------|
| Same band count (6 modes) at all k | Negatives are not “missing bands” |
| Γ point OK (~28 THz optical, 3 acoustic ≈ 0) | Cluster Hessian is locally sane at k=0 |
| 277/280 q-points had 2 negative λ (signed ω) on cluster path | Bloch sum D(k) not positive semi-definite — **Φ(0,R) from cluster FD is inconsistent with periodic crystal** |
| DFTB+ has no negatives | Periodic displacement FCs respect crystal symmetry |
| `positive` freq convention clips negatives to ω=0 | Misleading flat lines; use **`signed`** for diagnosis |
| PBC Hessian (`nPBC=(1,1,1)`) removes negatives but Γ optical ≈ **1.37 THz** | **Not a fix** — spectrum collapsed (~20× too soft); separate bug |

**Proper fix direction:** correct periodic force constants / Hessian in FireCore (PBC bonds during FD, consistent Φ extraction), then validate via CompChemUtils parity plots — not flipping \|ω\| or clipping.

---

## 2. What was implemented (by repository)

### 2.1 CompChemUtils (`examples/phonons/`)

| File | Role |
|------|------|
| `phonon_utils.py` | Unified Bloch solver `solve_bands_from_phi`, `phi_blocks_from_phonopy_fc`, `PhononCalculator` with `fc_mode` / hessian cache, `build_solver_comparison_payload` |
| `phonon_backends.py` | `MMFFBackend`: `fc_mode` (`hessian` / `phonopy`), `hessian_pbc`, `compute_phi_blocks`, FireCore crystal I/O |
| `run_phonon.py` | CLI: `--mmff-fc-mode`, `--hessian-pbc` / `--no-hessian-pbc`, `--freq-convention signed`, `--band-solver unified` |
| `export_phonon_bands_json.py` | JSON + embedded HTML comparison viewer |
| `phonon_bands_viewer.html` | Interactive Plotly; toggle datasets; signed ω shows negative branches |
| `plot_phonon_comparison.py` | Q-path validation fix (all curves share master distance axis) |

CompChemUtils does **not** implement the Hessian — it calls FireCore via `pyBall/MMFF.py` and post-processes Φ(0,R) in Python.

### 2.2 FireCore (`cpp/` + `pyBall/`)

| File | Role |
|------|------|
| `cpp/libs/Molecular/MMFF_lib.cpp` | `getHessian3Nx3N`: central FD, PBC logging (`bPBC`, `nPBC`), symmetrization, zero-init |
| `pyBall/MMFF.py` | Loads **`cpp/Build/libs/Molecular/libMMFF_lib.so` only** (via `Build` symlink) |

Build rule (mandatory): **only** `/home/prokop/git/FireCore/cpp/Build/` is the runtime library path. It symlinks to `Build-opt` or `Build-asan`. Do not copy `.so` between trees.

---

## 3. Build system: what broke and how it was fixed

### 3.1 Symptom: “does not compile / cannot load MMFF”

When `Build → Build-asan` and Python ran **without** `LD_PRELOAD=libasan`:

```
OSError: .../libMMFF_lib.so: undefined symbol: __asan_option_detect_stack_use_after_return
```

When `Build-opt` was used but **dependencies were stale**:

```
nm -D libMMFF_lib.so | grep asan
  U __asan_alloca_poison
  U __asan_init
  ...
```

**Root cause:** `Build-opt`’s link line pulled **ASAN-compiled** object files from `Build-asan`:

```
.../Build/common/math/CMakeFiles/DynamicOpt.dir/DynamicOpt.cpp.o   # was asan when Build→asan
```

So the `.so` was a **mixed ASAN/opt** artifact — not a source compile error.

### 3.2 Fix (opt, no ASAN)

```bash
cd /home/prokop/git/FireCore/cpp
ln -sfn Build-opt Build

cd Build-opt
cmake --build . --target DynamicOpt ProjectiveDynamics_d MMFF_lib

# Verify clean library:
nm -D libs/Molecular/libMMFF_lib.so | grep -i asan   # must print nothing
```

After this, **MMFF loads and runs** on 54-atom supercell without ASAN preload.

### 3.3 Recommended build for phonon / fitting work

| Task | Build |
|------|--------|
| Production phonon runs, fitting loops | `Build → Build-opt` |
| Memory corruption hunt | `Build → Build-asan`, run with `LD_PRELOAD=libasan` and **no matplotlib in same process** |

---

## 4. Runtime errors — ASAN, heap corruption, and where to look

These errors indicate **real or environmental memory problems**. They are **not** “phonon plotting bugs” — treat them as blockers for trusting MMFF Hessian output until understood.

### 4.1 ASAN heap-use-after-free during `MMFF.init()` (Build-asan, supercell)

**When:** 54-atom 3×3×3 supercell, `Build → Build-asan`, `LD_PRELOAD=libasan`.

**Typical report:** AddressSanitizer: heap-use-after-free in MMFF setup (often before `getHessian3Nx3N` runs).

**Where to search in FireCore:**

- `MolWorld_sp3::init()`, `MMFFBuilder::assignBondParams`, `assignSpecialTypes`, `makeMMFFs`
- PBC neighbor list construction: `initNBmol`, `neighCell` bookkeeping for large cells
- Any use-after-free in **molecule builder** when `nPBC>0` and many image cells

**Hypothesis:** lifecycle bug in MMFF world setup for large periodic systems, exposed only under ASAN (may also exist silently in opt).

### 4.2 `double free or corruption (!prev)` after successful Hessian (Build-opt)

**When:** After `getHessian3Nx3N` **returns**, Python prints `[MMFF] Hessian norm: ...`, `[phonon] Cached Hessian Phi blocks: ...`, sometimes after `solve_bands` — then process aborts on teardown.

**What it says:** glibc heap metadata corrupted or **double `free()`** during C++ destructor / Python extension unload.

**Where to search in FireCore:**

- Global/static `MolWorld_sp3 W` in `MMFF_lib.cpp` — re-entrant `init()` without full teardown
- `MMFF.init()` called multiple times per process (backend creates new init each `compute_phi_blocks`)
- FFTW / OpenMP buffers in `eval_no_omp()` path used by Hessian FD loop
- Temporary supercell `.xyz` path: ensure no aliasing of `apos` / `fapos` buffers exposed to Python

**Workaround for testing:** run Hessian in a **subprocess** (`multiprocessing` / fresh `python -c` per structure) so teardown crash does not kill long pipelines. **Fix belongs in FireCore.**

### 4.3 ASAN + matplotlib `ft2font` crash

**When:** `run_phonon.py` reaches plotting; or any `import matplotlib` while ASAN is active in the same process.

```
AddressSanitizer: CHECK failed: asan_interceptors.cpp:458
  __cxa_throw ... matplotlib/ft2font.cpython-312-...so
```

**What it says:** ASAN interceptor conflict — **not** proof that matplotlib corrupts MMFF; it means **do not mix ASAN-instrumented runtime with normal extension modules** in one process.

**Mitigation:**

```bash
unset LD_PRELOAD ASAN_OPTIONS LSAN_OPTIONS
# or run Hessian-only scripts without importing matplotlib
```

Shell profile / `venvML` may set `ASAN_OPTIONS=detect_leaks=0:...` — clear before opt runs.

### 4.4 Mixed ASAN symbol error (section 3.1)

**What it says:** loaded `.so` was linked against ASAN objects but runtime has no ASAN.

**Fix:** rebuild entire dependency chain in one build tree; verify with `nm -D libMMFF_lib.so | grep asan`.

---

## 5. Numerical results (diamond, 3×3×3, 280-point q-path)

Shared q-path: `plots/diamond_qpath_280.dat` (must match exactly across all datasets).

| Dataset | Directory | Hessian settings | Γ optical (THz) | min ω (THz) | n(ω<−0.01) | Hessian ‖H‖ |
|---------|-----------|------------------|-----------------|-------------|------------|-------------|
| DFTB+ reference | `test_primitive/diamond_primitive_dftb_3x3x3/` | phonopy FC | ~27.7 | ≈0 | 0 | — |
| LAMMPS Tersoff | `test_primitive/diamond_primitive_tersoff_3x3x3/` | phonopy FC | (see npz) | ≈0 | 0 | — |
| MMFF cluster (good, Jun 9 ~16:45) | `test_primitive/diamond_primitive_mmff_3x3x3/phonon_bands.npz` | cluster, old run | ~27.68 | **−10.53** | **554** | — |
| MMFF cluster (opt rebuild) | `test_primitive/diamond_primitive_mmff_cluster_recompute/` | `nPBC=(0,0,0)`, `bPBC=1` | ~27.68 | **−10.53** | **554** | **3.07×10⁵** |
| MMFF PBC (new) | `test_primitive/diamond_primitive_mmff_pbc_3x3x3/` | `nPBC=(1,1,1)` | **~1.37** | ≈0 | 0 | **1.09×10⁵** |

**Important cache note:** `diamond_primitive_mmff_3x3x3/hessian_phi_blocks.npz` was **overwritten** during failed PBC experiments (~18:25) with the broken ~1.37 THz Φ data. The **good cluster bands** survive only in `phonon_bands.npz` (16:45) and in `diamond_primitive_mmff_cluster_recompute/`.

**Comparison plot (open in browser):**

- `plots/diamond_solver_comparison.html` — DFTB + MMFF cluster-signed + MMFF PBC-signed
- `plots/diamond_solver_comparison.png`
- `plots/diamond_solver_comparison.json`

Toggle **`mmff/cluster-signed (nPBC=0, opt rebuild)`** to see former negative branches (signed ω, not clipped).

---

## 6. Using CompChemUtils reference data from FireCore (read-only)

When debugging in **`/home/prokop/git/FireCore/`** only — **do not edit CompChemUtils** — treat CompChemUtils as a **frozen test oracle**.

### 6.1 Paths (absolute)

```text
COMP=/home/prokop/git/CompChemUtils/examples/phonons
FC=/home/prokop/git/FireCore
```

| Asset | Path | Use |
|-------|------|-----|
| Q-path (280 pts) | `$COMP/plots/diamond_qpath_280.dat` | Same k-points for all methods |
| DFTB+ bands | `$COMP/test_primitive/diamond_primitive_dftb_3x3x3/phonon_bands.npz` | Reference ω(k) |
| DFTB+ FC cache | `.../force_constants.npz` | phonopy FC parity |
| Tersoff bands | `$COMP/test_primitive/diamond_primitive_tersoff_3x3x3/phonon_bands.npz` | Classical FF reference |
| MMFF cluster (negatives) | `$COMP/test_primitive/diamond_primitive_mmff_cluster_recompute/phonon_bands.npz` | MMFF baseline with imaginary k-modes |
| MMFF Φ blocks (cluster) | `.../hessian_phi_blocks.npz` | Direct Φ(0,R) input to Python solver |
| MMFF PBC (broken scale) | `$COMP/test_primitive/diamond_primitive_mmff_pbc_3x3x3/` | Regression test after PBC fix |
| Crystal (Bohr) | `$FC/cpp/common_resources/crystals/diamond_primitive.xyz` | MMFF native input |
| Config template | `$COMP/phonon_config.json` | Tool paths (`firecore_path`, DFTB, LAMMPS) |

### 6.2 Minimal parity check from FireCore (Python, no CompChemUtils edits)

After rebuilding `libMMFF_lib.so`:

```bash
unset LD_PRELOAD ASAN_OPTIONS
export FIRECORE_PATH=/home/prokop/git/FireCore
export PHONON_REF=/home/prokop/git/CompChemUtils/examples/phonons

cd $FIRECORE_PATH
/home/prokop/venvs/ML/bin/python - <<'PY'
import sys, os, numpy as np
sys.path.insert(0, os.environ["FIRECORE_PATH"])
sys.path.insert(0, os.environ["PHONON_REF"])

from phonon_backends import MMFFBackend
from phonon_utils import read_structure, BOHR_TO_ANG, QPath, solve_bands_from_phi
from run_phonon import resolve_mmff_structure, load_config

ref = os.environ["PHONON_REF"]
config = {"tools": {"firecore_path": os.environ["FIRECORE_PATH"],
                    "mmff_data_dir": os.environ["FIRECORE_PATH"] + "/cpp/common_resources"}}
struct = resolve_mmff_structure("diamond_primitive", config["tools"]["firecore_path"])
pos, cell, syms, _ = read_structure(struct)
pos, cell = pos * BOHR_TO_ANG, cell * BOHR_TO_ANG

# --- FireCore Hessian (edit hessian_pbc True/False) ---
backend = MMFFBackend(firecore_path=config["tools"]["firecore_path"], hessian_pbc=False)
Phi, cell_bohr = backend.compute_phi_blocks(pos, cell, syms, 3)
qp = QPath.from_file(ref + "/plots/diamond_qpath_280.dat")
masses = np.full(2, 12.0107)  # diamond primitive
freqs, _ = solve_bands_from_phi(Phi, cell_bohr, masses, qp.qpts, fc_units='hartree_bohr2', freq_convention='signed')

# --- Compare to frozen reference (read-only) ---
dftb = np.load(ref + "/test_primitive/diamond_primitive_dftb_3x3x3/phonon_bands.npz")
f_ref = np.sort(dftb["frequencies"], axis=1)
f_mmff = np.sort(freqs, axis=1)
print("Gamma MMFF", np.sort(freqs[0]))
print("Gamma DFTB", np.sort(f_ref[0]))
print("max|Δω| along path (THz)", np.max(np.abs(f_mmff - f_ref)))
print("n negative MMFF", np.sum(freqs < -0.01))
PY
```

Run in a **fresh subprocess** if double-free on exit is still present.

### 6.3 Regenerate comparison HTML (read-only inputs)

From CompChemUtils (does not modify FireCore):

```bash
cd /home/prokop/git/CompChemUtils/examples/phonons
unset LD_PRELOAD ASAN_OPTIONS
/home/prokop/venvs/ML/bin/python export_phonon_bands_json.py --solver-comparison \
  --result-dir test_primitive/diamond_primitive_dftb_3x3x3 \
  --q-path-file plots/diamond_qpath_280.dat \
  --output plots/diamond_solver_comparison.json \
  --html plots/diamond_solver_comparison.html --embed \
  --png plots/diamond_solver_comparison.png
```

Add MMFF `.npz` files via the Python merge pattern used in the last session (load `phonon_bands.npz` with custom labels) or extend `--calc` flags.

### 6.4 `phonon_bands.npz` schema

Keys: `qpts`, `distances`, `frequencies`, `labels`, `method`, `program`, `supercell`, `band_solver`, `freq_convention`, …

All comparison scripts require **identical `qpts`** (see `validate_qpath_match` in `plot_phonon_comparison.py`).

### 6.5 DFTB+ and LAMMPS raw displacements

Under each `test_primitive/diamond_primitive_*_3x3x3/disp-001/`:

- DFTB: `geometry.gen`, `dftb_in.hsd`, `results.tag` (forces)
- Tersoff: `structure.lammps`, `dump.force`

Useful if FireCore moves to a **phonopy displacement workflow** (like DFTB) instead of full supercell Hessian.

---

## 7. Open bugs — prioritized for FireCore work

### P0 — PBC Hessian gives wrong force constants

- **Symptom:** `nPBC=(1,1,1)` → Γ_optical ≈ 1.37 THz, ‖H‖ ≈ 1.09×10⁵; cluster `nPBC=(0,0,0)` → Γ ≈ 27.7 THz, ‖H‖ ≈ 3.07×10⁵.
- **Search:** `getHessian3Nx3N` FD loop with PBC images; are `eval_no_omp()` forces consistent when displacing atoms near cell boundaries? Is Φ extraction (`extract_phi_blocks` in CompChemUtils) assuming cluster topology while H was built with images?
- **Acceptance test:** Γ optical within ~10% of DFTB (~28 THz) **and** no negative λ along standard diamond path (or negatives understood and bounded).

### P0 — Heap corruption / double-free on MMFF re-init

- **Symptom:** `double free or corruption (!prev)` after successful Hessian.
- **Search:** global `W` state, multiple `init()` per process, Python ctypes buffer lifetime.

### P1 — ASAN UAF on supercell init (Build-asan)

- **Search:** `assignSpecialTypes`, PBC neighbor arrays, bond list for 54+ atoms.

### P2 — DFTB phonopy vs unified solver mismatch (~3.35 THz max)

- Likely in CompChemUtils `phi_blocks_from_phonopy_fc` (phonopy 4 FC layout) — does not block MMFF fitting but affects DFTB as oracle.

### P3 — Experimental MMFF phonopy FC mode

- `fc_mode=phonopy` + `compute_forces`: incomplete displacements, unit issues — not production-ready.

---

## 8. Recommended workflow split (fitting phase)

```text
/home/prokop/git/FireCore/cpp/          ← PRIMARY: MMFF, PBC, Hessian FD, fitting targets
/home/prokop/git/FireCore/pyBall/       ← ctypes bindings, load Build/libMMFF_lib.so
/home/prokop/git/CompChemUtils/         ← SECONDARY: orchestration, caches, plots, parity only
```

| Activity | Repo |
|----------|------|
| Fix `getHessian3Nx3N`, PBC neighbors, init/teardown | **FireCore** |
| Parameter fitting objectives (phonon RMSE vs DFTB) | **FireCore** (compute) + read refs from CompChemUtils |
| Q-path, band plots, HTML viewer, batch benchmarks | **CompChemUtils** (unchanged) |
| Golden references (`phonon_bands.npz`, q-path) | **CompChemUtils** — treat as read-only fixtures |

---

## 9. Commands cheat sheet

### Build MMFF (opt)

```bash
cd /home/prokop/git/FireCore/cpp && ln -sfn Build-opt Build
cd Build && cmake --build . --target MMFF_lib
```

### MMFF phonon run (CompChemUtils)

```bash
cd /home/prokop/git/CompChemUtils/examples/phonons
unset LD_PRELOAD ASAN_OPTIONS
/home/prokop/venvs/ML/bin/python run_phonon.py \
  --structure diamond_primitive --method mmff --supercell 3 3 3 \
  --q-path-file plots/diamond_qpath_280.dat \
  --outdir test_primitive/diamond_primitive_mmff_cluster_recompute \
  --no-hessian-pbc --freq-convention signed --band-solver unified \
  --force-recompute
```

PBC attempt (currently broken scale):

```bash
  ... --hessian-pbc --outdir test_primitive/diamond_primitive_mmff_pbc_3x3x3
```

### ASAN debug session (FireCore only)

```bash
cd /home/prokop/git/FireCore/cpp && ln -sfn Build-asan Build
cd Build && cmake --build . --target MMFF_lib
export LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libasan.so.8
export ASAN_OPTIONS=detect_leaks=0:halt_on_error=1
# Run minimal repro — no matplotlib, small then large cell
```

---

## 10. Summary

1. **CompChemUtils** now has a modular phonon pipeline, unified Bloch solver, MMFF Hessian backend hooks, and interactive comparison HTML.
2. **FireCore** `getHessian3Nx3N` runs on Build-opt; compile/load issues were **mixed ASAN/opt linking**, not missing source.
3. **Cluster Hessian** reproduces correct Γ and **negative finite-k modes** (signed ω down to ~−10.5 THz) — the original pathology.
4. **PBC Hessian (`nPBC=(1,1,1)`)** removes negatives but produces **physically wrong** frequencies (~1.37 THz) — primary bug for **`FireCore/cpp/`**.
5. **Memory errors** (ASAN UAF, double-free) point to **MMFF init/teardown and PBC supercell lifecycle** — must be fixed before trusting automated fitting loops.
6. **CompChemUtils reference files** (`test_primitive/`, `plots/diamond_qpath_280.dat`, comparison HTML) are the parity oracle when working **read-only** from FireCore.

---

*Generated: 2026-06-09. Session artifacts: `plots/diamond_solver_comparison.html`, `test_primitive/diamond_primitive_mmff_cluster_recompute/`, `test_primitive/diamond_primitive_mmff_pbc_3x3x3/`.*
