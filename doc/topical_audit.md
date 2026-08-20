# Topical Audit

Cross-implementation map of scientific topics in this repository. One section per topic. Each section lists every implementation location with status and notes, the parity status (where reference checks exist), and open issues.

For file locations see [`CODEMAP.md`](../CODEMAP.md); for design rules see [`ARCHITECTURE.md`](../ARCHITECTURE.md); for AI task guidance see [`doc/AGENTS/skills/`](AGENTS/skills/).

---

```yaml
---
type: TopicalAudit
title: Geometry container & I/O (AtomicSystem)
tags: [geometry, io, xyz, mol, mol2, gen, pbc]
---
```

## Summary

Canonical molecular geometry container used across the codebase. Parallel-array layout (`apos`, `enames`, `atypes`), optional PBC + lattice vectors, bond graph, neighbor lists. File I/O for XYZ (extended with lattice), MOL, MOL2, GEN. Selections, rotations, PBC replication. An object-graph alternative (`AtomicGraph`) provides stable identity for topology work.

## Implementations

| Location | Status | Notes |
|----------|--------|-------|
| [`py/AtomicSystem.py`](../py/AtomicSystem.py) | active | Production container: `apos`, `enames`, `atypes`, PBC, bonds; `saveXYZ`, `loadXYZ`, MOL/MOL2/GEN I/O; `clonePBC()`, `add_electron_pairs()`, selections, rotations, neighbor lists |
| [`py/AtomicSystem_new.py`](../py/AtomicSystem_new.py) | experimental | Fork with verbose debug logging; not the production import path |
| [`py/AtomicGraph.py`](../py/AtomicGraph.py) | active | Object-graph alternative (`Atom`/`Bond`/`Ring` with stable identity); `to_arrays()` for numpy/vispy interop; deletion does not renumber |
| [`py/atomicUtils.py`](../py/atomicUtils.py) | active | Low-level primitives: file loaders, bond/H-bond detection, angles/dihedrals, orientation frames, graph/cycle helpers, fragment assembly |
| [`py/elements.py`](../py/elements.py) | active | Periodic-table lookup (Z, radii, masses, Jmol colors, valence electrons) consumed by geometry + visualization |
| [`examples/replicate_xyz.py`](../examples/replicate_xyz.py) | active | Tile structure in XY with `clonePBC()` |
| [`examples/add_epairs.py`](../examples/add_epairs.py) | active | Add `E` dummy atoms to N/O via `add_electron_pairs()` |
| [`examples/pyutils/orient.py`](../examples/pyutils/orient.py) | active | Center + PCA-orient an XYZ |

## Parity Status

| Pair | Metric | Tolerance | Test / reference |
|------|--------|-----------|------------------|
| XYZ round-trip | atom count, positions | exact | Implicit in all relax/scan CLIs that read → write XYZ |
| `clonePBC` tiling | cell vectors, atom count | exact | `examples/replicate_xyz.py` |

## Open Issues

- `AtomicSystem_new.py` is a parallel fork — not yet reconciled with `AtomicSystem.py`.
- Legacy examples import `pyBall.AtomicSystem` (FireCore); new code uses `py.AtomicSystem`.

---

```yaml
---
type: TopicalAudit
title: Geometric constraints (GeomConstraint)
tags: [constraints, freeze, distance, angle, dihedral, backend-agnostic]
---
```

## Summary

Program-agnostic constraint specification translated by each backend to its native syntax. Used by `relax`, `relaxed_scan`, and any task that fixes atoms or internal coordinates.

## Implementations

| Location | Status | Notes |
|----------|--------|-------|
| [`py/geom_engine.py`](../py/geom_engine.py) — `GeomConstraint` dataclass | active | Types: `freeze_atoms`, `fix_distance`, `fix_angle`, `fix_dihedral` |
| [`py/geom_engine.py`](../py/geom_engine.py) — `freeze_atoms`, `fix_distance`, `fix_angle`, `fix_dihedral` | active | Constructor helpers |
| [`py/interfaces/dftbplus.py`](../py/interfaces/dftbplus.py) | active | Translates to DFTB+ `Constrain` block |
| [`py/interfaces/psi4.py`](../py/interfaces/psi4.py) | active | Only `freeze_atoms` → `frozen_cartesian` |
| [`py/interfaces/pyscf.py`](../py/interfaces/pyscf.py) | partial | Not yet implemented (warns and ignores) |
| [`py/interfaces/xtb.py`](../py/interfaces/xtb.py) | partial | xTB has no native constraints; `batch_relax_xtb.py` resets metal positions post-relax as a workaround |
| [`py/interfaces/gpaw.py`](../py/interfaces/gpaw.py) | active | Translates to GPAW `constraints` arg |

## Parity Status

| Pair | Metric | Tolerance | Test / reference |
|------|--------|-----------|------------------|
| `freeze_atoms` round-trip | frozen atom positions unchanged after relax | exact | `examples/AgTip_CarboxAnhydride_bonds/batch_relax_dftb.py` (frozen metal) |

## Open Issues

- PySCF backend ignores constraints (warns).
- xTB backend has no native constraint support — workaround only.
- `fix_angle` / `fix_dihedral` not exercised by any example yet.

---

```yaml
---
type: TopicalAudit
title: Geometry relaxation
tags: [relax, optimization, dftb, pyscf, psi4, xtb, gpaw, mmff]
---
```

## Summary

Backend-agnostic geometry optimization. `relax()` dispatches to `backend.run_relax()` (local) or `backend.export_relax()` (cluster input files). Returns `RelaxResult` (optimized geometry, per-step energies, convergence flag).

## Implementations

