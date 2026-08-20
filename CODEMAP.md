# CompChemUtils — Code Map

> **ATTENTION LLMs**: Quick file-location index. Use this to find where things live before searching. For design rules and usage patterns see [`ARCHITECTURE.md`](ARCHITECTURE.md); for cross-topic implementation maps see [`doc/topical_audit.md`](doc/topical_audit.md); for AI task guidance see [`doc/AGENTS/skills/`](doc/AGENTS/skills/).
>
> Generated data (simulation outputs, `systems/`, `structures/*.xyz`, `jobs/`, `results/`, `plots/`) is NOT listed here — only the scripts that produce it. Large datasets live outside the repo (see `DEPEND.md`).

## Top-level layout

| Path | Purpose |
|------|---------|
| `py/` | Core Python library (geometry, tasks, backends, chembook, cluster, system builders, dftb, ocl) |
| `examples/` | Runnable workflows and study scripts — thin CLIs on top of `py/` |
| `test/`, `tests/` | Test scripts (run via `run.sh`/`make.sh` inside the test dir) |
| `doc/` | Design chats, study specs, agent skills/protocols/workflows, topical audits, machine notes |
| `data/` | Small in-repo reference data (large datasets live outside — see `DEPEND.md`) |
| `tmp/` | Scratch (gitignored) |
| `ARCHITECTURE.md` | Orthogonal three-layer design + supporting modules + usage patterns |
| `AGENTS.md` | Hard rules for AI agents (fail-loud, surgical edits, reuse, validation, chembook, …) |
| `CODEMAP.md` | This file — file/folder index |
| `doc/topical_audit.md` | Cross-implementation maps per scientific topic (parity status) |
| `machine_config.yaml` | Machine-specific tool paths and dataset locations (repo root; see `py/config_loader.py`) |

---

## `py/` — core library

### Geometry / chemistry layer (`py/`)
| File | Role |
|------|------|
| `AtomicSystem.py` | Canonical geometry container (`apos`, `enames`, `atypes`, PBC, bonds); XYZ/MOL/MOL2/GEN I/O; selections, rotations, neighbor lists, `clonePBC()`, `add_electron_pairs()` (N, O, S, P valence) |
| `geom_engine.py` | Program-agnostic constraints (`GeomConstraint`, `freeze_atoms`, `fix_distance`); adsorption placement (`place_molecule_on_edge`, `auto_edge_placement`, `generate_edge_attach_movie`); H-bond dimer assembly (`build_hbond_dimer`, `strip_epairs`); `validate_geometry()`; `make_hydride()` universal XH_n generator from bond length + angle; `_find_host_atom()` / `_mol_frame_from_epairs()` for molecule-on-surface orientation |
| `atomicUtils.py` | Low-level primitives: file loaders, bond/H-bond detection, angles/dihedrals, orientation frames, graph/cycle helpers, fragment assembly |
| `elements.py` | Periodic-table lookup (Z, radii, masses, Jmol colors, valence electrons) |
| `AtomicGraph.py` | Object-graph alternative to parallel arrays (`Atom`/`Bond`/`Ring` with stable identity; `to_arrays()` for numpy/vispy) |
| `AtomicSystem_new.py` | Experimental fork of `AtomicSystem` with verbose debug logging; not the production import path |
| `config_loader.py` | Machine-independent path/tool resolution from `machine_config.yaml` (`require_path`, `get_tool`, `dftbcore_lib`, `ensure_pyball_path`) |
| `plotUtils.py` | Shared matplotlib diagnostics (1D scans, 2D scalar fields, cube slices, `plotGeometry`, trajectories, `plot_init_final_comparison`); keep plotting out of core compute modules |
| `molVisApp.py` | Interactive PyQt5 + Vispy molecular viewer (`python -m py.molVisApp [xyz|POSCAR]`) |
| `__init__.py` | Package marker (empty) |

