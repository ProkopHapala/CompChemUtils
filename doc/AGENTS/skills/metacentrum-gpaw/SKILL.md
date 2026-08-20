---
name: metacentrum-gpaw
description: Use when running GPAW jobs on MetaCentrum cluster. Covers module loading, PAW setup paths, PBS script generation, MPI execution, smearing for metals, dipole correction for slabs, and all known pitfalls from production runs.
trigger:
  glob:
    - "**/*gpaw*.pbs"
    - "**/*gpaw*.py"
    - "**/generate_*jobs*.py"
    - "**/MetalTip*/**"
  keyword:
    - "gpaw"
    - "metacentrum"
    - "pbs"
    - "qsub"
    - "GPAW_SETUP_PATH"
    - "dipole correction"
    - "fermidirac"
---

## Quick Reference Card

```bash
# PBS header — copy verbatim
#PBS -q luna
module purge
module add py-gpaw/24.1.0-gcc-10.2.1-fojjhkw
export GPAW_SETUP_PATH=/storage/praha1/home/prokop/gpaw-setups-24.1.0/gpaw-setups-24.1.0
export OMP_NUM_THREADS=1
mpirun -np $PBS_NUM_PPN python3 script.py 2>&1
```

```python
# GPAW constructor — minimum viable for metals
from gpaw import GPAW, PW, FermiDirac
calc = GPAW(
    mode=PW(400), xc='PBE', kpts=(1,1,1), spinpol=False,
    symmetry='off', maxiter=333,
    occupations=FermiDirac(0.05),           # CRITICAL for metals
    convergence=dict(energy=1e-5, density=1e-5, bands='occupied'),
)
```

## Known Pitfalls (all encountered in production)

### 1. `GPAW_SETUP_PATH` not set by `py-gpaw` module

**Symptom:** `FileNotFoundError: Could not find required PAW dataset file "O.LDA"`
**Cause:** The `py-gpaw/24.1.0` spack module does NOT export `GPAW_SETUP_PATH`. Unlike the old `gpaw/1.4.0` module which set it automatically.
**Fix:** Always manually export after module load:
```bash
export GPAW_SETUP_PATH=/storage/praha1/home/prokop/gpaw-setups-24.1.0/gpaw-setups-24.1.0
```
**Also set in Python as fallback:**
```python
os.environ.setdefault('GPAW_SETUP_PATH', '/storage/praha1/home/prokop/gpaw-setups-24.1.0/gpaw-setups-24.1.0')
```
**Note:** `gpaw install-data` fails on frontend (HTTP 403 — no outbound internet). Setups must be pre-downloaded and transferred. The 24.1.0 setups are at the path above. Old setups (`gpaw-setups-0.9.20000`) at `/software/gpaw/1.4.0/setup_files/gpaw-setups-0.9.20000` also work but may lack newer PAW features.

### 2. Wrong module name: `gpaw` vs `py-gpaw`

**Symptom:** Old Python 3.4 environment, missing features, or module not found.
**Cause:** `module add gpaw` loads `gpaw/1.4.0-py34` (ancient, Intel toolchain). The modern version is under `py-gpaw/`.
**Fix:** Always use `module add py-gpaw/24.1.0-gcc-10.2.1-fojjhkw`.
**Verify:** `module avail *gpaw*` on the frontend.

### 3. Wrong executable: `gpaw-python` does not exist

**Symptom:** `mpirun was unable to find the specified executable file`.
**Cause:** `gpaw-python` exists in some GPAW installations but NOT in the spack-built `py-gpaw/24.1.0` on Metacentrum.
**Fix:** Use `mpirun -np $PBS_NUM_PPN python3 script.py`. GPAW is imported as a Python module — `python3` with `mpirun` works for MPI parallelism.

### 4. Missing `-q luna` queue directive

**Symptom:** Jobs wait forever in default queue.
**Cause:** No `#PBS -q` directive → jobs go to shared default queue.
**Fix:** Always add `#PBS -q luna` (dedicated FZU queue with priority).

### 5. `maxiter` in convergence dict → `InputError`

**Symptom:** `InputError: The convergence keyword "maxiter" was supplied, which we do not know how to handle`.
**Cause:** `maxiter` is a GPAW constructor argument, NOT a convergence dict key. Convergence dict keys use spaces: `'energy'`, `'density'`, `'eigenstates'`, `'maximum iterations'`.
**Fix:**
```python
# WRONG
calc = GPAW(convergence=dict(energy=1e-5, maxiter=500))
# RIGHT
calc = GPAW(maxiter=500, convergence=dict(energy=1e-5, density=1e-5, bands='occupied'))
```

