---
name: metacentrum
description: Use when submitting or managing HPC jobs on MetaCentrum (Czech national grid). Covers OpenPBS job submission, scratch workflow, module system, file transfer, and job monitoring.
trigger:
  glob:
    - "**/*.pbs"
    - "**/*.sh"
  keyword:
    - "metacentrum"
    - "qsub"
    - "qstat"
    - "SCRATCHDIR"
    - "pbs"
---

## System Identity

MetaCentrum = Czech national HPC grid. Scheduler: **OpenPBS** (NOT Slurm). All job control via `qsub`/`qstat`/`qdel`.

## Hard Rules

- **NEVER run computations on login/frontend nodes.** Always submit via `qsub` or use `qsub -I` for interactive shell on a compute node.
- **ALWAYS use `$SCRATCHDIR`** for I/O. Copy inputs to scratch at job start, copy outputs back before job ends. Scratch is fast local NVMe; home/storage is slow NFS.
- **Kerberos tickets expire after ~12h.** If SSH fails, run `kinit` to re-authenticate.
- **Clean scratch before exit:** `rm -rf $SCRATCHDIR/*` — otherwise data is lost when job ends.

## Connection

```
ssh prokop@metafzu.fzu.cz
```

Frontend nodes: `metafzu.fzu.cz` (FZU Prague), `tarkil.metacentrum.cz` (Prague), `skirit.ics.muni.cz` (Brno).

For large data transfer, connect directly to storage node (faster, accepts only scp/rsync):
```
scp -r prokop@storage-praha1.metacentrum.cz:/home/prokop/PATH .
rsync -avh --progress prokop@storage-praha1.metacentrum.cz:/home/prokop/PATH .
```

## PBS Commands

| Command | Purpose |
|---------|---------|
| `qsub job.pbs` | Submit job |
| `qstat -u prokop` | Check your jobs |
| `qstat -f JOBID` | Full details of a job |
| `qdel JOBID` | Kill a job |
| `pbsnodes -a` | List compute nodes and properties |
| `qsub -I -l walltime=00:30:00 -l select=1:ncpus=1:mem=1gb` | Interactive compute node shell |
| `quota -s` | Check storage quota |

Job states: `Q` (queued), `R` (running), `E` (exiting), `F` (finished).

## PBS Job Script Template

```bash
#!/bin/bash
#PBS -N JOB_NAME
#PBS -l select=1:ncpus=16:mem=64gb:scratch_local=100gb
#PBS -l walltime=24:00:00
#PBS -j oe

trap 'cp -r $SCRATCHDIR/* $PBS_O_WORKDIR/ 2>/dev/null; rm -rf $SCRATCHDIR/*' EXIT

cd $PBS_O_WORKDIR
module purge
module add python    # or vasp, gpaw, psi4, etc.

cp -r ./input_data/* $SCRATCHDIR/
cd $SCRATCHDIR

export OMP_NUM_THREADS=$PBS_NUM_PPN
python3 run_calc.py > output.log 2>&1

cp -r * $PBS_O_WORKDIR/
```

### PBS Variables

| Variable | Meaning |
|----------|---------|
| `$SCRATCHDIR` | Fast local scratch on compute node (auto-created by PBS, auto-deleted after job) |
| `$PBS_O_WORKDIR` | Directory where `qsub` was executed (your home/storage) |
| `$PBS_JOBID` | Job ID |
| `$PBS_NUM_PPN` | Number of CPUs allocated |

### Resource Specification

```
#PBS -l select=1:ncpus=16:mem=64gb:scratch_local=100gb
```

- `select=1` = 1 chunk (node). Use `select=2` for multi-node (rare for QC).
- `ncpus` = cores per chunk. Match to your parallelism (e.g. `mpirun -np $ncpus`).
- `mem` = total memory per chunk. Overestimate slightly — OOM kills the job.
- `scratch_local` = local scratch disk size on compute node.
- `walltime` = max runtime. Job is killed when exceeded. Always set `trap` to save outputs.

### Error Codes

| Exit | Meaning | Fix |
|------|---------|-----|
| -23 | Kerberos ticket missing | Re-auth: `kinit` |
| -25 | CPU limit exceeded | Request more `ncpus` |
| -27 | OOM | Increase `mem=` |
| -29 | Walltime exceeded | Resubmit with more walltime + checkpoint |
| 271 | Killed via `qdel` | Manual termination |

## Module System

Software is loaded via environment modules (Lmod/EnvironmentModules).

```bash
module avail *vasp*          # search available software (wildcard)
module avail *python*
module avail *gpaw*
module add vasp/6.4.2        # load specific version
module add python gpaw psi4  # load multiple
module purge                 # unload everything (ALWAYS do this first in PBS scripts)
module list                  # show loaded modules
```

### Available Chemistry Modules (verified 2025-07)