| Location | Status | Notes |
|----------|--------|-------|
| [`py/tasks/relax.py`](../py/tasks/relax.py) — `relax()` | active | Modes `local` / `export`; accepts `GeomConstraint` list |
| [`py/tasks/base.py`](../py/tasks/base.py) — `RelaxResult` | active | `geom`, `energies`, `converged`, `n_steps`, `output_files` |
| [`py/interfaces/dftbplus.py`](../py/interfaces/dftbplus.py) — `run_relax`, `export_relax` | active | ASE-based optimization; GenFormat export |
| [`py/interfaces/pyscf.py`](../py/interfaces/pyscf.py) — `run_relax` | active | Berny solver |
| [`py/interfaces/psi4.py`](../py/interfaces/psi4.py) — `run_relax`, `export_relax` | active | |
| [`py/interfaces/xtb.py`](../py/interfaces/xtb.py) — `run_relax`, `export_relax` | active | tblite or xtb CLI |
| [`py/interfaces/gpaw.py`](../py/interfaces/gpaw.py) — `run_relax`, `export_relax` | active | |
| [`py/interfaces/mmff.py`](../py/interfaces/mmff.py) — `run_relax` | active | RDKit MMFF94; local-only |
| [`examples/hbond/relax_dimer.py`](../examples/hbond/relax_dimer.py) | active | xTB / DFTB+ dimer relax CLI |
| [`examples/pySCF/relax_small_mols.py`](../examples/pySCF/relax_small_mols.py) | active | H₂O, NH₃, HCOOH, CH₂O |
| [`examples/AgTip_CarboxAnhydride_bonds/`](../examples/AgTip_CarboxAnhydride_bonds/README.md) | active | `batch_relax_dftb.py`, `batch_relax_xtb.py`, `run_cluster_relax.py` |
| [`examples/phonons/relax_dftb.py`](../examples/phonons/relax_dftb.py) | active | Equilibrate lattice before phonon supercell |
| [`examples/tSiNCs/vib_utils.py`](../examples/tSiNCs/vib_utils.py) — `optimize_and_cache` | active | Per-method optimization with cache |

## Parity Status

| Pair | Metric | Tolerance | Test / reference |
|------|--------|-----------|------------------|
| H₂O geometry (xTB vs PySCF) | O–H, ∠HOH | ~0.02 Å, ~2° | `examples/pySCF/relax_small_mols.py` vs `examples/hbond/relax_dimer.py` |

## Open Issues

- PySCF constraints not implemented (see GeomConstraint topic).
- No automated cross-backend parity test for relaxation — manual comparison only.

---

```yaml
---
type: TopicalAudit
title: Coordinate scans (rigid & relaxed)
tags: [scan, rigid, relaxed, adsorption, dissociation, grid]
---
```

## Summary

Rigid scan: pre-compute geometry frames, evaluate energy per frame (parallelizable, no QM coupling). Relaxed scan: step-by-step with constraints, using `step_callback` for geometry ops. Two grid generators: `make_scan_grid` (adsorption — fine near contact) and `make_scan_grid_geometric` (dissociation — fine near r_eq, geometric coarsening).

## Implementations

| Location | Status | Notes |
|----------|--------|-------|
| [`py/tasks/scan.py`](../py/tasks/scan.py) — `rigid_scan`, `relaxed_scan` | active | Local + export modes |
| [`py/tasks/scan.py`](../py/tasks/scan.py) — `make_scan_grid` | active | Adsorption grid: fine near contact, coarse far, +r_inf reference point |
| [`py/tasks/scan.py`](../py/tasks/scan.py) — `make_scan_grid_geometric` | active | Dissociation grid: 0.1 Å near r_eq, geometric bands, 1 Å / 5 Å to r_max |
| [`py/tasks/scan.py`](../py/tasks/scan.py) — `make_rigid_shift_frames` | active | Translate a fragment to a series of distances |
| [`py/tasks/base.py`](../py/tasks/base.py) — `ScanResult` | active | `coords`, `energies`, `geoms`, `comments`, `output_files` |
| [`examples/hbond/scan_dimer.py`](../examples/hbond/scan_dimer.py) | active | Rigid O···O scan from relaxed dimer |
| [`examples/AgTip_CarboxAnhydride_bonds/scan_adsorption.py`](../examples/AgTip_CarboxAnhydride_bonds/scan_adsorption.py) | active | E_int scan on M₄ cluster |
| [`examples/AgTip_CarboxAnhydride_bonds/scan_surface_adsorption.py`](../examples/AgTip_CarboxAnhydride_bonds/scan_surface_adsorption.py) | active | E_int scan on M(111)+adatom |
| [`examples/fukui/scan_ch2o_adatom.py`](../examples/fukui/scan_ch2o_adatom.py) | active | Molecule-to-surface distance scan XYZ movies |
| [`examples/fukui/gpaw_fukui_cluster/generate_CO_scan_jobs.py`](../examples/fukui/gpaw_fukui_cluster/generate_CO_scan_jobs.py) | active | CO rigid scan over symmetry-inequivalent atoms (GPAW + PySCF) |
| [`examples/dftb/dftb_scan.py`](../examples/dftb/dftb_scan.py) | active | Legacy `FFfit.linearScan` + DFTB+ |
| [`examples/tPsi4resp/scan_2d.py`](../examples/tPsi4resp/scan_2d.py) | active | 2D potential scan (two coordinates) |

## Parity Status

| Pair | Metric | Tolerance | Test / reference |
|------|--------|-----------|------------------|
| H₂O dimer rigid scan | E_bind min position/value | see Water dimer topic | `examples/hbond/` |

## Open Issues

- Relaxed scan not exercised by any example end-to-end (only rigid scans have CLIs).
- 2D scan (`tPsi4resp/scan_2d.py`) predates `py.tasks.scan` — not unified.

---

```yaml
---
type: TopicalAudit
title: Water dimer (H-bond)
tags: [noncovalent, hbond, xtb, dftb]
---
```

## Summary

Oriented H₂O (and general O/N host) dimers via e-pair dummy atoms, backend-agnostic relax and rigid host–host distance scans. Geometry construction lives in `geom_engine.build_hbond_dimer`; scan grids in `make_scan_grid_geometric`; thin CLIs under `examples/hbond/`.

## Implementations

| Location | Status | Notes |
|----------|--------|-------|
| [`py/geom_engine.py`](../py/geom_engine.py) — `build_hbond_dimer`, `strip_epairs` | active | Acceptor lp along `+axis`; donor O–H along `−axis`; E stripped per monomer |
| [`py/tasks/scan.py`](../py/tasks/scan.py) — `make_scan_grid_geometric` | active | Fine 0.1 Å near r_eq; geometric bands; 1 Å / 5 Å steps to r_max |
| [`examples/hbond/`](../examples/hbond/README.md) | active | `relax_dimer.py`, `scan_dimer.py` — xTB, DFTB+ |
| [`examples/pySCF/`](../examples/pySCF/README.md) | active | Legacy PySCF H-bond scans (separate workflow) |
| [`examples/tPsi4resp/`](../examples/tPsi4resp/README.md) | active | Psi4 RESP + scans |

## Parity Status

| Pair | Metric | Tolerance | Test / reference |
|------|--------|-----------|------------------|
| GFN2-xTB H₂O dimer | O···O at E_bind min | ~2.8–2.9 Å | `examples/hbond/` manual run |
| GFN2-xTB H₂O dimer | E_bind min | ~−0.15 to −0.25 eV | vs [`noncovalent_interactions.md`](AGENTS/protocols/domain/noncovalent_interactions.md) (~−5 kcal/mol) |
| DFTB+ SCC (no D3) | E_bind min | order-of-magnitude only | Dispersion missing without s-dftd3 build |

