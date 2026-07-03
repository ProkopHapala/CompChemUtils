
# RULES:

* DO NOT RUN STUFF ON LOGIN NODE!!!
  * you may use interactive node for that: `qsub -I -l walltime=00:30:00 -l select=1:ncpus=1:mem=1gb`
* USE SCRATCH — always copy inputs to `$SCRATCHDIR`, run there, copy results back
* Kerberos tickets expire after ~12h — re-authenticate with `kinit` if SSH stops working

---

# Quickstart

1. **Connect:** `ssh prokop@metafzu.fzu.cz` (wait for password prompt)
2. **Prepare job script** (see template below) with `#PBS` directives
3. **Submit:** `qsub my_job.pbs`
4. **Check status:** `qstat -u prokop`
5. **When finished:** check `.o` / `.e` files, copy results from submission dir

---

# Connect to Server

```
ssh prokop@metafzu.fzu.cz
```

Wait for password prompt. Frontend nodes: `tarkil.metacentrum.cz` (Prague), `skirit.ics.muni.cz` (Brno), `alfrid.metacentrum.cz` (Plzen).

## Persistent SSH for AI Agents

Add to `~/.ssh/config` for stable connection (avoids repeated password prompts):

```
Host metacentrum
    HostName metafzu.fzu.cz
    User prokop
    ServerAliveInterval 60
    ControlMaster auto
    ControlPath ~/.ssh/control-%r@%h:%p
    ControlPersist 4h
```

---

# Copy Large Data Fast

Frontend nodes are slow for data transfer. Go directly to storage node (accepts only scp/rsync):

```
scp -r prokop@storage-praha1.metacentrum.cz:/home/prokop/OH-Tip .
```

```
rsync -avh --progress prokop@storage-praha1.metacentrum.cz:/home/prokop/OH-Tip .
```

---

# PBS Job Submission (OpenPBS)

MetaCentrum uses **OpenPBS** (not Slurm). Essential commands:

| Command | Purpose |
|---------|---------|
| `qsub job.pbs` | Submit a job |
| `qstat -u prokop` | Check your job status |
| `qdel JOBID` | Kill a job |
| `pbsnodes -a` | Info about compute nodes |
| `qsub -I -l walltime=00:30:00 -l select=1:ncpus=1:mem=1gb` | Interactive node shell |
| `quota -s` | Check storage quota |

Job states: `Q` (queued), `R` (running), `E` (exiting), `F` (finished)

## PBS Job Script Template

```bash
#!/bin/bash
#PBS -N JOB_NAME
#PBS -l select=1:ncpus=16:mem=64gb:scratch_local=100gb
#PBS -l walltime=24:00:00
#PBS -j oe
#PBS -M your@email.cz
#PBS -m bae

# 1. Catch unexpected termination (out of walltime, qdel) to save data
trap 'clean_scratch' EXIT
clean_scratch() {
    echo "Job caught signal or exited. Copying outputs..."
    cp -r $SCRATCHDIR/* $PBS_O_WORKDIR/
    rm -rf $SCRATCHDIR/*
}

# 2. Go to submission dir, load modules
cd $PBS_O_WORKDIR
module purge
module add python    # or: vasp, gpaw, psi4, etc.

# 3. Copy inputs to fast local scratch
cp -r ./input_data/* $SCRATCHDIR/
cd $SCRATCHDIR

# 4. Run calculation
export OMP_NUM_THREADS=$PBS_NUM_PPN
python3 run_calc.py > output.log 2>&1

# 5. Copy results back to submission dir
cp -r * $PBS_O_WORKDIR/
```

## Key PBS Variables

| Variable | Meaning |
|----------|---------|
| `$SCRATCHDIR` | Fast local scratch on compute node (auto-created by PBS) |
| `$PBS_O_WORKDIR` | Directory where `qsub` was executed |
| `$PBS_JOBID` | Job ID |
| `$PBS_NUM_PPN` | Number of CPUs allocated |

## Error Code Reference

| Exit Status | Meaning | Action |
|-------------|---------|--------|
| -23 | Missing Kerberos ticket | Re-authenticate (`kinit`) |
| -25 | Exceeded CPU limits | Request more `ncpus` |
| -27 | Out of Memory (OOM) | Increase `mem=` |
| -29 | Walltime exceeded | Resubmit with more walltime or checkpoint |
| 271 | Job killed via `qdel` | Manual termination |

---

# Scratch Workflow (from Paolo's example)

The pattern used in production FireCore fitting jobs:

