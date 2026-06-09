# Git hygiene — `examples/phonons/`

Minimal repo policy: **commit modules, scripts, small essential inputs, and documentation** — not run outputs, caches, plots, or machine-specific configs.

---

## Commit (recommended next commit)

### Core pipeline (modified — stage these)

| File | Why |
|------|-----|
| `phonon_utils.py` | Unified Bloch solver, `PhononCalculator`, hessian cache, solver comparison payload |
| `phonon_backends.py` | DFTB / LAMMPS / **MMFF** backends, `hessian_pbc`, `resolve_mmff_structure` |
| `run_phonon.py` | Main CLI: MMFF flags, band solver, freq convention |
| `plot_phonon_comparison.py` | Shared q-path validation fix |

### New pipeline pieces (untracked — add)

| File | Why |
|------|-----|
| `export_phonon_bands_json.py` | Export `phonon_bands.npz` → JSON/HTML comparison |
| `phonon_bands_viewer.html` | **Source** for interactive Plotly viewer (not generated output) |

### Documentation (add)

| File | Why |
|------|-----|
| `MMFF_phonon_PBC_report.md` | Session report: physics, ASAN, FireCore vs CompChemUtils split |
| `GIT_NOTES.md` | This file |

### Optional documentation (your call)

| File | Notes |
|------|-------|
| `phonons_fitting.md` | Fitting strategy notes; contains external chat links — keep if useful internally, skip if too informal |
| `phonons_improvement.md` | Agent/session scratchpad — **do not commit** unless trimmed to durable design notes |
| `phonons_ref.md` | Already tracked; keep if still accurate |

### Essential inputs only (small text, shared q-path)

| File | Why |
|------|-----|
| `diamond_fcc_path.dat` | Already tracked; q-path preset |
| `plots/diamond_qpath_280.dat` | **Canonical 280-point diamond path** used by DFTB/Tersoff/MMFF comparisons (~15 KB) |
| `Si_qpath_ref.dat` | Si reference q-path (~few KB) |
| `experimental_phonon_data.json` | Already tracked; INS reference points |

### Template config (update + commit, not local config)

| File | Action |
|------|--------|
| `phonon_config.template.json` | **Extend** with `firecore_path`, `mmff_data_dir` placeholders; commit template only |
| `phonon_config.json` | **Do not commit** — personal absolute paths |
| `phonon_config_pbc.json` | **Do not commit** — same |

### Removals (already deleted in working tree — stage deletions)

| File | Reason |
|------|--------|
| `plot_comparison.py` | Superseded by `plot_phonon_comparison.py` |
| `plot_mp_diamond.py` | Superseded by `plot_phonon_comparison.py` |

### README touch-up (optional same commit)

Update `README.md` to list `export_phonon_bands_json.py`, `phonon_bands_viewer.html`, MMFF backend flags, and pointer to `MMFF_phonon_PBC_report.md`.

---

## Do NOT commit (results / garbage / local)

### Run outputs and caches

```text
test_primitive/              # all phonon_bands.npz, force_constants.npz, hessian_phi_blocks.npz, band.*, disp-*, phonon_state.json
phonon_results/
phonon_results_pbc/
relax_Si_*/
relax_diamond_*/
relax_*_summary.dat
alamode_results/
benchmarks/                  # LAMMPS dumps, log.test, run artifacts (see below)
__pycache__/
```

### Generated plots and exports

```text
plots/*.png
plots/*.html                 # except phonon_bands_viewer.html lives in parent dir, not plots/
plots/*.json                 # export_phonon_bands_json.py output; regenerate locally
```

Regenerate comparison locally:

```bash
unset LD_PRELOAD ASAN_OPTIONS
python export_phonon_bands_json.py --solver-comparison ...
```

### Downloaded / large reference data

```text
Articles/                    # PDF papers
phonondb_ref/
phonondb_si/
mp_diamond_phonon_bands.dat
mp_diamond_path_segments.npy
diamond_phonon_bands.dat     # unless you explicitly want a tiny text ref checked in
Si_phonon_bands.dat          # same
```

Document fetch paths in `DEPEND.md` or `README.md` instead.

### Machine-specific

```text
phonon_config.json
phonon_config_pbc.json
```

---