## Open Issues

- DFTB+ default `D3` dispersion requires binary compiled with `WITH_SDFTD3=ON`; current fork build may need `--method-dftb none`.
- Homodimer O index detection in library snippets assumes first half / second half layout; `scan_dimer._dimer_indices` is the robust path for general dimers.
- Parallel PySCF/Psi4 scan examples predate `build_hbond_dimer` — not unified yet.

---

```yaml
---
type: TopicalAudit
title: Interaction energy (E_int)
tags: [interaction_energy, fragment, binding, adsorption]
---
```

## Summary

Fragment-based interaction energy: `E_int = E_whole − E_frag1 − E_frag2`. Optional per-fragment relaxation. Validates that fragments are disjoint and cover all atoms. Supports local + export modes.

## Implementations

| Location | Status | Notes |
|----------|--------|-------|
| [`py/tasks/interaction_energy.py`](../py/tasks/interaction_energy.py) — `interaction_energy()` | active | Fragment validation, optional relax of whole/fragments, local + export |
| [`py/tasks/base.py`](../py/tasks/base.py) — `InteractionEnergyResult` | active | `E_int`, `E_whole`, `E_frag1`, `E_frag2`, fragment geoms + indices |
| [`examples/AgTip_CarboxAnhydride_bonds/scan_adsorption.py`](../examples/AgTip_CarboxAnhydride_bonds/scan_adsorption.py) | active | E_int scan on M₄ cluster (xTB vs DFTB+) |
| [`examples/fukui/gpaw_fukui_cluster/generate_CO_scan_jobs.py`](../examples/fukui/gpaw_fukui_cluster/generate_CO_scan_jobs.py) | active | CO scan: E_int = E_total − E_mol − E_CO |

## Parity Status

| Pair | Metric | Tolerance | Test / reference |
|------|--------|-----------|------------------|
| — | — | — | No automated parity test yet |

## Open Issues

- No thin CLI wrapper for `interaction_energy()` — examples compute E_int inline.
- Counterpoise (BSSE) correction not implemented.

---

```yaml
---
type: TopicalAudit
title: Molecular vibrations (gas-phase Hessians)
tags: [vibrations, hessian, frequencies, modes, pyscf, dftb, mmff, gpaw, cp2k, psi4]
---
```

## Summary

Harmonic vibrational frequencies and normal modes. Library task `vibrations()` dispatches to backends; the `tSiNCs/` example folder has a full multi-backend pipeline with consolidated `.npy` caching, mode matching across methods, and MMFF force-constant fitting.

## Implementations

| Location | Status | Notes |
|----------|--------|-------|
| [`py/tasks/vibrations.py`](../py/tasks/vibrations.py) — `vibrations()` | active | Local + export modes |
| [`py/tasks/base.py`](../py/tasks/base.py) — `VibResult` | active | `frequencies`, `modes`, `masses`, `ir_intensities`, `raman_activities` |
| [`py/interfaces/pyscf.py`](../py/interfaces/pyscf.py) — `run_vibrations` | active | Analytical Hessian |
| [`py/interfaces/dftbplus.py`](../py/interfaces/dftbplus.py) — `run_vibrations`, `export_vibrations` | active | |
| [`py/interfaces/xtb.py`](../py/interfaces/xtb.py) — `run_vibrations` | active | |
| [`py/interfaces/gpaw.py`](../py/interfaces/gpaw.py) — `run_vibrations` | active | |
| [`py/interfaces/mmff.py`](../py/interfaces/mmff.py) — `run_vibrations` | active | RDKit MMFF94 |
| [`examples/tSiNCs/vib_spectra.py`](../examples/tSiNCs/vib_spectra.py) | active | Unified CLI: `run`, `plot`, `match`, `export`, `bundle`, `migrate`, `list` |
| [`examples/tSiNCs/vib_utils.py`](../examples/tSiNCs/vib_utils.py) | active | Per-backend calculators (PySCF, DFTB+, MMFF, GPAW, CP2K, Psi4), Hessian extraction, `optimize_and_cache` |
| [`examples/tSiNCs/vib_store.py`](../examples/tSiNCs/vib_store.py) | active | Hierarchical cache `workdir/<mol>/<method>/` |
| [`examples/tSiNCs/vib_match.py`](../examples/tSiNCs/vib_match.py) | active | Mode assignment via mass-weighted eigenvector projection |
| [`examples/tSiNCs/vib_export.py`](../examples/tSiNCs/vib_export.py) | active | Backfill `modes.npy`; bundle export for FF fitting |
| [`examples/tSiNCs/vib_plot.py`](../examples/tSiNCs/vib_plot.py) | active | Stick/Gaussian overlay plotting |
| [`examples/tSiNCs/fit_mmff_ch4.py`](../examples/tSiNCs/fit_mmff_ch4.py), `fit_mmff_c2h6.py` | active | Scale MMFF force constants to match reference modes |
| [`examples/tSiNCs/analyze_*_modes.py`](../examples/tSiNCs/README.md) | active | Mode assignment tables (CH₄, C₂H₆, adamantane) |
| [`examples/dftb/example_hessian.py`](../examples/dftb/example_hessian.py) | active | DFTB+ Hessian readout sanity check |

## Parity Status

| Pair | Metric | Tolerance | Test / reference |
|------|--------|-----------|------------------|
| PySCF vs DFTB+ frequencies (CH₄) | RMS wavenumber | ~50 cm⁻¹ | `examples/tSiNCs/` manual |
| MMFF vs PySCF (CH₄) after fitting | RMS wavenumber | ~20 cm⁻¹ | `fit_mmff_ch4.py` |

## Open Issues

- `vib_spectra.py` pipeline is in examples, not in `py/tasks/` — not yet unified with the library `vibrations()` task.
- CP2K and Psi4 vibrational backends in `vib_utils.py` are not wrapped as `CalculationBackend` subclasses.

---

```yaml
---
type: TopicalAudit
title: Bulk phonon dispersion
tags: [phonons, periodic, lammps, dftb, mmff, alamode, phonopy, bloch]
---
```

## Summary

Periodic phonon band structure from force constants. Modular pipeline (`phonon_utils.py` + `phonon_backends.py` + `run_phonon.py`) with hash-based force-constant caching, pluggable backends (DFTB+, LAMMPS, MMFF), auto/manual q-paths, and multi-method comparison plots. Legacy ALAMODE + phonopy workflows preserved.

## Implementations

