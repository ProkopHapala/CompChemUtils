# DFTB OpenCL kernels

| File | Role |
|------|------|
| `LCAO_grid.cl` | LCAO density and orbital projection onto 3D grids |
| `LCAO_STM.cl` | STM tunneling (Dyson / MO overlap scans) |

Loaded by `Grid_dftb.GridProjector._load_kernels()`. Source: SPAMMM `kernels/`.