### Task layer (`py/tasks/`)
| File | Role |
|------|------|
| `base.py` | Result dataclasses: `RelaxResult`, `ScanResult`, `VibResult`, `FukuiResult`, `PhononResult`, `InteractionEnergyResult` |
| `relax.py` | `relax()` — geometry optimization (modes `local`/`export`) |
| `scan.py` | `rigid_scan()`, `relaxed_scan()`; distance grids (`make_scan_grid` adsorption, `make_scan_grid_geometric` H-bond dissociation); `make_rigid_shift_frames()` |
| `vibrations.py` | `vibrations()` — harmonic frequency/mode workflow |
| `interaction_energy.py` | E_int = E_whole − E_frag1 − E_frag2, optional per-fragment relaxation |
| `bake_jobs.py` | Generic Fukui cluster job baker (`bake_fukui_jobs`, `bake_pbs`); **ChemBook integration** via `bake_chembook_init_code()` / `bake_chembook_done_code()` |
| `metal_tip.py` | Metal slab relaxation workflow: `relax_metal_system()` (core function, spec §10.3), `build_relax_backend()` (GPAW + dipole correction), `load_slab_from_job()` (ChemBook geometry loader) |
| `__init__.py` | Re-exports result types, `interaction_energy`, `bake_fukui_jobs`, `relax_metal_system`, `build_relax_backend`, `load_slab_from_job` |

### Backend layer (`py/interfaces/`)
| File | Backend | Capabilities |
|------|---------|--------------|
| `_base.py` | `CalculationBackend` ABC | capability guard (`check`), default stubs |
| `dftbplus.py` | DFTB+ (subprocess) | energy, relax, vibrations, phonons |
| `pyscf.py` | PySCF (HF/DFT) | energy, relax, vibrations, density, esp, fukui |
| `psi4.py` | Psi4 | energy, relax, resp, esp |
| `xtb.py` | xTB (tblite/CLI) | energy, relax, vibrations |
| `gpaw.py` | GPAW (PW/LCAO) | energy, relax, vibrations, phonons, density, esp; **dipole correction** (`dipole='z'` param, spec §5.1) |
| `mmff.py` | MMFF94 (RDKit) | energy, relax, vibrations (local-only) |
| `__init__.py` | exports `CalculationBackend` | — |

### In-process DFTB+ + GPU (`py/dftb/`)
Low-level DFTB+ layer (below `py/interfaces/dftbplus.py`). Two execution paths: task backend (subprocess) vs in-process ctypes SCF + OpenCL grid/STM projection. Same SK files (`sk_dir`) and fork (`dftb.repo`).

| File | Role |
|------|------|
| `DFTBcore.py` | ctypes wrapper to `libdftbcore.so` (SCF, H/S/DM/eigenvectors) |
| `DFTBplusParser.py` | Parse `wfc.*.hsd` STO basis for grid projection |
| `Grid_dftb.py` | OpenCL `GridProjector` (density, MOs, STM/LDOS) |
| `basis_optimizer.py` | Fit STO tails to reference density profiles |
| `__init__.py` | Package exports |
| `kernels/` | `LCAO_grid.cl`, `LCAO_STM.cl` OpenCL kernels |
| `data/` | `wfc.mio-1-1.hsd`, `wfc.3ob-3-1.hsd` STO basis data |

### OpenCL base (`py/ocl/`)
| File | Role |
|------|------|
| `OpenCLBase.py` | PyOpenCL utility base class (context/queue/kernel management) used by `py/dftb` |
| `clUtils.py` | OpenCL helper utilities |
| `__init__.py` | Package marker |

### Cluster / HPC (`py/cluster/`)
PBS plumbing for Metacentrum — not part of the geometry/task/backend triangle.

| File | Role |
|------|------|
| `resources.py` | `ResourceSpec` dataclass (cores, nodes, RAM, walltime, GPU, queue) with PBS formatting helpers |
| `pbs.py` | `write_pbs_script`, `write_array_pbs` from `ResourceSpec` + shell command list |
| `interactive_job.py` | Parse `qstat -f JOBID`, export PBS env to `job_env.json`/`.sh` for SSH/agent use (`python3 -m py.cluster.interactive_job JOBID`) |
| `__init__.py` | Exports `ResourceSpec`, `parse_qstat`, `extract_node`, `extract_variables` |

### Domain builders (`py/system_specific/`)
ASE-dependent geometry builders — kept separate so ASE stays optional for the rest of `py/`.

