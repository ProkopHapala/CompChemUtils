# CompChemUtils Orthogonal Architecture Documentation

> **ATTENTION LLMs**: Read this before modifying any code. The architecture is deliberately
> orthogonal: geometry, tasks, and backends are separate. Do NOT mix them.

---

## Core Design Principle

The system is built on **orthogonal separation of concerns**:
- **Geometry/Chemistry layer** (what to calculate)
- **Task layer** (what type of calculation)
- **Backend layer** (which software/method to use)

This allows any task to work with any backend without code duplication.

---

## Module Structure

### 1. Geometry/Chemistry Layer (`py/`)

**`AtomicSystem.py`** — Core molecular geometry container
- Stores atomic positions (`apos`), element names (`enames`), atomic types (`atypes`)
- Handles file I/O (XYZ, MOL, MOL2, GEN formats)
- Geometry operations: rotation, translation, selection, subset extraction
- Bond finding, neighbor lists, angle/dihedral detection
- Periodic boundary conditions: `clonePBC()`, `clonePBC_central()`
- Methods: `saveXYZ()`, `findBonds()`, `selectSubset()`, `orient()`, `shift()`

**`geom_engine.py`** — Program-agnostic geometric constraints
- `GeomConstraint` dataclass: freeze atoms, fix distance/angle/dihedral
- Helper functions: `freeze_atoms()`, `fix_distance()`, `fix_angle()`, `fix_dihedral()`
- Advanced placement: `place_molecule_on_edge()`, `auto_edge_placement()`
- Molecule attachment: `generate_ag4_attach_movie()`, `generate_edge_attach_movie()`
- Validation: `validate_geometry()` for sanity checks

**`elements.py`** — Periodic table data
- Element properties: atomic numbers, masses, vdW radii, valence electrons
- Used by `AtomicSystem` for property initialization

---

### 2. Task Layer (`py/tasks/`)

**`base.py`** — Result dataclasses (pure data containers)
- `RelaxResult`: optimized geometry, energies, convergence status
- `ScanResult`: coordinate values, energies, geometries per frame
- `VibResult`: frequencies, modes, masses
- `FukuiResult`: f+, f-, f0 functions on grid
- `PhononResult`: q-points, frequencies, eigenvectors
- `InteractionEnergyResult`: E_int, component energies, fragment geometries

**`relax.py`** — Geometry relaxation orchestration
```python
def relax(geom, backend, method, basis=None, constraints=None,
          mode='local', outdir='.', **kw) -> RelaxResult
```
- `mode='local'`: calls `backend.run_relax()` directly
- `mode='export'`: calls `backend.export_relax()` to write input files

**`vibrations.py`** — Vibrational frequency calculation
```python
def vibrations(geom, backend, method, basis=None,
               mode='local', outdir='.', **kw) -> VibResult
```

**`scan.py`** — Rigid and relaxed scans
- `rigid_scan()`: pre-compute frames, evaluate energy per frame (parallelizable)
- `relaxed_scan()`: step-by-step with constraints, uses `step_callback` for geometry ops
- `make_scan_grid()`: non-uniform distance grid (fine near contact, coarse far)
- `make_rigid_shift_frames()`: generate frames by translating fragment

**`interaction_energy.py`** — E_int = E_whole - E_frag1 - E_frag2
- Optional relaxation of whole system and/or fragments
- Supports both local execution and export modes

---

### 3. Backend Layer (`py/interfaces/`)

