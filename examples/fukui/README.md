# fukui

Fukui functions (f⁺, f⁻, f⁰) for organics and metal systems — GPAW plane-wave and PySCF Gaussian DFT, cluster job baking, and cross-method comparison plots.

- **fukui_backend.py** — shared `read_cube`, `write_cube`, `run_fukui_for_molecule()` helpers imported by runners
- **run_fukui.py** — PySCF Fukui CLI (`--mol`, `--basis`, `--xc`, 1D/2D plots); geometries from repo `data/xyz/`
- **run_gpaw_fukui_mol.py** — GPAW PBE Fukui for isolated molecules (N/N±1 single-points, grid subtraction)
- **run_ag_fukui.py** — PySCF Fukui for metal clusters (Ag₄, Ag₇, Au₄, Cu₄)
- **run_ag111_adatom.py** — PySCF Fukui on Ag(111)+adatom slab models
- **run_ag111_adatom_gpaw.py** — GPAW periodic Fukui for M(111)+adatom
- **run_ag_tetrahedron.py** / **run_batch_DZVP.py** — batch cluster Fukui with alternate basis sets
- **make_fukui_cubes.py** / **compute_fukui_grids.py** — subtract ρ(N±1) cubes → f⁺/f⁻/f⁰ grids
- **plot_fukui_slices.py** — generic 2D slice panels (ρ_N, ρ_A, ρ_C, f⁺, f⁻, f⁰)
- **plot_fukui_slices_metal.py** — M₄ tetrahedron cluster slices
- **plot_gpaw_fukui_slices.py** — M(111)+adatom surface slices through adatom
- **compare_ag4_basis.py** — def2-SVP vs LANL2DZ on Ag₄
- **compare_metal_fukui.py** — |f|_max across Ag/Au/Cu(111)+adatom
- **compare_cluster_surface_fukui.py** — M₄ cluster vs M(111)+adatom magnitude ratio
- **scan_ch2o_adatom.py** — generate molecule-to-surface distance scan XYZ movies (Ag₄, Ag₇, slab)
- **submit_gpaw_fukui.pbs** — Metacentrum PBS wrapper for `run_gpaw_fukui_mol.py`
- **Fukui.md** / **REPORT_Fukui_Metals.md** — theory notes and metals study summary

| Subdirectory | Purpose |
|--------------|---------|
| [`gpaw_fukui_cluster/`](gpaw_fukui_cluster/README.md) | Baked GPAW Fukui + CO rigid-scan cluster packages |
| [`pyscf_fukui_cluster/`](pyscf_fukui_cluster/README.md) | Baked PySCF Fukui cluster package |
| [`structures/`](structures/README.md) | Input XYZ/POSCAR/CIF for metals and scan trajectories |
| [`results/`](results/README.md) | Local density/Fukui output cache (not in git) |

Cluster baking uses `py.tasks.bake_jobs.bake_fukui_jobs` — see [`/ARCHITECTURE.md`](/ARCHITECTURE.md) Pattern 7.

Parent index: [`../README.md`](../README.md).