| Location | Status | Notes |
|----------|--------|-------|
| [`examples/phonons/phonon_utils.py`](../examples/phonons/phonon_utils.py) — `PhononCalculator` | active | Force-constant caching by structure hash; q-path handling (`QPath`); band solving |
| [`examples/phonons/phonon_backends.py`](../examples/phonons/phonon_backends.py) | active | `DFTBBackend`, `LAMMPSBackend`, `MMFFBackend`; `make_backend()` factory |
| [`examples/phonons/run_phonon.py`](../examples/phonons/run_phonon.py) | active | CLI: `--method`, `--supercell`, `--q-path-file`/`--q-path-auto` |
| [`examples/phonons/plot_phonon_comparison.py`](../examples/phonons/plot_phonon_comparison.py) | active | Overlay `.npz` band results with q-path validation |
| [`examples/phonons/plot_bz_paths_3d.py`](../examples/phonons/plot_bz_paths_3d.py) | active | 3D Brillouin-zone path visualization |
| [`examples/phonons/export_phonon_html.py`](../examples/phonons/export_phonon_html.py) | active | Interactive HTML band viewer |
| [`examples/phonons/export_phonon_bands_json.py`](../examples/phonons/export_phonon_bands_json.py) | active | JSON export for web viewer |
| [`examples/phonons/fit_mmff_phonon.py`](../examples/phonons/fit_mmff_phonon.py), `grid_fit_mmff_phonon.py` | active | Scale MMFF stiffness to match reference phonons |
| [`examples/phonons/relax_dftb.py`](../examples/phonons/relax_dftb.py) | active | Equilibrate lattice before supercell build |
| [`examples/phonons/test_diamond_phonon_bands.py`](../examples/phonons/test_diamond_phonon_bands.py) | active | Standalone diamond bands via pyBall MMFF Bloch sum |
| [`examples/phonons/download_phonon_refs.py`](../examples/phonons/download_phonon_refs.py) | active | Fetch reference bands (Materials Project, phonondb, Mendeley) |
| [`examples/phonons/setup_alamode_phonon.py`](../examples/phonons/setup_alamode_phonon.py), `run_alamode_phonon.py` | legacy | ALAMODE + LAMMPS displacement workflow |
| [`examples/phonons/setup_dftb_phonon.py`](../examples/phonons/setup_dftb_phonon.py), `run_phonopy_phonon.py` | legacy | DFTB+ + phonopy band workflow |
| [`py/interfaces/dftbplus.py`](../py/interfaces/dftbplus.py) — `run_phonons` (base) | active | Declared in `CalculationBackend`; DFTB+ via phonopy |
| [`py/interfaces/gpaw.py`](../py/interfaces/gpaw.py) — `run_phonons` (base) | active | Declared in `CalculationBackend` |

## Parity Status

| Pair | Metric | Tolerance | Test / reference |
|------|--------|-----------|------------------|
| Diamond Tersoff vs MP DFT | band RMS | ~5 THz | `plot_phonon_comparison.py` vs `mp_diamond_phonon_bands.dat` |
| Si SW vs experimental | INS points RMS | ~2 THz | `plot_phonon_benchmark.py` vs `experimental_phonon_data.json` |
| Band solver parity (phonopy vs phi_blocks) | eigenvalues | 0.01 THz | `check_band_solver_parity()` in `phonon_utils.py` |

## Open Issues

- Phonon pipeline lives in `examples/phonons/`, not in `py/tasks/` — not unified with library `PhononResult`.
- LAMMPS and MMFF phonon backends are not `CalculationBackend` subclasses.
- `experimental_phonon_data.json` contains approximate INS values — not publication-quality.

---

```yaml
---
type: TopicalAudit
title: Fukui functions
tags: [fukui, density, electrophilic, nucleophilic, pyscf, gpaw, metals]
---
```

## Summary

Fukui functions f⁺, f⁻, f⁰ from electron-density differences: f⁺ = ρ(N+1) − ρ(N), f⁻ = ρ(N) − ρ(N−1), f⁰ = ½(f⁺ + f⁻). Computed at fixed geometry for three charge states (N, N±1). GPAW (plane-wave, periodic) and PySCF (Gaussian, isolated) backends. Cluster job baking via `bake_jobs.bake_fukui_jobs`. Cross-method and cluster-vs-surface comparison plots.

## Implementations

| Location | Status | Notes |
|----------|--------|-------|
| [`py/tasks/base.py`](../py/tasks/base.py) — `FukuiResult` | active | `f_plus`, `f_minus`, `f_zero` grids + condensed (Mulliken) + grid metadata |
| [`py/interfaces/_base.py`](../py/interfaces/_base.py) — `run_fukui` (abstract) | active | Declared in `CalculationBackend` |
| [`examples/fukui/fukui_backend.py`](../examples/fukui/fukui_backend.py) | active | Shared `read_cube`, `write_cube`, `run_fukui_for_molecule()`, `compute_fukui_mulliken()` |
| [`examples/fukui/run_fukui.py`](../examples/fukui/run_fukui.py) | active | PySCF Fukui CLI |
| [`examples/fukui/run_gpaw_fukui_mol.py`](../examples/fukui/run_gpaw_fukui_mol.py) | active | GPAW PBE for isolated molecules |
| [`examples/fukui/run_ag_fukui.py`](../examples/fukui/run_ag_fukui.py) | active | PySCF for metal clusters (Ag₄, Ag₇, Au₄, Cu₄) |
| [`examples/fukui/run_ag111_adatom.py`](../examples/fukui/run_ag111_adatom.py) | active | PySCF on Ag(111)+adatom |
| [`examples/fukui/run_ag111_adatom_gpaw.py`](../examples/fukui/run_ag111_adatom_gpaw.py) | active | GPAW periodic M(111)+adatom |
| [`examples/fukui/make_fukui_cubes.py`](../examples/fukui/make_fukui_cubes.py), `compute_fukui_grids.py` | active | Subtract ρ cubes → f grids |
| [`examples/fukui/plot_fukui_slices.py`](../examples/fukui/plot_fukui_slices.py) (+ `_metal`, `_gpaw`) | active | 2D slice panels |
| [`examples/fukui/compare_ag4_basis.py`](../examples/fukui/compare_ag4_basis.py) | active | def2-SVP vs LANL2DZ |
| [`examples/fukui/compare_metal_fukui.py`](../examples/fukui/compare_metal_fukui.py) | active | |f|_max across Ag/Au/Cu(111)+adatom |
| [`examples/fukui/compare_cluster_surface_fukui.py`](../examples/fukui/compare_cluster_surface_fukui.py) | active | M₄ cluster vs M(111)+adatom ratio |
| [`examples/fukui/pyscf_fukui_cluster/generate_jobs.py`](../examples/fukui/pyscf_fukui_cluster/generate_jobs.py) | active | Baked PySCF N/N±1 scripts (uses `bake_jobs` + ChemBook) |
| [`examples/fukui/gpaw_fukui_cluster/generate_jobs.py`](../examples/fukui/gpaw_fukui_cluster/generate_jobs.py) | active | Baked GPAW N/N±1 scripts (uses `bake_jobs` + ChemBook) |
| [`examples/fukui/pyscf_relax_hbonds/generate_jobs.py`](../examples/fukui/pyscf_relax_hbonds/generate_jobs.py) | active | Baked PySCF relax jobs for H-bond dimons (uses `bake_jobs` + ChemBook) |
| [`py/tasks/bake_jobs.py`](../py/tasks/bake_jobs.py) — `bake_fukui_jobs` | active | Generic Fukui job baker: XYZ ingest, charge-state loops, PBS scripts |