## Deprecated / legacy / temporary

| Item | Status | Action |
|------|--------|--------|
| `plot_comparison.py` | **Removed** | Stage `git rm` |
| `plot_mp_diamond.py` | **Removed** | Stage `git rm` |
| `run_phonon.py.bak` | Backup | Delete if present; never commit |
| `plot_phonon_comparison copy.py` | Duplicate | Delete; never commit |
| `test_diamond_phonon_bands.py` | **Legacy standalone** MMFF script (pre-`run_phonon.py`, hard-coded FireCore paths, duplicates logic now in `phonon_backends.py`) | **Do not commit** unless moved to `/test` and rewritten to use `phonon_config.json`; otherwise delete or keep local-only |
| `benchmarks/` | Old ALAMODE/LAMMPS **one-off runs** (`.force` dumps, `log.test`) | Do not commit; keep shell `.sh` + `.lammps` inputs elsewhere if still needed |
| `phonons_improvement.md` | Temporary investigation log | Do not commit |
| `test_primitive/diamond_primitive_mmff_pbc_3x3x3/diamond_primitive_mmff_3x3x3/` | Accidental nested duplicate outdir from failed runs | Delete locally |
| MMFF `fc_mode=phonopy` path in backend | **Experimental / broken** | Code can stay; document as non-production in report |

### Still supported but “legacy” workflows (keep in git if already tracked)

These are **modules**, not results — remain in repo:

- `run_phonopy_phonon.py`, `run_alamode_phonon.py`, `setup_*`, `plot_phonon_benchmark.py`, `plot_phonons.py`, `plot_alamode_overlay.py`, `relax_dftb.py`, `download_phonon_refs.py`, `export_phonon_bands.py`

No need to delete unless you later consolidate.

---

## Suggested `.gitignore` additions (repo root or `examples/phonons/`)

```gitignore
# phonons — outputs
examples/phonons/test_primitive/
examples/phonons/phonon_results/
examples/phonons/phonon_results_pbc/
examples/phonons/relax_*/
examples/phonons/alamode_results/
examples/phonons/benchmarks/
examples/phonons/phonondb_*/
examples/phonons/Articles/

examples/phonons/__pycache__/
examples/phonons/**/__pycache__/

examples/phonons/plots/*.png
examples/phonons/plots/*.html
examples/phonons/plots/*.json
!examples/phonons/plots/diamond_qpath_280.dat

examples/phonons/phonon_config.json
examples/phonons/phonon_config_pbc.json

examples/phonons/**/*.npz
examples/phonons/**/band.dat
examples/phonons/**/band.png
examples/phonons/**/band.yaml
examples/phonons/**/phonon_state.json
examples/phonons/**/disp-*/
examples/phonons/**/detailed.out
examples/phonons/**/charges.bin
examples/phonons/**/*.force
examples/phonons/**/log.lammps
examples/phonons/**/dump.*
```

Adjust if you later want to check in one **tiny** golden `phonon_bands.npz` under `/test/fixtures/` (not under `examples/`).

---

## Minimal staging command (reference only — do not run blindly)

```bash
cd examples/phonons

git add phonon_utils.py phonon_backends.py run_phonon.py plot_phonon_comparison.py
git add export_phonon_bands_json.py phonon_bands_viewer.html
git add MMFF_phonon_PBC_report.md GIT_NOTES.md
git add plots/diamond_qpath_280.dat Si_qpath_ref.dat
git add phonon_config.template.json   # after adding firecore_path / mmff_data_dir fields
git rm plot_comparison.py plot_mp_diamond.py 2>/dev/null || true

# verify nothing personal/large slipped in:
git diff --cached --stat
```

---

## What lives outside this repo

| Asset | Location |
|-------|----------|
| MMFF library / Hessian fix | `/home/prokop/git/FireCore/cpp/` |
| Crystal `.xyz` (Bohr) | `FireCore/cpp/common_resources/crystals/` |
| DFTB slakos, LAMMPS potentials | User paths in `phonon_config.json` (see template) |
| Regenerated band caches | `examples/phonons/test_primitive/` (local only) |

CompChemUtils stays the **orchestration + parity viewer**; FireCore stays the **force field + Hessian** worktree.

---

*Last updated: 2026-06-09*
