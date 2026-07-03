# Fukui Function Calculations

Scripts for computing and analyzing Fukui functions (f+, f-, f0) for
organic molecules and metal clusters using GPAW (plane-wave) and PySCF
(Gaussian basis) DFT methods.

Fukui functions measure electron density response to electron
addition/removal:
- **f+** (electrophilic) = ρ(N+1) - ρ(N) — where an added electron goes
- **f-** (nucleophilic) = ρ(N) - ρ(N-1) — where electron density is lost
- **f0** (radical)      = 0.5 × (f+ + f-)

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `gpaw_fukui_cluster/` | GPAW plane-wave Fukui jobs for isolated molecules + CO rigid scan jobs. See its [README.md](gpaw_fukui_cluster/README.md). |
| `pyscf_fukui_cluster/` | PySCF Gaussian basis Fukui jobs for isolated molecules. See its [README.md](pyscf_fukui_cluster/README.md). |

## Top-level Scripts

### Runners (compute Fukui densities)

| File | Type | Purpose |
|------|------|---------|
| `run_gpaw_fukui_mol.py` | Reusable | GPAW PBE Fukui for isolated molecules. Runs N/N+1/N-1 single-points, writes density cubes + Fukui grids. CLI: `--mol`, `--batch`, `--ecut`, `--vacuum`. |
| `run_ag_fukui.py` | One-off | PySCF PBE Fukui for metal clusters (Ag4, Ag7, Au4, Cu4). Hardcoded cluster specs (spin states per cluster). CLI: `--mol`, `--basis`. |
| `submit_gpaw_fukui.pbs` | One-off | PBS script to submit `run_gpaw_fukui_mol.py` on Metacentrum. Edit MOLECULES/ECUT/VACUUM variables. |

### Post-processing (compute Fukui from density cubes)

| File | Type | Purpose |
|------|------|---------|
| `make_fukui_cubes.py` | Reusable | Generic: reads 3 density cubes (N, N+1, N-1), subtracts to produce f+/f-/f0 cube files. CLI: `--cube-N`, `--cube-A`, `--cube-C`, `--outdir`. |

### Plotting & Analysis

| File | Type | Purpose |
|------|------|---------|
| `plot_fukui_slices.py` | Reusable | Generic 2D slice plotter for density + Fukui cubes. Panels: ρ_N, ρ_A, ρ_C, f+, f-, f0. CLI: `--cube-N/A/C`, `--out`, `--slice`. |
| `plot_fukui_slices_metal.py` | One-off | 2D Fukui slices for metal M4 tetrahedron clusters. Hardcoded results_metal/ path, tetrahedron geometry assumptions. CLI: `--mol`, `--basis`. |
| `plot_gpaw_fukui_slices.py` | One-off | 2D Fukui slices for GPAW M(111)+adatom surfaces. Slices through adatom position. CLI: `--metal`. |
| `compare_ag4_basis.py` | One-off | Compare Ag4 Fukui: def2-SVP vs LANL2DZ basis. Reads Mulliken indices + grid stats from results_Ag/. |
| `compare_metal_fukui.py` | One-off | Compare Fukui |f|_max across Ag/Au/Cu(111)+adatom surfaces. Reads results_metal/ .npy files. |
| `compare_cluster_surface_fukui.py` | One-off | Compare Fukui magnitude: M4 clusters vs M(111)+adatom surfaces. Computes surface/cluster ratio. |

### Reports

| File | Purpose |
|------|---------|
| `REPORT_Fukui_Metals.md` | Summary report: metal surface adatom reactivity via Fukui functions. Conclusions on Ag/Au/Cu. |

## Shared Backend

Most scripts import `fukui_backend.py` (not in git — lives in the
results directories on the cluster). It provides `read_cube()`,
`write_cube()`, `run_fukui_for_molecule()`, and `read_xyz()` helpers.

## Notes

- All molecules are planar, aligned in xy-plane (z=0)
- GPAW uses periodic box + vacuum; PySCF uses isolated molecule (no PBC)
- For anions in GPAW: use `Mixer(0.05, 5, 1.0)` + `maxiter=500` for small molecules
- For PySCF: always use `density_fit()` for >50 basis functions
- `def2-SVP` lacks diffuse functions — use `def2-SVPD` for production anion work