## Parity Status

| Pair | Metric | Tolerance | Test / reference |
|------|--------|-----------|------------------|
| sum f⁺ / sum f⁻ | ratio ≈ 1.0 | <5% deviation | Sanity check in post-processing (GPAW + PySCF) |
| GPAW vs PySCF f⁺ shape | qualitative | visual | `compare_*` plots |

## Open Issues

- `run_fukui` not implemented on `PySCFBackend` / `GPAWBackend` as a `CalculationBackend` method — Fukui logic lives in `examples/fukui/fukui_backend.py` instead.
- Diffuse functions (def2-SVPD) recommended for anions but not default.
- No automated numerical parity test for Fukui values across backends.

---

```yaml
---
type: TopicalAudit
title: Metal surface × molecule interaction
tags: [metal, surface, adsorption, fcc111, adatom, coordination]
---
```

## Summary

Systematic study of coordination bond strength between small molecules and FCC(111) metal surfaces, comparing bare terraces against adatom sites. The central observable is `ΔΔE_undercoord = E_ads^adatom − E_ads^bare` — how much stronger does a molecule bind to an undercoordinated adatom vs. a flat terrace? Geometry construction lives in `py/system_specific/MetalTips.py`; the generation CLI and ChemBook-protocol output tree live in `examples/MetalTip_Molecule_interaction/`. Design spec: [`MetalTip_Molecule_Interaction_Study_Spec.md`](MetalTip_Molecule_Interaction_Study_Spec.md).

## Implementations

| Location | Status | Notes |
|----------|--------|-------|
| [`py/system_specific/MetalTips.py`](../py/system_specific/MetalTips.py) — `build_fcc111_adatom` | active | Single-adatom FCC(111) slab; 16 metals; separate FCC/BCC lattice constant tables |
| [`py/system_specific/MetalTips.py`](../py/system_specific/MetalTips.py) — `build_fcc111_multi_adatom` | active | Multi-adatom configs: dimer (2, NN), trimer (3, equilateral triangle), row (3, line); fractional shifts of supercell lattice vectors |
| [`py/system_specific/MetalTips.py`](../py/system_specific/MetalTips.py) — `layer_indices`, `bottom_layer_indices`, `top_layer_indices` | active | Z-grouped layer indexing for frozen-atom selection |
| [`py/interfaces/gpaw.py`](../py/interfaces/gpaw.py) — `GPAWBackend(dipole='z')` | active | Dipole correction via `DipoleCorrection` + `PoissonSolver` wrapper (spec §5.1); export scripts include dipole setup code |
| [`py/tasks/metal_tip.py`](../py/tasks/metal_tip.py) — `relax_metal_system` | active | Core relaxation function: loads slab, freezes bottom layers, runs GPAW with dipole correction, verifies frozen-atom displacement, writes ChemBook `meta.json` |
| [`py/tasks/metal_tip.py`](../py/tasks/metal_tip.py) — `build_relax_backend` | active | Factory for GPAWBackend with dipole correction defaults (spec §5.1, §5.8) |
| [`py/tasks/metal_tip.py`](../py/tasks/metal_tip.py) — `load_slab_from_job` | active | Load geometry + metadata from ChemBook job directory (`input/CONTCAR` + `meta.json`) |
| [`examples/MetalTip_Molecule_interaction/generate_metal_geometries.py`](../examples/MetalTip_Molecule_interaction/generate_metal_geometries.py) | active | Phase 1 CLI: 41 geometries (16 metals × {bare, adatom} + Cu/Ag/Au × {dimer, trimer, row}); ChemBook protocol with `meta.json`/`README.md` per node, `input/CONTCAR` + `input/start.xyz`, preview plots as `<variant>.png` |
| [`examples/MetalTip_Molecule_interaction/benchmark_cu_relax.py`](../examples/MetalTip_Molecule_interaction/benchmark_cu_relax.py) | active | Benchmark script (spec §11.1): Cu bare + adatom, gamma-point, PBE, dipole correction; verifies frozen atoms + adatom position; supports `--mode export` |
| [`examples/fukui/`](../examples/fukui/README.md) | active | Fukui functions on metal clusters and M(111)+adatom slabs (preceding work) |
| [`examples/AgTip_CarboxAnhydride_bonds/`](../examples/AgTip_CarboxAnhydride_bonds/README.md) | active | Ag tip + anhydride adsorption (preceding work, M₄ cluster model) |

## Parity Status

| Pair | Metric | Tolerance | Test / reference |
|------|--------|-----------|------------------|
| FCC(111) adatom NN distance | a/√2 | exact | Verified: Cu 2.556 Å = 3.615/√2 |
| Trimer equilateral | all sides = a/√2 | exact | Verified: Cu all 3 distances = 2.556 Å |
| Slab vacuum | vac_below=5 Å, vac_above=10 Å | exact | Dipole correction zone below, molecule room above |

## Open Issues

- FCC lattice constants for hypothetical FCC phases (Ti, V, Cr, Mn, Fe, Co, Zn, Mo, W) are volume-preserving estimates — Phase 0 bulk EOS will self-consistently determine them (spec §3.2).
- Multi-adatom configs (dimer/trimer/row) generated only for Cu, Ag, Au — other metals bare+adatom only.
- Molecule placement and interaction energy calculations not yet implemented (Phase 2+).
- **GPAW NumPy 2.x incompatibility**: GPAW 25.7.0 compiled against NumPy 1.x but system has NumPy 2.2.6 — local execution blocked until environment fixed (downgrade numpy<2 or install GPAW in conda `psi4env` which has NumPy 1.24.3).
- Relaxation infrastructure implemented but not yet benchmarked — `benchmark_cu_relax.py` export mode verified; local mode pending GPAW environment fix.

