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
- **ALWAYS use `#PBS -q luna`** (batch scripts) or `-q luna` (`qsub -I`) — dedicated FZU queue with priority. Without it, jobs go to the default shared queue.
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
| `qsub -I -q luna -l walltime=02:00:00 -l select=1:ncpus=1:mem=2gb` | Interactive compute node shell (always use `-q luna` — dedicated queue with priority) |
| `quota -s` | Check storage quota |

Job states: `Q` (queued), `R` (running), `E` (exiting), `F` (finished).

## PBS Job Script Template

```bash
#!/bin/bash
#PBS -N JOB_NAME
#PBS -l select=1:ncpus=16:mem=64gb:scratch_local=100gb
#PBS -l walltime=24:00:00
#PBS -j oe
#PBS -q luna

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

**GPAW:** `module add py-gpaw/24.1.0-gcc-10.2.1-fojjhkw` (spack build). **Must manually set `GPAW_SETUP_PATH`** — the spack module does NOT set it. Setups at `/storage/praha1/home/prokop/gpaw-setups-24.1.0/gpaw-setups-24.1.0/`. Do NOT use `/cfs/projects/` paths — not mounted on compute nodes. To install setups: `wget https://wiki.fysik.dtu.dk/gpaw-files/gpaw-setups-24.1.0.tar.gz` then `tar -xzf` (the `gpaw install-data` command fails with 403 Forbidden on MetaCentrum). Use `python3` (not `gpaw-python`) with `mpirun -np $PBS_NUM_PPN python3 script.py`. For PW restart: constant cell required across frames. Set `maxiter=200` for convergence.

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
- `FileNotFoundError: Could not find required PAW dataset file` → `GPAW_SETUP_PATH` not set or points to non-existent directory. Check with `ls $GPAW_SETUP_PATH/C.PBE.gz` on compute node.
- `MPI_ABORT` → usually follows from a Python error on rank 0 — check full traceback above

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

## Interactive Jobs for AI Agents

### Problem

`qsub -I` opens an interactive shell, but AI agent `run_command` calls are separate processes — can't keep a shell open. Two solutions below.

### Method 1: SSH to Compute Node (RECOMMENDED)

1. **User opens `qsub -I` in a terminal** (holds the job allocation):
   ```bash
   qsub -I -q luna -l walltime=02:00:00 -l select=1:ncpus=1:mem=2gb
   ```
2. **Agent extracts job info** via `py/cluster/interactive_job.py`:
   ```bash
   python3 py/cluster/interactive_job.py JOBID --outdir test
   ```
   Writes `job_env.json` (machine-readable) + `job_env.sh` (sourceable — exports PBS vars + inits module system).
   Find JOBID: `qstat -u prokop` → look for `STDIN`/interactive job.
3. **Agent runs commands via SSH** to the compute node:
   ```bash
   ssh NODE 'source /path/to/job_env.sh && module add py-gpaw/24.1.0-gcc-10.2.1-fojjhkw && python3 script.py'
   ```
   `job_env.sh` handles module init (`source /cvmfs/.../loadmodules`) — needed because non-interactive SSH skips `profile.d`.

**Key points:**
- Always use `-q luna` (dedicated queue, priority)
- Each SSH = fresh shell → must load modules every time (`&&` chain)
- `PBS_O_PATH` is skipped in `job_env.sh` (would break module system)
- Python API: `from py.cluster.interactive_job import parse_qstat, extract_node, extract_variables`

### Method 2: tmux Wrapper

```bash
tmux new-session -d -s mc -x 200 -y 50
tmux send-keys -t mc 'qsub -I -q luna -l walltime=02:00:00 -l select=1:ncpus=1:mem=2gb' Enter
sleep 10 && tmux capture-pane -t mc -p          # check if job started
tmux send-keys -t mc 'module add ... && python3 script.py' Enter
sleep 5 && tmux capture-pane -t mc -p -S -10    # read output
tmux kill-session -t mc                          # cleanup
```

Less reliable than SSH (timing issues with `sleep`/`capture-pane`, line wrapping, no exit codes).

### Full documentation

See `doc/EVIROMENTS_AND_MACHINES/Prokop_Metacentrum.exploration.md` sections "Persistent Interactive PBS Job via tmux" and "Persistent Interactive PBS Job via SSH to Compute Node".