| File | Role |
|------|------|
| `MetalTips.py` | FCC(111) slab + adatom builders for 16 study metals (separate FCC/BCC lattice constant tables, `build_fcc111_adatom`, `build_fcc111_multi_adatom` for dimer/trimer/row configs), `layer_indices`/`bottom_layer_indices`/`top_layer_indices` helpers, edge-pair frames, Ag₄ cluster directions, `AtomicSystem` export helpers |
| `__init__.py` | Package marker; documents ASE-dependent scope |

### Job metadata — ChemBook (`py/chembook/`)
Filesystem-based metadata protocol. A directory becomes a node by containing `chembook.json`. See `chembook-jobs` skill. Design chat: `doc/ChemBook.chat.md`.

| File | Role |
|------|------|
| `schema.py` | `SCHEMA_VERSION="chembook.job.v0"`, `COMPULSORY_FIELDS`, `validate()` → `(errors, warnings)`, `create_skeleton()` |
| `core.py` | `generate_id()` (12-hex, collision-checked), `resolve_true_path()` (symlink-aware), `read_node`/`write_node`/`walk_nodes`/`find_by_id`, `run_command_and_record()`, `get_git_commit()`, `now_iso()` |
| `cli.py` | `python -m py.chembook {init,run,validate,scan}` |
| `__main__.py` | `python -m py.chembook` entry point |
| `__init__.py` | Re-exports `validate`, `SCHEMA_VERSION`, `COMPULSORY_FIELDS`, `generate_id`, `resolve_true_path`, `read_node`, `write_node`, `walk_nodes`, `find_by_id` |

---

## `examples/` — workflows and study scripts

Thin CLIs on top of `py/`. Not imported by the library; paths/datasets often local. Many scripts predate the `py/` refactor and still import legacy `pyBall` — prefer `py.*` for new work.

### Top-level utilities
| File | Role |
|------|------|
| `add_epairs.py` | Add electron-pair (`E`) dummy atoms to N/O in XYZ via `AtomicSystem.add_electron_pairs()` |
| `replicate_xyz.py` | Tile structure in XY with `AtomicSystem.clonePBC()` |
| `plot_movies.py` | XY/XZ previews of XYZ movies via `plotUtils.plotGeometry` |
| `README.md` | Examples index with topic → path table |

### `hbond/` — H-bond dimer build + relax + scan
| File | Role |
|------|------|
| `relax_dimer.py` | `build_hbond_dimer()` + `py.tasks.relax` (xTB / DFTB+) |
| `scan_dimer.py` | Rigid acceptor-O···donor-O scan (`make_scan_grid_geometric` + `make_rigid_shift_frames` + `rigid_scan`) |
| `README.md` | Usage, outputs table, reference checks (H₂O homodimer) |

### `AgTip_CarboxAnhydride_bonds/` — metal tip + anhydride adsorption
| File | Role |
|------|------|
| `surface_workflow.py` | Unified CLI: adatom/edgepair/cluster attach movies, Psi4/GPAW QC input export |
| `generate_metal4.py` | Build M₄ tetrahedron XYZ from FCC lattice constant |
| `run_cluster_relax.py` | Relax molecule+cluster frames via `py.tasks.relax` |
| `batch_relax_dftb.py` | Batch DFTB+ relax with frozen metal atoms |
| `batch_relax_xtb.py` | Batch GFN2-xTB relax (resets metal positions post-relax) |
| `scan_adsorption.py` | Rigid E_int scan on M₄ cluster (xTB vs DFTB+) |
| `scan_surface_adsorption.py` | Same for M(111)+adatom |
| `test_dftb_export.py` | Export-only DFTB+ inputs to debug SK parameter issues |
| `*.md` | Study writeups (relaxation/scan reports) |