---

```yaml
---
type: TopicalAudit
title: DFTB+ in-process SCF & GPU density/STM projection
tags: [dftb, ctypes, scf, density, stm, ldos, opencl, gpu, sto]
---
```

## Summary

Low-level DFTB+ layer (below the subprocess task backend). `DFTBcore` wraps `libdftbcore.so` via ctypes for in-process SCF and matrix export (H, S, DM, eigenvectors). `Grid_dftb` projects density matrices and MOs onto 3D grids via OpenCL (`LCAO_grid.cl`, `LCAO_STM.cl`) for density visualization and STM/LDOS imaging. Same SK files and fork as the subprocess backend.

## Implementations

| Location | Status | Notes |
|----------|--------|-------|
| [`py/dftb/DFTBcore.py`](../py/dftb/DFTBcore.py) | active | ctypes to `libdftbcore.so`: `init`, `run_scf`, `get_dm_dense`, `get_eigvecs_dense`, `enable_matrix_collection` |
| [`py/dftb/DFTBplusParser.py`](../py/dftb/DFTBplusParser.py) | active | Parse `wfc.*.hsd` STO basis for grid projection |
| [`py/dftb/Grid_dftb.py`](../py/dftb/Grid_dftb.py) — `GridProjector` | active | OpenCL density/MO/STM projection; `load_basis_sto`, `project_density`, `project_orbitals`, `setup_gridprojector_from_dftb` |
| [`py/dftb/basis_optimizer.py`](../py/dftb/basis_optimizer.py) | active | Fit STO tails to reference density profiles |
| [`py/dftb/kernels/`](../py/dftb/README.md) | active | `LCAO_grid.cl`, `LCAO_STM.cl` (ported from SPAMMM) |
| [`py/ocl/OpenCLBase.py`](../py/ocl/OpenCLBase.py) | active | PyOpenCL utility base (context/queue/kernel management) |
| [`py/ocl/clUtils.py`](../py/ocl/clUtils.py) | active | OpenCL helper utilities |
| [`examples/dftb/example_dftb_lib.py`](../examples/dftb/example_dftb_lib.py) | active | Minimal `DFTBcore` usage demo |
| [`examples/dftb/example_orbitals.py`](../examples/dftb/example_orbitals.py) | active | Eigenvectors → waveplot cubes → `plotUtils.plot_cube_slice` |
| [`examples/dftb/compare_density_multizeta.py`](../examples/dftb/compare_density_multizeta.py) | active | Density across SK/zeta variants |
| [`examples/dftb/compare_waveplot_lib.py`](../examples/dftb/compare_waveplot_lib.py) | active | waveplot vs in-process density parity |
| [`examples/dftb/test_dense_projection.py`](../examples/dftb/test_dense_projection.py) | active | Dense-basis projection onto DFTB grid |
| [`examples/dftb/test_3d_grid_density.py`](../examples/dftb/test_3d_grid_density.py) | active | 3D grid density sampling validation |

## Parity Status

| Pair | Metric | Tolerance | Test / reference |
|------|--------|-----------|------------------|
| In-process DM vs subprocess `eigenvec.bin` | matrix elements | exact | `DFTBcore` design goal — export without `eigenvec.bin` |
| waveplot vs `Grid_dftb` density | grid values | qualitative | `compare_waveplot_lib.py` |

## Open Issues

- Legacy examples import `pyBall.DFTB.*` (FireCore); new code should use `py.dftb`.
- `basis_optimizer.py` fitting not integrated into the main pipeline.
- GPU STM kernel (`LCAO_STM.cl`) not exercised by a recent example.

---

```yaml
---
type: TopicalAudit
title: QC backend abstraction (CalculationBackend)
tags: [backend, abstraction, capabilities, dispatch]
---
```

## Summary

Abstract base class `CalculationBackend` with declared `capabilities` set and `run_*` / `export_*` methods. Tasks call `backend.check(task)` before dispatch. Six concrete backends: DFTB+, PySCF, Psi4, xTB, GPAW, MMFF94. Method/basis parameter semantics are backend-specific (see ARCHITECTURE.md).

## Implementations

| Location | Status | Capabilities |
|----------|--------|--------------|
| [`py/interfaces/_base.py`](../py/interfaces/_base.py) — `CalculationBackend` | active | ABC: `run_energy`, `run_relax`, `run_vibrations`, `run_phonons`, `run_density`, `run_esp`, `run_fukui`, `run_resp`; `export_energy`, `export_relax`, `export_vibrations`, `export_scan_frames` |
| [`py/interfaces/dftbplus.py`](../py/interfaces/dftbplus.py) — `DFTBPlusBackend` | active | energy, relax, vibrations, phonons |
| [`py/interfaces/pyscf.py`](../py/interfaces/pyscf.py) — `PySCFBackend` | active | energy, relax, vibrations, density, esp, fukui |
| [`py/interfaces/psi4.py`](../py/interfaces/psi4.py) — `Psi4Backend` | active | energy, relax, resp, esp; `export_movie` |
| [`py/interfaces/xtb.py`](../py/interfaces/xtb.py) — `XTBBBackend` | active | energy, relax, vibrations; tblite or xtb CLI |
| [`py/interfaces/gpaw.py`](../py/interfaces/gpaw.py) — `GPAWBackend` | active | energy, relax, vibrations, phonons, density, esp |
| [`py/interfaces/mmff.py`](../py/interfaces/mmff.py) — `MMFFBackend` | active | energy, relax, vibrations (local-only) |

## Parity Status

| Pair | Metric | Tolerance | Test / reference |
|------|--------|-----------|------------------|
| Cross-backend single-point energy (same geometry) | E_tot | backend-specific | No automated test — manual via `run_energy` |

## Open Issues

- `run_density`, `run_esp`, `run_fukui`, `run_resp` declared on base but only partially implemented on backends.
- LAMMPS, MMFF-phonon, CP2K, Psi4-vib backends in `examples/` are NOT `CalculationBackend` subclasses.
- No automated capability-matrix test.

---

```yaml
---
type: TopicalAudit
title: Cluster job baking & ChemBook metadata
tags: [cluster, baking, pbs, chembook, provenance, metadata]
---
```

## Summary

Generate self-contained cluster job scripts from templates, with ChemBook metadata baked in so each job writes its own `chembook.json` at runtime. The baker loops charge states (Fukui) or scan frames, calls a user-supplied run-script callback, and emits PBS submission files. ChemBook is the repo-wide metadata protocol: every simulation directory is a "node" with `chembook.json` (provenance, system, method, status).

## Implementations