| Module | Notes |
|--------|-------|
| `vasp/`, `vasp46/`, `vasp52/`, `vasp53/` | VASP (licensed — check access) |
| `vaspkit/`, `p4vasp/` | VASP pre/post-processing |
| `gpaw/`, `py-gpaw/` | GPAW |
| `xtb/` | Extended Tight Binding |
| `cp2k/` | CP2K |
| `nwchem/` | NWChem |
| `orca/` | ORCA |
| `turbomole/` | TURBOMOLE |
| `siesta/` | SIESTA |
| `quantum-espresso/`, `espresso/`, `espresso_md/` | QE |
| `wannier90/` | Wannier90 |
| `phonopy/`, `py-phonopy/` | Phonopy |
| `ase/`, `py-ase/` | Atomic Simulation Environment |
| `crystal/` | CRYSTAL |
| `cfour/` | CFOUR |
| `wien2k/` | WIEN2k |
| `columbus/` | COLUMBUS |
| `plumed/` | PLUMED (MD enhanced sampling) |
| `vmd/`, `xcrysden/` | Visualization |

### Python / Conda

| Module | Version |
|--------|---------|
| `python/` | base system python |
| `mambaforge/` | Python 3.10.6, conda 22.9.0 |
| `conda-modules/` | conda infrastructure |
| `py-pip/` | pip |

### NOT Available as Modules (must install manually)

- **PySCF** — `pip install pyscf` works (v2.13.1). Use with `module add mambaforge`.
- **Psi4** — NOT available. conda channels broken on frontend (no outbound internet to conda repos). Try `pip install psi4` or build from source.

### Installing Python Packages (no conda internet on frontend)

conda channels are blocked on the frontend. Use pip instead:
```bash
module add mambaforge
pip install --user pyscf    # or into venv:
python3 -m venv $SCRATCHDIR/venv && source $SCRATCHDIR/venv/bin/activate && pip install pyscf
```

## Scratch Workflow (Production Pattern)

1. Check `$SCRATCHDIR` is set (PBS creates it):
   ```bash
   [ -z "$SCRATCHDIR" ] && { echo "SCRATCHDIR empty!" >&2; exit 1; }
   cd $SCRATCHDIR || exit 1
   ```
2. Load modules (`module purge` first)
3. Copy source code to scratch and compile there (fast I/O):
   ```bash
   cp -r $PBS_O_WORKDIR/MyCode .
   cd MyCode && cmake .. && make
   ```
4. Copy input files and data to scratch
5. Run calculations
6. Copy results back: `cp -r $SCRATCHDIR/results/* $PBS_O_WORKDIR/`
7. Clean: `rm -rf $SCRATCHDIR/*`

## Code-Specific Quick Reference

**PySCF:** NOT a module. Use `module add mambaforge` then `pip install --user pyscf` (v2.13.1 available). Set `mf.chkfile='calc.chk'` for restart. Use density fitting for large systems. Set `OMP_NUM_THREADS=$PBS_NUM_PPN`.

**GPAW:** `module add gpaw`. Set `GPAW_SETUP_PATH`. Parallel: `mpirun -np N gpaw-python script.py`. LCAO mode faster for molecules. Save density restart files (small, useful). Do NOT save wavefunction restart files — too large for slow disk (same as VASP WAVECAR).

**VASP:** `module add vasp/6.x.x`. Files: `POSCAR`, `POTCAR`, `INCAR`, `KPOINTS`. Run: `mpirun -np N vasp_std`. Save `CHGCAR` for restart (small, useful). Do NOT save `WAVECAR` — too large for slow disk.

**Psi4:** NOT a module. conda channels blocked on frontend. Try `pip install --user psi4` or build from source. Run: `psi4 -n 8 input.in output.out`. Set `memory 32 GB` in input to match PBS `mem=`.

## Resource Estimation

| Software | Memory | Cores | Notes |
|----------|--------|-------|-------|
| PySCF | ~2GB / 100 basis funcs | 4-16 | Density fitting reduces memory |
| VASP | ~1GB / atom | 16-64 | Save CHGCAR, NOT WAVECAR (too large) |
| GPAW | ~4GB / 100 atoms (PW) | 8-32 | LCAO uses less |
| Psi4 | ~2-4GB / 100 basis funcs | 8-16 | Set memory in input file |

## Job Monitoring

```bash
qstat -u prokop              # your jobs
cat JOBNAME.oJOBID           # stdout
cat JOBNAME.eJOBID           # stderr
```

Crash signatures to check in `.e`/`.o` files:
- `Segmentation fault` → memory/bounds issue
- `Convergence failure` / `Energy not converging` → SCF parameters
- `walltime` / exit -29 → needs more time or checkpoint restart
- `Out of memory` / exit -27 → increase `mem=`

## Parallel Job Pattern (Multiple Runs per Job)

For parameter sweeps, run N independent calculations in parallel within one PBS job using background processes + PID tracking:

```bash
ncpus=16
nruns=0
# Build TODO list of parameter combinations
echo "$params" >> TODO

while [ -s TODO ]; do
    for (( icpu=1; icpu <= ncpus; icpu++ )); do
        [ -f CPU.$icpu.pid ] && kill -0 "$(cat CPU.$icpu.pid)" 2>/dev/null && continue
        rm -f CPU.$icpu.pid
        run_line=$(head -1 TODO) || break
        tail -n +2 TODO > TODO.new && mv TODO.new TODO
        ./exec.sh $icpu $run_line &
        echo $! > CPU.$icpu.pid
    done
done

# Wait for all
for pidfile in CPU.*.pid; do
    [ -f "$pidfile" ] && wait "$(cat "$pidfile")" 2>/dev/null; rm -f "$pidfile"
done
```