**`_base.py`** — Abstract base class for all backends
```python
class CalculationBackend(ABC):
    name: str = "base"
    capabilities: Set[str] = set()  # {'energy', 'relax', 'vibrations', ...}

    # Local execution methods
    def run_energy(self, geom, method, basis=None, **kw) -> float
    def run_relax(self, geom, method, basis=None, constraints=None, **kw)
    def run_vibrations(self, geom, method, basis=None, **kw) -> VibResult
    def run_phonons(self, geom, method, basis=None, kpoints=None, **kw)
    def run_density(self, geom, method, basis=None, grid=None, **kw)
    def run_esp(self, geom, method, basis=None, grid=None, **kw)
    def run_fukui(self, geom, method, basis=None, grid=None, **kw) -> FukuiResult
    def run_resp(self, geom, method, basis=None, **kw)

    # Export methods (for cluster jobs)
    def export_energy(self, geom, method, basis=None, outdir='.', **kw) -> List[str]
    def export_relax(self, geom, method, basis=None, constraints=None, outdir='.', **kw)
    def export_vibrations(self, geom, method, basis=None, outdir='.', **kw)
    def export_scan_frames(self, frames, method, basis=None, outdir='.', **kw)
```

#### DFTB+ Backend (`dftbplus.py`)

**Slater-Koster (SK) table parameter sets:**

| Parameter Set | `sk_path` basename | Elements (from SK files) | Key Parameters |
|---------------|--------------------|--------------------------|----------------|
| **mio-1-1** | `mio-1-1` | C, H, N, O, P, S | `method='D3'` or `'D3H5'` |
| **3ob** | `3ob-3-1` | Br, C, Ca, Cl, F, H, I, K, Mg, N, Na, O, P, S, Zn | `method='D3'` or `'D3H5'` |
| **auorg** | `auorg-1-1` | Au, C, H, N, O, S | `orbital_resolved_scc=True` (mandatory) |
| **matsci** | `matsci-0-3` | Al, B, C, Cu, H, N, Na, O, P, Si, Ti | `method='D3'` |
| **pbc** | `pbc-0-3` | C, F, Fe, H, N, O, Si | `method='D3'`, `kpts` mesh |
| **hyb** | `hyb-0-2` | Ag, As, C, Ga, H, O, S, Si | `method='D3'` |
| **ob2** | `ob2-1-1` | C, H, N, O | `method='D3'` |
| **trans3d** | `trans3d-0-1` | C, Co, Fe, H, N, Ni, O, Sc, Ti | `method='D3'` |

**Constructor parameters:**
```python
backend = DFTBPlusBackend(
    sk_path='/path/to/skfiles/3ob-3-1',   # Mandatory for DFTB Hamiltonian
    method='D3H5',                         # '', 'D3', 'D3H5'
    scc=True,
    orbital_resolved_scc=False,           # REQUIRED for auorg-1-1
    temperature=300.0,
    kpts=(4, 4, 1),                       # For periodic systems
    maxiter=250,
)
```

**Capabilities:** `{'energy', 'relax', 'vibrations', 'phonons'}`

**Export format:** Writes `dftb_in.hsd` + `geo.gen`

**Critical note for auorg:**
```python
# auorg-1-1 REQUIRES orbital_resolved_scc=True
backend = DFTBPlusBackend(
    sk_path='/path/to/auorg-1-1',
    orbital_resolved_scc=True
)
```

**Method parameter semantics for DFTB+:**
- `method=''` or `None`: Plain SCC-DFTB (no dispersion)
- `method='D3'`: DFT-D3 dispersion with Becke-Johnson damping
- `method='D3H5'`: DFT-D3 with H5 correction (hydrogen-bond specific)

---

#### PySCF Backend (`pyscf.py`)

- `method`: `'hf'`, `'rhf'`, `'uhf'`, `'b3lyp'`, `'pbe'`, or any PySCF-supported functional
- `basis`: standard basis sets — `'6-31G*'`, `'cc-pVDZ'`, `'sto-3g'`, `'def2-SVP'`, etc.
- Capabilities: `{'energy', 'relax', 'vibrations', 'density', 'esp', 'fukui'}`
- Constraints: NOT yet implemented (warns and ignores)

---

#### Psi4 Backend (`psi4.py`)