1. **Check SCRATCHDIR exists** (PBS creates it automatically):
   ```bash
   if [ -z "$SCRATCHDIR" ]; then echo "Error: SCRATCHDIR empty!" >&2; exit 1; fi
   cd $SCRATCHDIR || exit 1
   ```

2. **Load modules and compile in scratch** (fast local I/O):
   ```bash
   module purge
   module load cmake python36-modules
   cp -r $HOME/FireCore FireCore
   cd FireCore/cpp/Build && cmake .. && make
   ```

3. **Copy inputs and data to scratch**:
   ```bash
   cp $PBS_O_WORKDIR/input_files . 
   cp -r $PBS_O_WORKDIR/data_folder .
   ```

4. **Run calculations** (parallel loop over CPU slots with PID tracking)

5. **Copy results back** to `$PBS_O_WORKDIR`

6. **Clean up scratch** before exit:
   ```bash
   rm -rf $SCRATCHDIR/*
   ```

See full example: `Metacentrum_exmaples/Paolo_scratch_example.sh`

---

# Module System

```bash
module avail *vasp*       # search for available software
module avail *python*
module add vasp/6.4.2     # load specific version
module add python gpaw    # load multiple
module purge              # clear all loaded modules
module list               # show currently loaded
```

Common chemistry software: `vasp`, `gpaw`, `psi4`, `python` (with PySCF via pip/conda)

---

# Code-Specific Tips

## PySCF
- Load: `module add python` (install pyscf via pip/conda)
- Save checkpoints: `mf.chkfile = 'calc.chk'`
- For large systems: use density fitting to reduce memory
- Set `export OMP_NUM_THREADS=$PBS_NUM_PPN` to avoid thread over-allocation

## GPAW
- Load: `module add gpaw`
- Set `GPAW_SETUP_PATH` for pseudopotentials
- Parallel: `mpirun -np N gpaw-python script.py`
- LCAO mode is much faster than PW for molecules

## VASP
- Load: `module add vasp/6.x.x`
- Input files: `POSCAR`, `POTCAR`, `INCAR`, `KPOINTS`
- Run: `mpirun -np N vasp_std` (or `vasp_gam` for Gamma-only)
- Always save `WAVECAR`/`CHGCAR` for restart (`ISTART=1` in INCAR)
- Check for existing checkpoints before writing new PBS script

## Psi4
- Load: `module add psi4`
- Run: `psi4 -n 8 input.in output.out`
- Set `memory 32 GB` in input file to match PBS request

---

# Useful Web Tools

| Tool | URL | Purpose |
|------|-----|---------|
| **PBSmon** | https://metavo.metacentrum.cz/pbsmon2/ | Job/node monitoring, quota, hardware specs |
| **Qsub Assembler** | https://metavo.metacentrum.cz/pbsmon2/qsub_pbspro | GUI form to build valid `qsub` commands, shows free nodes |
| **OpenDemand** | (via PBSmon) | Browser-based file manager, job monitor, interactive terminals, Jupyter |
| **e-INFRA AI Chat** | https://chat.ai.e-infra.cz | LLM chatbot (login with MetaCentrum credentials), can attach logs/files |
| **MetaCentrum Docs** | https://docs.metacentrum.cz/en/docs/welcome | Official docs with AI chat assistant (bottom-right corner) |

---

# Resource Estimation Cheat Sheet

| Software | Memory estimate | Typical cores | Notes |
|----------|----------------|---------------|-------|
| PySCF | ~2GB per 100 basis functions | 4-16 | Density fitting reduces memory |
| VASP | ~1GB/atom | 16-64 | Save WAVECAR for restart |
| GPAW | ~4GB/100 atoms (PW) | 8-32 | LCAO mode uses less memory |
| Psi4 | ~2-4GB per 100 basis functions | 8-16 | Set memory in input file |

---

# Monitoring & Babysitting Jobs

## Manual checking
```bash
qstat -u prokop                          # job status
cat my_job.oJOBID                        # stdout
cat my_job.eJOBID                        # stderr
```

## Crash detection patterns
- **Segmentation fault** → check memory, array bounds
- **Energy not converging / Convergence failure** → SCF issue, adjust parameters
- **Walltime exceeded** → resubmit with checkpoint + more walltime
- **Out of memory** → increase `mem=` in PBS script

## Resident monitor (for AI agents)
Run a lightweight Python daemon in `tmux` on the frontend (or use `oven.metacentrum.cz` for long-running control jobs up to 1 month walltime):
- Polls `qstat` every 5-10 minutes
- Detects finished jobs, checks `.o`/`.e` files for errors
- Can auto-resubmit failed jobs with configurable max retries
- Saves state to JSON for tracking across restarts