| Location | Status | Notes |
|----------|--------|-------|
| [`py/tasks/bake_jobs.py`](../py/tasks/bake_jobs.py) — `bake_fukui_jobs` | active | Generic Fukui baker: XYZ ingest, charge loops, PBS scripts, backend-specific callbacks |
| [`py/tasks/bake_jobs.py`](../py/tasks/bake_jobs.py) — `bake_pbs` | active | PBS script writer from `ResourceSpec` + commands |
| [`py/tasks/bake_jobs.py`](../py/tasks/bake_jobs.py) — `bake_chembook_init_code`, `bake_chembook_done_code` | active | Emit Python snippets templated via `@@CHEMBOOK_INIT@@` / `@@CHEMBOOK_DONE@@` |
| [`py/chembook/schema.py`](../py/chembook/schema.py) | active | `chembook.job.v0` schema; `validate()`, `create_skeleton()`, compulsory fields |
| [`py/chembook/core.py`](../py/chembook/core.py) | active | `generate_id` (12-hex collision-checked), `resolve_true_path` (symlink-aware), `read_node`/`write_node`/`walk_nodes`/`find_by_id`, `run_command_and_record` |
| [`py/chembook/cli.py`](../py/chembook/cli.py) | active | `python -m py.chembook {init,run,validate,scan}` |
| [`examples/fukui/pyscf_fukui_cluster/generate_jobs.py`](../examples/fukui/pyscf_fukui_cluster/generate_jobs.py) | active | Bakes PySCF Fukui scripts + ChemBook |
| [`examples/fukui/gpaw_fukui_cluster/generate_jobs.py`](../examples/fukui/gpaw_fukui_cluster/generate_jobs.py) | active | Bakes GPAW Fukui scripts + ChemBook |
| [`examples/fukui/pyscf_relax_hbonds/generate_jobs.py`](../examples/fukui/pyscf_relax_hbonds/generate_jobs.py) | active | Bakes PySCF relax jobs + ChemBook |
| [`examples/MetalTip_Molecule_interaction/generate_metal_geometries.py`](../examples/MetalTip_Molecule_interaction/generate_metal_geometries.py) | active | Writes `chembook.json` directly (mode C — no QC run) |
| [`doc/AGENTS/skills/chembook-jobs/SKILL.md`](AGENTS/skills/chembook-jobs/SKILL.md) | active | AI guideline: 3 application modes, schema, procedure |
| [`doc/ChemBook.chat.md`](ChemBook.chat.md) | reference | Full design brainstorm (3896 lines) |

## Parity Status

| Pair | Metric | Tolerance | Test / reference |
|------|--------|-----------|------------------|
| `chembook validate` on generated nodes | 0 errors | exact | Run after any campaign |

## Open Issues

- ChemBook CLI commands not yet implemented: `extract`, `sync`, `find`, `convert`, `plot`, `prune`, `migrate`, `index`.
- `bake_jobs` is Fukui-specific (`bake_fukui_jobs`); no generic `bake_jobs` for relax/scan.
- `generate_metal_geometries.py` writes a parallel `meta.json` alongside `chembook.json` — schema unification pending.

---

```yaml
---
type: TopicalAudit
title: HPC cluster plumbing (PBS / Metacentrum)
tags: [hpc, pbs, metacentrum, cluster, ssh, interactive]
---
```

## Summary

PBS job script generation, resource specs, and interactive-job environment capture for Metacentrum (Czech national HPC, OpenPBS `luna` queue). Complements the job baker with operational tooling: queue monitoring, agent SSH integration, environment setup.

## Implementations

| Location | Status | Notes |
|----------|--------|-------|
| [`py/cluster/resources.py`](../py/cluster/resources.py) — `ResourceSpec` | active | cores, nodes, RAM, walltime, GPU, queue; `walltime_str`, `mem_mb` |
| [`py/cluster/pbs.py`](../py/cluster/pbs.py) — `write_pbs_script`, `write_array_pbs` | active | From `ResourceSpec` + command list |
| [`py/cluster/interactive_job.py`](../py/cluster/interactive_job.py) | active | `parse_qstat`, `extract_node`, `extract_variables`, `write_json`/`write_shell`; `python3 -m py.cluster.interactive_job JOBID` |
| [`examples/metacentrum/metacentrum_monitor.py`](../examples/metacentrum/metacentrum_monitor.py) | active | Poll queue, detect failed jobs, recovery hooks |
| [`examples/metacentrum/setup_metacentrum_ai.sh`](../examples/metacentrum/setup_metacentrum_ai.sh) | active | Shell setup for agent SSH workflows |
| [`examples/metacentrum/ai_agent_integration_guide.md`](../examples/metacentrum/ai_agent_integration_guide.md) | active | Agent + `interactive_job` + SSH runbook |
| [`examples/metacentrum/metacentrum_pbs_skill.md`](../examples/metacentrum/metacentrum_pbs_skill.md) | active | PBS directive patterns; `#PBS -q luna` |
| [`examples/metacentrum/dft_babysitter_skill.md`](../examples/metacentrum/dft_babysitter_skill.md) | active | Long-running DFT job checklist |
| [`doc/AGENTS/skills/metacentrum/SKILL.md`](AGENTS/skills/metacentrum/SKILL.md) | active | Metacentrum submission/monitoring skill |

## Parity Status

| Pair | Metric | Tolerance | Test / reference |
|------|--------|-----------|------------------|
| — | — | — | Operational tooling; no numerical parity |

## Open Issues

- `metacentrum_monitor.py` not integrated with `chembook scan` / `validate`.
- No SLURM support (Metacentrum is OpenPBS).

---

```yaml
---
type: TopicalAudit
title: RESP charge fitting (Psi4)
tags: [resp, charges, psi4, electrostatic_potential]
---
```

## Summary

Restrained Electrostatic Potential (RESP) charge fitting via Psi4. Computes ESP on a grid, fits atom-centered charges subject to restraints. Legacy workflow with fragment jobs and 1D/2D potential scans.

## Implementations

| Location | Status | Notes |
|----------|--------|-------|
| [`py/interfaces/psi4.py`](../py/interfaces/psi4.py) — `run_resp` | active | `CalculationBackend` method |
| [`examples/tPsi4resp/psi4resp.py`](../examples/tPsi4resp/psi4resp.py) | active | Main RESP workflow driver (conda `p4env`) |
| [`examples/tPsi4resp/psi4resp_2.py`](../examples/tPsi4resp/psi4resp_2.py) | active | Variant with alternate method/basis |
| [`examples/tPsi4resp/plot_charges.py`](../examples/tPsi4resp/plot_charges.py) | active | Visualize fitted charges |
| [`examples/tPsi4resp/HBondModel.py`](../examples/tPsi4resp/HBondModel.py) | active | H-bond dimer model helpers |
| [`examples/tPsi4resp/scan_2d.py`](../examples/tPsi4resp/scan_2d.py), `scan_2d_jobs.py` | active | 2D potential scans |
| [`examples/tPsi4resp/psi4scan.py`](../examples/tPsi4resp/psi4scan.py), `psi4_scan_jobs.py` | active | 1D scans + cluster export |