### `dftb/` — DFTB+ scans, orbitals, waveplot
| File | Role |
|------|------|
| `dftb.py` | Batch parallel DFTB+ relax driver (legacy `pyBall` + subprocess) |
| `dftb_scan.py` / `dftb_scan_2.py` | 1D rigid scan via `FFfit.linearScan` + DFTB+ single-points |
| `dftb_scan_getE.py` | Extract energies from completed scan directories |
| `dftb_scan_jobs.py` | Export/batch scan jobs for cluster submission |
| `dftb_jobs_frags.py` | Fragment-based DFTB+ job generation |
| `dftb_post_proc.py` / `dftb_postproc.py` | Post-process DFTB+ outputs |
| `plot_Es.py` | Plot scan energy curves |
| `example_dftb_lib.py` | Minimal `dftb_utils` usage demo |
| `example_hessian.py` | DFTB+ Hessian readout + vibrational sanity check |
| `example_orbitals.py` | DFTB+ eigenvectors → waveplot cubes → `plotUtils.plot_cube_slice` |
| `compare_density_multizeta.py` | Compare electron density across SK/zeta variants |
| `compare_waveplot_lib.py` | waveplot vs in-process density extraction parity |
| `test_python_api.py` | DFTB+ Python/ASE API smoke tests |
| `test_waveplot_dftb.py` / `test_waveplot_dftbcore.py` | waveplot integration tests |
| `test_dense_projection.py` | Dense-basis projection onto DFTB grid |
| `test_3d_grid_density.py` | 3D grid density sampling validation |
| `DFTB_docs.md` / `dftb_ASI_level3_interface.md` | Consolidated DFTB+ notes |

### `fukui/` — Fukui functions (GPAW, PySCF, metals)
| File | Role |
|------|------|
| `fukui_backend.py` | Shared `read_cube`, `write_cube`, `run_fukui_for_molecule()` helpers |
| `run_fukui.py` | PySCF Fukui CLI (`--mol`, `--basis`, `--xc`, 1D/2D plots) |
| `run_gpaw_fukui_mol.py` | GPAW PBE Fukui for isolated molecules (N/N±1) |
| `run_ag_fukui.py` | PySCF Fukui for metal clusters (Ag₄, Ag₇, Au₄, Cu₄) |
| `run_ag111_adatom.py` | PySCF Fukui on Ag(111)+adatom slab models |
| `run_ag111_adatom_gpaw.py` | GPAW periodic Fukui for M(111)+adatom |
| `run_ag_tetrahedron.py` / `run_batch_DZVP.py` | Batch cluster Fukui with alternate basis sets |
| `make_fukui_cubes.py` / `compute_fukui_grids.py` | Subtract ρ(N±1) cubes → f⁺/f⁻/f⁰ grids |
| `plot_fukui_slices.py` | Generic 2D slice panels (ρ_N, ρ_A, ρ_C, f⁺, f⁻, f⁰) |
| `plot_fukui_slices_metal.py` | M₄ tetrahedron cluster slices |
| `plot_gpaw_fukui_slices.py` | M(111)+adatom surface slices through adatom |
| `compare_ag4_basis.py` | def2-SVP vs LANL2DZ on Ag₄ |
| `compare_metal_fukui.py` | |f|_max across Ag/Au/Cu(111)+adatom |
| `compare_cluster_surface_fukui.py` | M₄ cluster vs M(111)+adatom magnitude ratio |
| `scan_ch2o_adatom.py` | Generate molecule-to-surface distance scan XYZ movies |
| `Fukui.md` / `REPORT_Fukui_Metals.md` | Theory notes and metals study summary |
| `README.md` | Fukui index + subdirectory table |

#### `fukui/gpaw_fukui_cluster/` — baked GPAW Fukui + CO scan package
| File | Role |
|------|------|
| `generate_jobs.py` | Fukui job generator: bakes standalone GPAW scripts (uses `bake_jobs` + ChemBook) |
| `generate_CO_scan_jobs.py` | CO rigid scan job generator (GPAW + PySCF via `--pyscf`) |
| `run_fukui.py` | Flexible Fukui runner (CLI args, self-contained) |
| `run_CO_scan.py` | Flexible CO scan runner (GPAW restart) |
| `plot_selected_atoms.py` | Plot molecules with symmetry-inequivalent atoms highlighted |
| `submit_all.sh` | Submit all molecules via flexible runner |
| `README.md` | Full run instructions, resource estimates, sanity checks |