### 6. Missing `FermiDirac` smearing for metals

**Symptom:** SCF fails to converge, energy oscillates, "Charge sloshing" in metallic systems.
**Cause:** GPAW default occupations may not use smearing. Metallic slabs require fractional occupations.
**Fix:** Always pass `occupations=FermiDirac(0.05)` to the GPAW constructor for any system with metallic character (slabs, bulk metals, adatom systems). Use 0.05 eV as the smearing width (spec standard).

### 7. Anion SCF convergence failure (small molecules)

**Symptom:** SCF runs 333+ iterations without converging for charge=-1 calculations on small molecules (H2O, CH2O, CH2NH).
**Cause:** Diffuse anion electron in large vacuum cell → charge sloshing. Default mixer (beta=0.1) too aggressive.
**Fix:** `mixer=Mixer(0.05, 5, 1.0)` + `maxiter=500`:
```python
from gpaw import Mixer
calc = GPAW(..., mixer=Mixer(0.05, 5, 1.0), maxiter=500)
```
**Caveat:** If the anion is truly unbound (LUMO of neutral > 0 eV), no mixer will help. Check HOMO/LUMO of neutral first.

### 8. PW restart fails when cell changes between frames

**Symptom:** `gpaw_restart()` doesn't speed up subsequent frames — each frame does full SCF from scratch.
**Cause:** In PW mode, the plane-wave basis is tied to the cell. Different cell → different G-vectors → wavefunctions can't be reused.
**Fix:** Use a constant cell (the largest one) for all frames in scans. Set `atoms.set_cell(cell, scale_atoms=False)` explicitly.

### 9. Dipole correction for slabs

**Requirement:** All slab calculations with a dipole moment normal to the surface MUST use dipole correction (spec §5.1). Without it, the artificial dipole from periodic images corrupts energies.
**Implementation:**
```python
from gpaw.dipole_correction import DipoleCorrection
from gpaw.poisson import PoissonSolver
ps = PoissonSolver(name='fd', nn=2)
poisson = DipoleCorrection(ps, direction='z', width=1.0)
calc = GPAW(..., poisson=poisson)
```
**Layout requirement:** Vacuum below the slab (≥5 Å) so the correction plane sits in vacuum, not inside the electron density.

### 10. `FixAtoms` constraint missing in exported scripts

**Symptom:** Frozen atoms move during relaxation in exported/baked scripts.
**Cause:** Export functions may not transfer ASE constraints to the standalone script.
**Fix:** Explicitly set constraint in the baked script:
```python
from ase.constraints import FixAtoms
atoms.set_constraint(FixAtoms(indices=[0,1,2,...,17]))
```

### 11. `poisson` parameter → `poissonsolver` (GPAW 24.1.0)

**Symptom:** `TypeError: Unknown GPAW parameter: poisson`
**Cause:** GPAW 24.1.0 accepts `poissonsolver` (one word), NOT `poisson`. This affects the GPAW constructor and `calc.set()`.
**Fix:** Always use `poissonsolver=...`:
```python
# WRONG
calc = GPAW(..., poisson=poisson)
# RIGHT
calc = GPAW(..., poissonsolver=poisson)
```
**Dipole correction pattern (correct):**
```python
from gpaw.dipole_correction import DipoleCorrection
from gpaw.poisson import PoissonSolver
ps = PoissonSolver(name='fd', nn=2)
poisson = DipoleCorrection(ps, direction='z', width=1.0)
calc = GPAW(..., poissonsolver=poisson)
```

### 12. `DipoleCorrection` wrapper fails in PW mode — use dict format

**Symptom:** `AssertionError: assert len(psolver) == 1` in `ReciprocalSpaceHamiltonian.__init__`
**Cause:** The `DipoleCorrection` wrapper object is incompatible with PW mode's parallelized Poisson solver. PW mode expects either a single `PoissonSolver` or a dict.
**Fix:** In PW mode, use the dict format `poissonsolver={'dipolelayer': 'xy'}` instead of wrapping a `PoissonSolver` with `DipoleCorrection`:
```python
# WRONG (PW mode) — fails with assert len(psolver) == 1
from gpaw.dipole_correction import DipoleCorrection
from gpaw.poisson import PoissonSolver
ps = PoissonSolver(name='fd', nn=2)
poisson = DipoleCorrection(ps, direction='z', width=1.0)
calc = GPAW(mode=PW(400), ..., poissonsolver=poisson)

# RIGHT (PW mode) — dict format
calc = GPAW(mode=PW(400), ..., poissonsolver={'dipolelayer': 'xy'})
```
**Note:** `'xy'` means the dipole layer correction is applied along z (the non-periodic direction). The slab must be periodic in x,y and non-periodic in z.
**FD/LCAO mode:** The `DipoleCorrection` wrapper still works in FD/LCAO mode. Only PW mode requires the dict format.

