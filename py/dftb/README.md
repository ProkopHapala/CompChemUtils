# py/dftb — in-process DFTB+ and GPU projection

Low-level DFTB+ layer (below `py/interfaces/dftbplus.py` task backends). Ported from [SPAMMM/spammm/quantum/DFTB](https://github.com/) with `LCAO_grid.cl` / `LCAO_STM.cl` kernels.

## Two execution paths

| Layer | Module | What it does |
|-------|--------|--------------|
| **Task backend** | `py/interfaces/dftbplus.py` | Subprocess `dftb+`, ASE export, relax/phonons |
| **In-process + GPU** | `py/dftb/` | `libdftbcore.so` ctypes SCF, density/MO matrices, OpenCL grid/STM |

Both use the same fork (`dftb.repo` in `machine_config.yaml`) and Slater–Koster files (`sk_dir`).

## Workflow (density on grid)

```python
from py import config_loader as cfg
from py.dftb import DFTBcore, setup_gridprojector_from_dftb
from py.dftb.DFTBplusParser import parse_wfc_hsd, convert_wfc_to_species_list_ang

d = DFTBcore(libpath=cfg.dftbcore_lib())
d.init('dftb_in.hsd')
d.enable_matrix_collection(dm=True, h=True, s=True)
E = d.run_scf()
dm = d.get_dm_dense()

wfc = parse_wfc_hsd('py/dftb/data/wfc.3ob-3-1.hsd')  # or machine wfc path
species_ang = convert_wfc_to_species_list_ang(wfc)
proj = setup_gridprojector_from_dftb({'dm': dm, 'apos': ...}, species_ang)
```

## Files

- **DFTBcore.py** — ctypes wrapper to `libdftbcore.so` (SCF, H/S/DM/eigenvectors)
- **DFTBplusParser.py** — parse `wfc.*.hsd` STO basis for grid projection
- **Grid_dftb.py** — OpenCL `GridProjector` (density, MOs, STM/LDOS)
- **basis_optimizer.py** — fit STO tails to reference density profiles
- **kernels/** — `LCAO_grid.cl`, `LCAO_STM.cl`
- **data/** — `wfc.mio-1-1.hsd`, `wfc.3ob-3-1.hsd`

## Legacy imports

Older examples use `from pyBall.DFTB.DFTBcore import DFTBcore` via `paths.pyball` (FireCore). Prefer `from py.dftb import DFTBcore` in new code.
