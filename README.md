# Computational Chemistry Utilities

Python toolkit for molecular geometry, QC workflows, and diagnostics. One geometry/task stack drives multiple quantum-chemistry programs — swap backends without rewriting workflows.

## Architecture

Three orthogonal layers (see [`ARCHITECTURE.md`](ARCHITECTURE.md)):

| Layer | Path | Role |
|-------|------|------|
| Geometry | [`py/`](py/README.md) | `AtomicSystem`, constraints, placement, I/O |
| Tasks | [`py/tasks/`](py/tasks/README.md) | relax, scan, vibrations, interaction energy, Fukui job baking |
| Backends | [`py/interfaces/`](py/interfaces/README.md) | wrappers with `capabilities` sets |

Supporting pieces: [`config_loader`](py/config_loader.py) (machine paths), [`plotUtils`](py/plotUtils.py) / [`molVisApp`](py/molVisApp.py) (visualization), [`py/cluster/`](py/cluster/README.md) (PBS/HPC), [`examples/`](examples/README.md) (workflows).

## Backends

| Backend | Typical use |
|---------|-------------|
| **xTB** | Fast semiempirical screening (GFN1/2, GFN-FF) |
| **DFTB+** | Cheap DFT with SK tables; periodic systems |
| **PySCF** | Gaussian-basis HF/DFT, Fukui, grids |
| **Psi4** | High-accuracy HF/DFT/MP2, RESP |
| **GPAW** | Plane-wave DFT, surfaces, periodic Fukui |
| **MMFF94** | Force-field relax and vibrations |

In-process DFTB+ / OpenCL grid projection lives in [`py/dftb/`](py/dftb/README.md) (below the task backends).

## Quick start

Copy [`machine_config.template.yaml`](machine_config.template.yaml) → `machine_config.yaml` and set local tool/SK paths.

```python
from py import config_loader as cfg
from py.AtomicSystem import AtomicSystem
from py.interfaces.xtb import XTBBBackend
from py.tasks.relax import relax

geom = AtomicSystem(fname='data/xyz/H2O.xyz')
backend = XTBBBackend(method='GFN2-xTB')
result = relax(geom, backend, method='GFN2-xTB', mode='local')
print(result.geom.apos)
```

Same pattern with `PySCFBackend`, `DFTBPlusBackend`, `GPAWBackend`, etc. — see [`ARCHITECTURE.md`](ARCHITECTURE.md) usage patterns.

### H-bond dimer (xTB / DFTB+)

Monomer XYZ files need e-pair (`E`) dummy atoms ([`examples/add_epairs.py`](examples/add_epairs.py)). Build, relax, then rigid O···O scan:

```bash
python examples/hbond/relax_dimer.py --mol data/xyz/H2O.xyz --backend xtb --outdir tmp/H2O_dimer_xtb
python examples/hbond/scan_dimer.py --geom tmp/H2O_dimer_xtb/relaxed.xyz --backend xtb --outdir tmp/H2O_dimer_scan_xtb
```

Details: [`examples/hbond/README.md`](examples/hbond/README.md), [`ARCHITECTURE.md`](ARCHITECTURE.md) Pattern 9.

## Documentation

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — design rules, backend semantics, examples
- [`AGENTS.md`](AGENTS.md) — contributor / agent conventions
- [`py/README.md`](py/README.md) — Python module index
- [`examples/README.md`](examples/README.md) — runnable study scripts (Fukui, phonons, adsorption, H-bonds, …)
- [`doc/topical_audit.md`](doc/topical_audit.md) — cross-topic implementation map