- `method`: `'b3lyp'`, `'pbe'`, `'hf'`, `'mp2'`, `'ccsd(t)'`, etc.
- `basis`: `'cc-pVDZ'`, `'6-311G*'`, `'def2-SVP'`, `'def2-TZVP'`, etc.
- Capabilities: `{'energy', 'relax', 'resp', 'esp'}`
- Special: `export_movie()` for XYZ trajectory → batch Psi4 inputs
- Constraints: Only `freeze_atoms` translated to `frozen_cartesian`

---

#### xTB Backend (`xtb.py`)

- `method`: `'GFN1-xTB'`, `'GFN2-xTB'`, `'GFN-FF'`, `'g-xTB'`
- `backend`: `'auto'` (try tblite → xtb CLI), `'tblite'`, `'xtb'`
- No basis parameter (semiempirical)
- Capabilities: `{'energy', 'relax', 'vibrations'}`
- Extra: `charge`, `uhf`, `solvent` (ALPB implicit solvent)

---

#### GPAW Backend (`gpaw.py`)

- `xc`: exchange-correlation — `'PBE'`, `'B3LYP'`, `'revPBE'`, `'RPBE'`, `'mBEEF'`, etc.
- `mode`: `'pw'` (plane-wave) or `'lcao'` (linear combination of atomic orbitals)
- `ecut`: plane-wave cutoff in eV (default 300, typical 400-600 for accurate adsorption)
- `kpts`: k-point mesh — `(1,1,1)` for molecules, `(4,4,1)` for surfaces
- `h`: real-space grid spacing (overrides `mode='pw'`)
- Capabilities: `{'energy', 'relax', 'vibrations', 'phonons', 'density', 'esp'}`
- No basis parameter (PAW datasets are separate from this interface)

---

#### MMFF94 Backend (`mmff.py`)

- `method`: `'mmff94'` or `'mmff94s'`
- No basis parameter (force field)
- Capabilities: `{'energy', 'relax', 'vibrations'}`
- Always local (no export needed — runs fast)

---

## Method/Basis Parameter Mapping

### Method strings (backend-specific interpretation):

| Backend | Method Parameter | Meaning |
|---------|------------------|---------|
| DFTB+ | `''`, `'D3'`, `'D3H5'` | Dispersion correction (SK set is backend config, not method) |
| PySCF | `'hf'`, `'rhf'`, `'uhf'`, `'b3lyp'`, `'pbe'` | HF or DFT functional |
| Psi4 | `'b3lyp'`, `'pbe'`, `'hf'`, `'mp2'` | HF or DFT or wave-function method |
| xTB | `'GFN1-xTB'`, `'GFN2-xTB'`, `'GFN-FF'`, `'g-xTB'` | GFN parameterization |
| GPAW | `'PBE'`, `'B3LYP'` (via `xc` param) | Exchange-correlation functional |
| MMFF | `'mmff94'`, `'mmff94s'` | Force field variant |

### Basis strings (where applicable):

| Backend | Basis Parameter | Examples |
|---------|-----------------|----------|
| PySCF | `basis` | `'6-31G*'`, `'cc-pVDZ'`, `'sto-3g'`, `'aug-cc-pVTZ'` |
| Psi4 | `basis` | `'cc-pVDZ'`, `'6-311G*'`, `'def2-SVP'`, `'def2-TZVP'` |
| DFTB+ | `basis=None` | Not used — SK files define basis |
| xTB | `basis=None` | Not used — semiempirical |
| GPAW | `basis=None` | Not used — PAW datasets are separate |
| MMFF | `basis=None` | Not used — force field |

---

## Usage Patterns

### Pattern 1: Local execution with DFTB+ (3ob set)
```python
from py.AtomicSystem import AtomicSystem
from py.interfaces.dftbplus import DFTBPlusBackend
from py.tasks.relax import relax

geom = AtomicSystem(fname='molecule.xyz')
backend = DFTBPlusBackend(
    sk_path='/home/user/SK/3ob-3-1',
    method='D3H5',
    scc=True
)
result = relax(geom, backend, method='D3H5', mode='local')
```

