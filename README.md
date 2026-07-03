# Computational Chemistry Utilities

## Architecture Overview

Three orthogonal layers — any task works with any backend:

| Layer | Modules | Purpose |
|-------|---------|---------|
| **Geometry** | `py/AtomicSystem.py`, `py/geom_engine.py` | Chemistry/geometry operations, constraints, placement |
| **Tasks** | `py/tasks/relax.py`, `py/tasks/scan.py`, `py/tasks/vibrations.py` | Calculation-type orchestration (local or export mode) |
| **Backends** | `py/interfaces/dftbplus.py`, `py/interfaces/pyscf.py`, `py/interfaces/psi4.py`, `py/interfaces/xtb.py`, `py/interfaces/gpaw.py`, `py/interfaces/mmff.py` | QC software wrappers with `capabilities` sets |

```python
from py.AtomicSystem import AtomicSystem
from py.interfaces.dftbplus import DFTBPlusBackend
from py.tasks.relax import relax

geom = AtomicSystem(fname='molecule.xyz')
backend = DFTBPlusBackend(sk_path='/path/to/SK/3ob-3-1', method='D3H5')
result = relax(geom, backend, method='D3H5', mode='local')
```

Supported backends: **DFTB+** (mio, 3ob, auorg, matsci, ...), **PySCF**, **Psi4**, **xTB** (GFN1/2, GFN-FF, g-xTB), **GPAW** (PBE, B3LYP, ...), **MMFF94**.

See `ARCHITECTURE.md` for full documentation.