### 13. `pbc=True` in all directions breaks dipole correction

**Symptom:** `ValueError: System must be non-periodic perpendicular to dipole-layer.`
**Cause:** Dipole correction requires the system to be non-periodic along the correction axis (z). If `pbc=True` (all 3 directions), GPAW rejects it.
**Fix:** Set `pbc=[True, True, False]` — periodic in x,y, non-periodic in z:
```python
atoms = Atoms(..., cell=cell, pbc=[True, True, False])
```

## PBS Script Template (Production-Ready)

```bash
#!/bin/bash
#PBS -N relax_Cu_bare
#PBS -l select=1:ncpus=8:mem=16gb:scratch_local=20gb
#PBS -l walltime=02:00:00
#PBS -j oe
#PBS -q luna
#PBS -m bae

trap 'cp -r $SCRATCHDIR/* $PBS_O_WORKDIR/ 2>/dev/null; rm -rf $SCRATCHDIR/* 2>/dev/null' EXIT

cd $PBS_O_WORKDIR
module purge
module add py-gpaw/24.1.0-gcc-10.2.1-fojjhkw
export GPAW_SETUP_PATH=/storage/praha1/home/prokop/gpaw-setups-24.1.0/gpaw-setups-24.1.0
export OMP_NUM_THREADS=1
export PYTHONUNBUFFERED=1

cp $PBS_O_WORKDIR/run_script.py $SCRATCHDIR/
cd $SCRATCHDIR
export TMPDIR=$SCRATCHDIR
export TMP=$SCRATCHDIR
export TEMP=$SCRATCHDIR

mpirun -np $PBS_NUM_PPN python3 run_script.py 2>&1

echo "Finished: $(date)"
cp -r $SCRATCHDIR/results $PBS_O_WORKDIR/ 2>/dev/null
```

## Baked Script Pattern (Self-Contained Runner)

Each baked script must be fully self-contained — no imports from the repo, no external data files. All geometry, parameters, and ChemBook provenance are embedded.

```python
#!/usr/bin/env python3
import os, sys, json, time, socket, atexit
import numpy as np
from datetime import datetime, timezone

os.environ.setdefault('GPAW_SETUP_PATH', '/storage/praha1/home/prokop/gpaw-setups-24.1.0/gpaw-setups-24.1.0')

from ase import Atoms
from ase.constraints import FixAtoms
from ase.optimize import BFGS
from ase.io import write
from gpaw import GPAW, PW, FermiDirac
from gpaw.dipole_correction import DipoleCorrection
from gpaw.poisson import PoissonSolver

# --- Constants embedded in script ---
METAL = "Cu"; VARIANT = "bare"
ECUT = 400.0; XC = "PBE"; KPTS = (1,1,1); SMEARING = 0.05
FMAX = 0.05; MAXSTEPS = 200
FROZEN = [0,1,2,...,17]  # frozen atom indices

# --- ChemBook provenance (write pending BEFORE running) ---
# ... see chembook-jobs SKILL.md for full pattern ...

# --- Build atoms (positions + cell embedded) ---
atoms = Atoms(symbols=[...], positions=[...], cell=[...], pbc=True)
atoms.set_constraint(FixAtoms(indices=FROZEN))

# --- GPAW calculator ---
ps = PoissonSolver(name='fd', nn=2)
poisson = DipoleCorrection(ps, direction='z', width=1.0)
calc = GPAW(
    mode=PW(ECUT), xc=XC, kpts=KPTS, spinpol=False, charge=0,
    symmetry='off', maxiter=333,
    occupations=FermiDirac(SMEARING),
    convergence=dict(energy=1e-5, density=1e-5, bands='occupied'),
    poisson=poisson,
    txt=os.path.join(RESULTS, 'gpaw.txt'),
)
atoms.calc = calc

# --- Relax ---
opt = BFGS(atoms, maxstep=0.2, logfile='-')
converged = opt.run(fmax=FMAX, steps=MAXSTEPS)
E = atoms.get_potential_energy()

# --- Verify frozen atoms didn't move ---
ps_final = atoms.get_positions()
frozen_disp = float(np.max(np.linalg.norm(ps_final[FROZEN] - np.array(INITIAL_POS[FROZEN]), axis=1)))
assert frozen_disp < 1e-4, f"Frozen atoms moved by {frozen_disp:.2e} Å!"

# --- Save + update ChemBook ---
write(os.path.join(RESULTS, 'relaxed.xyz'), atoms)
# ... update chembook.json status=done ...
```