#### `fukui/pyscf_fukui_cluster/` — baked PySCF Fukui package
| File | Role |
|------|------|
| `generate_jobs.py` | Job generator: bakes standalone PySCF scripts (uses `bake_jobs` + ChemBook) |
| `README.md` | Run instructions, resource estimates, PySCF vs GPAW comparison |

#### `fukui/pyscf_relax_hbonds/` — PySCF H-bond relax jobs
| File | Role |
|------|------|
| `generate_jobs.py` | Bakes PySCF relax jobs for H-bond dimers (uses `bake_jobs` + ChemBook) |

#### `fukui/structures/` — input geometries (generated by `scan_ch2o_adatom.py` etc.)
| File | Role |
|------|------|
| `README.md` | Describes input XYZ/POSCAR/CIF for metals and scan trajectories |

### `metacentrum/` — Metacentrum PBS monitoring + agent integration
| File | Role |
|------|------|
| `metacentrum_monitor.py` | Poll PBS queue, detect failed jobs, optional recovery hooks |
| `setup_metacentrum_ai.sh` | Shell setup for agent SSH workflows (modules, paths) |
| `ai_agent_integration_guide.md` | How agents use `py.cluster.interactive_job` + SSH |
| `metacentrum_pbs_skill.md` | PBS directive patterns; **always `#PBS -q luna`** for FZU |
| `dft_babysitter_skill.md` | Long-running DFT job babysitting checklist |
| `README.md` | Index |

### `MetalTip_Molecule_interaction/` — metal surface × molecule interaction study
Systematic study of coordination bond strength between small molecules and FCC(111) metal surfaces (bare vs. adatom vs. multi-adatom). Design spec: [`doc/MetalTip_Molecule_Interaction_Study_Spec.md`](../doc/MetalTip_Molecule_Interaction_Study_Spec.md).

| File | Role |
|------|------|
| `generate_metal_geometries.py` | Build FCC(111) slabs for 16 study metals: bare, single adatom (all metals), plus dimer/trimer/row multi-adatom configs (Cu, Ag, Au only). ChemBook protocol: `meta.json` + `README.md` per node, `input/CONTCAR` + `input/start.xyz`, preview plots as `<variant>.png` next to job dir. Uses Jmol colors from `py/elements.py` |
| `generate_relax_jobs.py` | Bake GPAW relax/SCF job scripts (Python runner + PBS) for Metacentrum: PW mode, FermiDirac smearing, dipole correction (`poissonsolver={'dipolelayer':'xy'}`), `FixAtoms` on bottom layers, ChemBook provenance, cube output (density/potential), `--scf-only` and `--coinage` flags. `--molecules` flag: bake molecule-on-surface jobs from `systems/<Metal>/<variant>_<molecule>_111_3x3x3/input/CONTCAR` |
| `generate_molecule_on_surface.py` | Phase 2 CLI: place molecules on relaxed Cu/Ag/Au slabs (bare + adatom). Orients molecule so electron lone pair faces target metal atom at ~2.4 Å. Uses `make_hydride()` for binary hydrides, XYZ files for HCN/CH2O/CH2NH. Reads relaxed slabs from `jobs_coinage/results_*/relaxed.xyz`. Cell z fixed to 22 Å |
| `make_hydrides.py` | Generate XYZ files for binary hydrides (H2O, H2S, NH3, PH3, CH4, SiH4) using `make_hydride()` from `geom_engine.py` |
| `benchmark_cu_relax.py` | Benchmark metal slab relaxation (spec §11.1): loads geometry from ChemBook job dir, runs GPAW PBE with dipole correction + frozen bottom layers, verifies frozen-atom displacement + adatom position. Supports `--mode local` and `--mode export` |
| `plot_init_final.py` | Thin wrapper: plot initial vs final geometry from `init_final_xyz/*.xyz` using `plotUtils.plot_init_final_comparison()` — 3 projections (XZ/YZ/XY) × 2 rows (full + top layers), red=initial, blue=final |
| `README.md` | Phase 1 summary table (41 geometries), Phase 2 molecule-on-surface (42 geometries), ChemBook directory layout, key parameters, usage |
| `systems/` | Generated geometry nodes (ChemBook protocol) — 41 slab geometries (Phase 1) + 42 molecule-on-surface geometries (Phase 2: Cu/Ag/Au × bare/adatom × 7 molecules); not listed here |

