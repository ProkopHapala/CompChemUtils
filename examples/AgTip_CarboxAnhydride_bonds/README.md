# AgTip_CarboxAnhydride_bonds

Adsorption of carboxylic/anhydride molecules on metal cluster tips (M₄ tetrahedron) and M(111)+adatom surfaces — DFTB+ and xTB relax, rigid binding-energy scans, unified surface movie export.

- **surface_workflow.py** — unified CLI: generate adatom/edgepair/cluster attach movies, export Psi4/GPAW QC inputs (replaces several legacy `geom_*` scripts)
- **generate_metal4.py** — build M₄ tetrahedron XYZ from FCC lattice constant (Ag, Au, Cu, …)
- **run_cluster_relax.py** — relax molecule+cluster frames via `py.tasks.relax` (xTB, DFTB+, PySCF)
- **batch_relax_dftb.py** — batch DFTB+ relax with frozen metal atoms (`py.interfaces.dftbplus`)
- **batch_relax_xtb.py** — batch GFN2-xTB relax; resets metal positions post-relax (no constraints in xTB)
- **scan_adsorption.py** — rigid E_int scan on M₄ cluster (xTB vs DFTB+), outputs `.dat` + `.xyz` + PNG
- **scan_surface_adsorption.py** — same for M(111)+adatom; reads DFTB+ `geo_end.gen`
- **test_dftb_export.py** — export-only DFTB+ inputs to debug SK parameter issues
- **DFTB_RELAXATION_REPORT.md** / **DFTB_RELAXATION_AND_SCAN_REPORT.md** / **RIGID_SCAN_REPORT.md** — study writeups

Workflow: generate cluster → orient movies → `batch_relax_*` → `scan_*`. SK paths via `machine_config.yaml`, not hard-coded `SK_PATH`.

Parent index: [`../README.md`](../README.md).
