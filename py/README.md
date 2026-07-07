# py

Python computational-chemistry subsystem — geometry/chemistry layer, task orchestration, QC backends, cluster helpers, and diagnostics. Orthogonal design: tasks are backend-agnostic; backends declare `capabilities`. See `/ARCHITECTURE.md`.

- **AtomicSystem.py** — canonical molecular geometry container (`apos`, `enames`, `atypes`, PBC, bonds), file I/O (XYZ/MOL/MOL2/GEN), selection, rotation, neighbor lists, bond finding
- **geom_engine.py** — program-agnostic `GeomConstraint` spec and placement workflows (edge attach, Ag₄ attach movies, `validate_geometry`); H-bond dimer construction from e-pair oriented monomers (`build_hbond_dimer`, `strip_epairs`)
- **atomicUtils.py** — low-level geometry primitives: file loaders, bond/H-bond detection, angles/dihedrals, orientation frames, graph/cycle helpers, fragment assembly
- **elements.py** — periodic-table lookup table (Z, radii, masses, colors, valence electrons) consumed by geometry and visualization code
- **AtomicGraph.py** — object-graph alternative to parallel arrays (`Atom`/`Bond`/`Ring` with stable identity, `to_arrays()` for numpy/vispy interop)
- **config_loader.py** — machine-independent path/tool resolution from `machine_config.yaml` at repo root (`require_path`, `get_tool`, `dftbcore_lib`, `ensure_pyball_path`)
- **dftb/** — in-process DFTB+ (`DFTBcore` ctypes) + OpenCL grid/STM projection (`Grid_dftb`, `kernels/LCAO_*.cl`); see `dftb/README.md`
- **ocl/** — `OpenCLBase` for GPU kernels (used by `py/dftb`)
- **plotUtils.py** — shared matplotlib diagnostics (1D scans, 2D scalar fields, cube slices, `plotGeometry`, trajectories); keep plotting out of core compute modules
- **molVisApp.py** — interactive PyQt5 + Vispy molecular viewer (`python -m py.molVisApp [xyz|POSCAR]`)
- **AtomicSystem_new.py** — experimental fork of `AtomicSystem` with verbose debug logging; not the production import path
- **__init__.py** — package marker (empty)
- **tasks/** — backend-agnostic calculation orchestration (relax, scan, vibrations, interaction energy, Fukui job baking)
- **interfaces/** — `CalculationBackend` implementations wrapping DFTB+, PySCF, Psi4, xTB, GPAW, MMFF; see `interfaces/README.md` for DFTB two-layer model
- **cluster/** — PBS script generation and interactive-job environment extraction for Metacentrum
- **system_specific/** — ASE-dependent domain builders (metal surfaces, clusters) not used by the generic task layer