## Resource Estimates

| System type | Atoms | CPUs | Memory | Walltime | Scratch | Notes |
|---|---|---|---|---|---|---|
| Small molecule (H2O, CH2O) | 3–6 | 4 | 8gb | 2h | 10gb | PW 200-500 eV |
| Medium molecule (pyridine) | 10–12 | 8 | 16gb | 4h | 20gb | |
| Large molecule (pentacene) | 36–40 | 16 | 32gb | 12h | 30gb | |
| Metal slab 3×3×3 (3d) | 27–28 | 8 | 16gb | 2h | 20gb | gamma-point, PW 400 eV |
| Metal slab 3×3×3 (4d/5d) | 27–28 | 16 | 32gb | 4h | 30gb | Mo, W, Pd, Ag, Pt, Au |
| Metal slab + k-mesh | 27–28 | 16-32 | 32gb | 8h | 30gb | 2×2×1 or 3×3×1 refinement |

## GPAW Module Details

| Property | Value |
|---|---|
| Module | `py-gpaw/24.1.0-gcc-10.2.1-fojjhkw` |
| GPAW version | 24.1.0 |
| Python | 3.9.12 |
| ASE | 3.22.1 (bundled) |
| NumPy | 1.22 (bundled) |
| SciPy | 1.8 (bundled) |
| MPI | OpenMPI 4.1.3 (bundled) |
| libxc | 4.3.4 (bundled) |
| Compiler | GCC 10.2.1 |

## Setup File Verification

Before submitting jobs, verify PAW setups exist for all elements:
```bash
# On frontend or compute node:
ls $GPAW_SETUP_PATH/Cu.PBE.gz  # should exist
ls $GPAW_SETUP_PATH/ | grep -E '^(Ti|V|Cr|Mn|Fe|Co|Ni|Cu|Zn|Mo|W|Al|Pd|Ag|Pt|Au)\..*PBE'
```

The 24.1.0 setups contain PBE setups for all 16 study metals (verified 2025-08).

## Debugging Checklist

When a GPAW job fails on Metacentrum, check in this order:

1. **`.o` output file** — look for Python traceback (MPI errors are usually downstream of a rank-0 Python error)
2. **`GPAW_SETUP_PATH`** — `echo $GPAW_SETUP_PATH` in the PBS script, verify `ls $GPAW_SETUP_PATH/El.PBE.gz` exists
3. **Module loaded?** — check `.o` file for `module: command not found` (happens if `module purge` runs before module system init)
4. **Queue** — `qstat -f JOBID` to verify it ran on `luna`
5. **Scratch** — `SCRATCHDIR` empty means job didn't get scratch allocation (check `#PBS -l scratch_local=NgB`)
6. **Walltime** — exit code -29 = walltime exceeded
7. **Memory** — exit code -27 = OOM, increase `mem=`
8. **SCF convergence** — check `gpaw.txt` for iteration count and energy trend. If not converging: add `FermiDirac` smearing (metals), gentler `Mixer` (anions), or increase `maxiter`
9. **Frozen atoms** — if frozen atoms moved, `FixAtoms` constraint was not set. Check the baked script.
10. **Dipole correction** — if slab energies look wrong, verify `DipoleCorrection` is in the calculator and vacuum below slab ≥ 5 Å.

## References

- General Metacentrum usage: [`metacentrum/SKILL.md`](../metacentrum/SKILL.md)
- ChemBook job metadata: [`chembook-jobs/SKILL.md`](../chembook-jobs/SKILL.md)
- Exploration log (all issues + fixes): [`doc/EVIROMENTS_AND_MACHINES/Prokop_Metacentrum.exploration.md`](../../../EVIROMENTS_AND_MACHINES/Prokop_Metacentrum.exploration.md)
- Metacentrum quickstart: [`doc/EVIROMENTS_AND_MACHINES/Prokop_Metacentrum.md`](../../../EVIROMENTS_AND_MACHINES/Prokop_Metacentrum.md)
- Job baking infrastructure: [`py/tasks/bake_jobs.py`](../../../py/tasks/bake_jobs.py)
- GPAW backend: [`py/interfaces/gpaw.py`](../../../py/interfaces/gpaw.py)
- Metal tip relax generator: [`examples/MetalTip_Molecule_interaction/generate_relax_jobs.py`](../../../examples/MetalTip_Molecule_interaction/generate_relax_jobs.py)
- Fukui GPAW job generator (reference): [`examples/fukui/gpaw_fukui_cluster/generate_jobs.py`](../../../examples/fukui/gpaw_fukui_cluster/generate_jobs.py)