### Pattern 2: Local execution with PySCF
```python
from py.AtomicSystem import AtomicSystem
from py.interfaces.pyscf import PySCFBackend
from py.tasks.relax import relax

geom = AtomicSystem(fname='molecule.xyz')
backend = PySCFBackend(verbose=0)
result = relax(geom, backend, method='b3lyp', basis='6-31G*', mode='local')
```

### Pattern 3: Export for cluster (Psi4)
```python
from py.interfaces.psi4 import Psi4Backend
from py.tasks.scan import rigid_scan, make_rigid_shift_frames

geom = AtomicSystem(fname='system.xyz')
backend = Psi4Backend(mem='4GB')
frames = make_rigid_shift_frames(geom, i_fixed=0, i_mobile=10,
                                 distances=[2.0, 2.5, 3.0, 4.0])
result = rigid_scan(frames, backend, method='b3lyp', basis='cc-pVDZ',
                    mode='export', outdir='scan_jobs/')
```

### Pattern 4: GPAW periodic surface calculation
```python
from py.interfaces.gpaw import GPAWBackend
from py.tasks.relax import relax

backend = GPAWBackend(
    kpts=(4, 4, 1),
    mode='pw',
    ecut=400,
    xc='PBE'
)
result = relax(geom, backend, method='PBE', mode='local')
```

### Pattern 5: xTB semiempirical fast screening
```python
from py.interfaces.xtb import XTBBBackend
from py.tasks.relax import relax

backend = XTBBBackend(method='GFN2-xTB', charge=0, uhf=0)
result = relax(geom, backend, method='GFN2-xTB', mode='local')
```

### Pattern 6: Relaxed scan with constraints
```python
from py.geom_engine import fix_distance
from py.tasks.scan import relaxed_scan

def constraints_fn(d):
    return [fix_distance(0, 10, d)]

def step_callback(geom, d):
    # shift atom 10 to distance d from atom 0
    geom_copy = geom.__class__.__new__(geom.__class__)
    geom_copy.__dict__.update(geom.__dict__)
    # ... apply shift ...
    return geom_copy

result = relaxed_scan(geom, backend, method='gfn2-xtb',
                      constraints_fn=constraints_fn,
                      step_callback=step_callback,
                      coord_values=[2.0, 2.5, 3.0],
                      mode='local')
```

---

## Key Architectural Rules for LLMs

1. **NEVER mix concerns**: Don't put backend-specific code in task modules
2. **ALWAYS use base classes**: New backends must inherit from `CalculationBackend`
3. **DECLARE capabilities**: Each backend must declare its supported tasks in `capabilities` set
4. **USE GeomConstraint**: All geometric constraints go through `geom_engine.py`, not backend-specific syntax
5. **RESPECT mode parameter**: All task functions support both `'local'` and `'export'` modes
6. **RETURN proper result types**: Use dataclasses from `tasks/base.py`, never raw tuples
7. **CONVERT geometry properly**: Backends must handle both `AtomicSystem` objects and `(apos, es)` tuples
8. **CHECK capabilities first**: Call `backend.check(task)` before attempting operations

---

## Adding New Backends

1. Create new file in `py/interfaces/`
2. Inherit from `CalculationBackend`
3. Set `name` and `capabilities`
4. Implement `run_*` methods for local execution
5. Implement `export_*` methods for cluster export (optional but recommended)
6. Handle geometry conversion: `_to_backend_format()` and `_from_backend_format()`
7. Map method/basis parameters appropriately for the software

---

## Adding New Tasks

1. Create result dataclass in `tasks/base.py`
2. Create task function in `tasks/` (e.g., `tasks/newtask.py`)
3. Accept `geom`, `backend`, `method`, `basis` as standard parameters
4. Support both `mode='local'` and `mode='export'`
5. Use `backend.check()` to verify capability
6. Return appropriate result dataclass