## Parity Status

| Pair | Metric | Tolerance | Test / reference |
|------|--------|-----------|------------------|
| — | — | — | No automated parity test |

## Open Issues

- RESP workflow predates `py/tasks/` — not unified with library task layer.
- No thin CLI wrapper; runs via `psi4resp.py` directly.

---

```yaml
---
type: TopicalAudit
title: Molecule attachment & polymerization
tags: [attachment, polymerization, backbone, endgroup, marker-atoms]
---
```

## Summary

Orient molecular backbones and endgroups via marker atoms (`Se`/`F`), join `.mol2` sequences, polymerize repeat units. Legacy `pyBall`-based; library equivalent is `geom_engine.place_molecule_on_edge` / `generate_edge_attach_movie`.

## Implementations

| Location | Status | Notes |
|----------|--------|-------|
| [`py/geom_engine.py`](../py/geom_engine.py) — `place_molecule_on_edge`, `auto_edge_placement`, `generate_edge_attach_movie` | active | Library placement API |
| [`examples/tAttach/attach.py`](../examples/tAttach/attach.py) | legacy | Original attachment workflow |
| [`examples/tAttach/attach_new*.py`](../examples/tAttach/README.md) | legacy | Iterative refactors toward marker-atom API |
| [`examples/tAttach/join_mols.py`](../examples/tAttach/join_mols.py) | active | Merge two `.mol2` systems |
| [`examples/tAttach/polymerize.py`](../examples/tAttach/polymerize.py) | active | Repeat unit attachment |
| [`examples/tAttach/render_molecules.py`](../examples/tAttach/render_molecules.py) | active | Static geometry plots |
| [`examples/tAttach/run_editor.py`](../examples/tAttach/run_editor.py) | active | `MoleculeEditor2D` GUI loader |

## Parity Status

| Pair | Metric | Tolerance | Test / reference |
|------|--------|-----------|------------------|
| — | — | — | No automated parity test |

## Open Issues

- `tAttach/` scripts use legacy `pyBall.AtomicSystem`; library API in `geom_engine` is the modern path.
- `attach_new*.py` iterative variants not consolidated.

---

```yaml
---
type: TopicalAudit
title: Visualization & diagnostics
tags: [plotting, matplotlib, vispy, pyqt, preview, cube, trajectory]
---
```

## Summary

Shared plotting and interactive visualization. `plotUtils.py` for matplotlib diagnostics (1D scans, 2D scalar fields, cube slices, geometry previews, trajectories). `molVisApp.py` for interactive PyQt5 + Vispy molecular viewer. Per-study plotting scripts live in `examples/`.

## Implementations

| Location | Status | Notes |
|----------|--------|-------|
| [`py/plotUtils.py`](../py/plotUtils.py) | active | 1D scans, 2D scalar fields, `plot_cube_slice`, `plotGeometry`, trajectories |
| [`py/molVisApp.py`](../py/molVisApp.py) | active | PyQt5 + Vispy viewer (`python -m py.molVisApp [xyz|POSCAR]`) |
| [`examples/plot_movies.py`](../examples/plot_movies.py) | active | XY/XZ previews of XYZ movies |
| [`examples/MetalTip_Molecule_interaction/generate_metal_geometries.py`](../examples/MetalTip_Molecule_interaction/generate_metal_geometries.py) | active | Preview plots (3×3 replicated, frozen-atom highlight) |
| [`examples/phonons/plot_phonon_comparison.py`](../examples/phonons/plot_phonon_comparison.py), `plot_bz_paths_3d.py`, `export_phonon_html.py` | active | Phonon band plots + 3D BZ + HTML viewer |
| [`examples/tSiNCs/vib_plot.py`](../examples/tSiNCs/vib_plot.py), `plot_modes_arrows.py`, `plot_vib_spectra.py` | active | Vibrational stick/Gaussian spectra + mode arrows |
| [`examples/fukui/plot_fukui_slices*.py`](../examples/fukui/README.md) | active | 2D Fukui slice panels |
| [`examples/tPsi4resp/plot_scan_2d*.py`](../examples/tPsi4resp/README.md) | active | 2D scan surface plots |
| [`doc/AGENTS/skills/centralized-plotting/SKILL.md`](AGENTS/skills/centralized-plotting/SKILL.md) | active | Plotting guidelines (transpose/aspect/alignment bugs) |
| [`doc/AGENTS/skills/visual-debugging/SKILL.md`](AGENTS/skills/visual-debugging/SKILL.md) | active | Diagnostic plot / headless visual test guidelines |

## Parity Status

| Pair | Metric | Tolerance | Test / reference |
|------|--------|-----------|------------------|
| — | — | — | Visualization; no numerical parity |

## Open Issues

- Some example plotting scripts duplicate `plotUtils` logic instead of importing it (see `centralized-plotting` skill).
- `molVisApp.py` not tested headless.

---

```yaml
---
type: TopicalAudit
title: Configuration & machine-independent paths
tags: [config, paths, machine_config, environment]
---
```

## Summary

Centralized resolution of tool binaries and dataset paths from `machine_config.yaml` at repo root. No hard-coded `/home/...` paths in source. External datasets documented in `DEPEND.md`.

## Implementations

| Location | Status | Notes |
|----------|--------|-------|
| [`py/config_loader.py`](../py/config_loader.py) | active | `require_path`, `get_tool`, `dftbcore_lib`, `ensure_pyball_path` |
| `machine_config.yaml` (repo root) | active | Machine-specific `sk_dir`, `dftb_bin`, `dftb.repo`, etc. |
| [`DEPEND.md`](../DEPEND.md) | active | Documents required external datasets |
| [`doc/EVIROMENTS_AND_MACHINES/`](EVIROMENTS_AND_MACHINES) | active | Per-machine setup notes (Desktop GTX3090, Laptop GTX1650, Metacentrum) |

## Parity Status

| Pair | Metric | Tolerance | Test / reference |
|------|--------|-----------|------------------|
| — | — | — | Configuration; no numerical parity |

## Open Issues

- Legacy examples still hard-code `/home/prokop/...` paths — should migrate to `config_loader`.
- `machine_config.yaml` not in git (machine-specific) — only template documented.