### `phonons/` — bulk phonon dispersion toolkit
| File | Role |
|------|------|
| `phonon_utils.py` | `PhononCalculator`, q-path handling, force-constant caching by structure hash |
| `phonon_backends.py` | `DFTBBackend`, `LAMMPSBackend`, `MMFFBackend` force calculators |
| `run_phonon.py` | CLI: compute bands (`--method`, `--supercell`, `--q-path-file`/`--q-path-auto`) |
| `plot_phonon_comparison.py` | Overlay multiple `.npz` band results with q-path validation |
| `plot_bz_paths_3d.py` | 3D Brillouin-zone path visualization |
| `export_phonon_html.py` | Interactive HTML band comparison viewer |
| `export_phonon_bands_json.py` | JSON export for web viewer |
| `export_phonon_bands.py` | Multi-method bands → single text file (legacy) |
| `fit_mmff_phonon.py` / `grid_fit_mmff_phonon.py` | Scale MMFF stiffness to match reference phonons |
| `relax_dftb.py` | Equilibrate lattice constant before phonon supercell build |
| `test_diamond_phonon_bands.py` | Standalone diamond bands via pyBall MMFF Bloch sum |
| `download_phonon_refs.py` | Fetch reference bands (Materials Project, phonondb, Mendeley) |
| `setup_alamode_phonon.py` / `run_alamode_phonon.py` | ALAMODE + LAMMPS displacement workflow (legacy) |
| `setup_dftb_phonon.py` / `run_phonopy_phonon.py` | DFTB+ + phonopy band workflow (legacy) |
| `plot_phonon_benchmark.py` / `plot_phonons.py` / `plot_alamode_overlay.py` | Legacy overlays |
| `phonon_config*.json` / `phonon_config.template.json` | Tool and potential paths |
| `experimental_phonon_data.json` | Approximate INS reference points (Si, diamond) |
| `*.md` | Notes (`phonons_ref`, `phonons_fitting`, `MMFF_phonon_PBC_report`, `GIT_NOTES`) |
| `README.md` | Full pipeline docs (modular + legacy), deprecation notes |

### `pySCF/` — small-molecule PySCF demos
| File | Role |
|------|------|
| `relax_small_mols.py` | Relax H₂O, NH₃, HCOOH, CH₂O via `pyscf` interface + overlay energy plots |
| `map_hbonds.py` | Linear/angular H-bond potential scans on dimers (legacy `FFfit` + PySCF) |
| `try_pyscf.py` | Minimal PySCF geometry optimization (Berny solver) sanity check |
| `README.md` | Index |

### `pyutils/` — geometry / FF debugging snippets (legacy `pyBall`)
| File | Role |
|------|------|
| `orient.py` | Center + PCA-orient an XYZ, write `*-oriented.xyz` |
| `NaCl_step.py` / `NaCl_step_.py` / `NaCl_step_2.py` | Build NaCl slab steps with ASE (iterative variants) |
| `PTCDA_NaCl.py` | Place PTCDA on NaCl slab (geometry experiment) |
| `test_sequence_placer.py` | Trial placements for molecular sequences on surfaces |
| `plotStuckAtomTrj.py` | Plot position/velocity/force for stuck-atom MD debug trajectories |
| `plotStuckAtomFF.py` | Force component differences along reaction coordinate |
| `README.md` | Index |

### `tAttach/` — molecule attachment / polymerization (legacy `pyBall`)
| File | Role |
|------|------|
| `attach.py` | Original attachment workflow: backbone + H-bond endgroups |
| `attach_new.py` / `attach_new2.py` / `attach_new3.py` | Iterative refactors toward marker-atom placement API |
| `join_mols.py` | Merge two `.mol2` systems with `addSystems()`, export combined XYZ/MOL2 |
| `polymerize.py` | Repeat unit attachment along a backbone |
| `render_molecules.py` | Static geometry plots for attached systems |
| `run_editor.py` | CLI loader for `MoleculeEditor2D` GUI |
| `README.md` | Index (library equivalent: `py/geom_engine.py`) |

### `tPsi4resp/` — Psi4 RESP + scans
| File | Role |
|------|------|
| `psi4resp.py` | Main RESP workflow driver (conda `p4env`) |
| `psi4resp_2.py` | Variant RESP run with alternate method/basis blocks |
| `psi4scan.py` | Local Psi4 scans (H₂O dimer, HCOOH dimer) via `FFfit.linearScan` |
| `psi4_scan_jobs.py` | Export Psi4 input files for scan batches |
| `psi4_scan_getE.py` | Harvest energies from completed scan jobs |
| `psi4_jobs_frags.py` | Fragment-based Psi4 job export (counterpoise-style) |
| `scan_2d.py` / `scan_2d_jobs.py` | 2D potential scan (two collective coordinates) + cluster export |
| `HBondModel.py` | H-bond dimer model geometry/energy helpers |
| `plot_charges.py` | Visualize RESP-fitted charges |
| `plot_scan_2d.py` / `plot_scan_2d_B3LYP_vs_DFTB.py` | 2D scan surface plots, method comparison |
| `README.md` | Index (modern equivalent: `py.tasks.scan` + `Psi4Backend` export) |

### `tSiNCs/` — molecular vibrational spectra pipeline
| File | Role |
|------|------|
| `vib_spectra.py` | Main entry: subcommands `run`, `plot`, `match`, `export`, `bundle`, `migrate`, `list` |
| `vib_utils.py` | Calculators, optimization, Hessian extraction, per-backend pipelines |
| `vib_store.py` | Hierarchical cache layout `workdir/<mol>/<method>/` |
| `vib_plot.py` | Stick/Gaussian overlay plotting helpers |
| `vib_match.py` | Assign modes between methods via mass-weighted eigenvector projection |
| `vib_export.py` | Backfill `modes.npy` from cached Hessians; bundle export for FF fitting |
| `run_vib_spectra.py` / `plot_vib_spectra.py` | Deprecated wrappers → use `vib_spectra.py` |
| `plot_modes_arrows.py` | Vector arrows on normal-mode displacements |
| `mmff_molecular_session.py` | Interactive MMFF vibrational exploration |
| `fit_mmff_ch4.py` / `fit_mmff_c2h6.py` | Scale MMFF force constants to match reference modes |
| `analyze_ch4_modes.py` / `analyze_c2h6_modes.py` / `analyze_adamantane_modes.py` | Mode assignment tables vs reference |
| `generate_pyscf_vib_jobs.py` | Bakes PySCF vibrational job scripts |
| `vib_match.py` / `vib_store.py` / `vib_utils.py` | Pipeline support modules |
| `*.md` | Setup notes (`CP2K_INSTALLATION_GUIDE`, `GPU_Acceletated_QM_packages`, `VibSpectra_ASE`, `MMFF_VIBRATION_FITTING_REPORT`) |
| `pyscf/` | PySCF/GPU tests and basis listing — see `pyscf/README.md` |
| `orca/` | ORCA MPI example inputs — see `orca/README.md` |
| `SiNCs_notes/` | Result writeups — see `SiNCs_notes/README.md` |
| `README.md` | Pipeline index (bulk phonons are in `../phonons/`) |

---

## `doc/` — documentation

### Top-level design chats and study specs
| File | Role |
|------|------|
| `ChemBook.chat.md` | ChemBook metadata protocol design brainstorm (3896 lines) — source of truth for `py/chembook/` |
| `MetalTip_Molecule_Interaction_Study_Spec.md` | Active metal-tip × molecule study spec |
| `MetalTip_Molecule_Interaction_Study_Spec_revised-gpt.md` / `-gpt.md` | Revised / GPT-assisted variants |
| `Fast_method_for_coordination_bonds_molecule_tip.md` | Method notes for coordination-bond study |
| `MolecularVisualization_QM_GUI.md` | Visualization / GUI design notes |
| `molecule_surface_orientation_tutorial.md` | Molecule-on-surface orientation tutorial |
| `CompChem_software_quick_cheatsheet.md` | Quick QC software reference |
| `GPU_accelerated_QM_software.chat.md` | GPU QM software brainstorm |
| `HighPErformanceComputerAlgebraSystem.md` | HP CAS notes |
| `PCET_methods.chat.md` | PCET methods brainstorm |
| `Fine_tuining_local_LLM_to_my_codebase_and_knowledge_base.chat.md` | Local LLM fine-tuning notes |
| `Metacentrum_LLM_Notes.md` | LLM-on-Metacentrum notes |
| `Hermes_Agent_Setup.md` / `Hermes_Agent_sandboxing_safety.md` | Hermes agent setup + sandboxing |
| `topical_audit.md` | Cross-implementation maps per scientific topic with parity status |

### `doc/AGENTS/` — AI agent guidance
| Path | Role |
|------|------|
| `agentic_debugging_principles.md` | Debugging principles for agents |
| `workflows/pre-inventory.md` / `post-inventory.md` | Pre/post-task inventory checklists |

#### `doc/AGENTS/skills/` — one `SKILL.md` per task type
| Skill | When to use |
|-------|-------------|
| `chembook-jobs` | Creating/baking/running QC jobs — wrap in ChemBook metadata protocol |
| `code-reuse` | Writing new code — inventory-first, module-vs-script, no-new-files |
| `reusable-architecture` | Writing new functions/scripts/tests — prevent duplication |
| `doc-read-navigate` | Before writing — search existing implementations, audits, READMEs, headers |
| `doc-task-summary` | After implementing — update headers, README, topical audits |
| `doc-audit` | Dedicated documentation work — OKF format, topical audits |
| `centralized-plotting` | 2D scalar field plotting — use shared `plotUtils`, avoid transpose/aspect bugs |
| `visual-debugging` | Diagnostic plots / headless visual tests for debugging |
| `numerical-parity` | Comparing two calculations or simulation methods |
| `forcefield-validation` | Implementing/debugging interatomic force-fields |
| `port-to-opencl` | Porting Python compute kernels to PyOpenCL |
| `gpu-debug` | Debugging GPU/OpenCL kernels |
| `gpu-optimize` | Optimizing GPU/OpenCL kernel performance |
| `python-native-bindings` | Python bindings to C/C++/Fortran via ctypes |
| `python-perf` | Performant Python — vectorization, NumPy anti-patterns, preallocation |
| `metacentrum` | Submitting/managing HPC jobs on MetaCentrum |
| `molecular-structure-sync` | Touching molecular topology/bond orders/render/export — keep `AtomicGraph` authoritative |
| `reference-data` | Creating/updating pytest reference files |
| `running-tests` | Running tests or writing new test scripts |
| `try` | (Placeholder skill — not active) |

#### `doc/AGENTS/protocols/` — domain + general protocols
| Path | Role |
|------|------|
| `domain/quantum_mechanics.md` | QM calculation protocols |
| `domain/intramolecular_forcefields.md` | Intramolecular FF protocols |
| `domain/noncovalent_interactions.md` | Noncovalent interaction protocols |
| `domain/molecule_surface.md` | Molecule-on-surface protocols |
| `domain/topology_building.md` | Topology building protocols |
| `general/parity_checking.md` | Parity checking protocols |
| `general/performance_optimization.md` | Performance optimization protocols |
| `general/qualitative_validation.md` | Qualitative validation protocols |
| `general/topology_verification.md` | Topology verification protocols |

### `doc/EVIROMENTS_AND_MACHINES/` — machine setup notes
| File | Role |
|------|------|
| `Prokop_Desktop_GTX3090.md` | Desktop (GTX 3090) setup |
| `Prokop_Laptop_GTX1650.md` | Laptop (GTX 1650) setup |
| `Prokop_Metacentrum.md` | Metacentrum production setup |
| `Prokop_Metacentrum.exploration.md` | Metacentrum exploration notes |

---

## Navigation order for an unfamiliar task
1. `CODEMAP.md` (this file) — find the right folder
2. `ARCHITECTURE.md` — read the design rules for that layer
3. `py/<layer>/README.md` — file list + one-liners
4. `doc/topical_audit.md` — check for existing implementations / parity status
5. `doc/AGENTS/skills/<matching-skill>/SKILL.md` — task-specific AI guidance
6. Source file headers — essence, design notes, open issues/caveats
