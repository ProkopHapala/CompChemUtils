# MetaCentrum PBS Job Submission Skill
# For AI agents: Hermes, Devin, OpenCode, Antigravity, Claude Code
# Target: MetaCentrum Czech National Grid (OpenPBS)
# Last updated: 2026-06-06

## System Architecture
- **Frontends** (login nodes): tarkil.metacentrum.cz, skirit.ics.muni.cz, alfrid.meta.zcu.cz, etc.
- **Scheduler**: OpenPBS (NOT Slurm - do not use sbatch/squeue)
- **Storage**: NFS home directories, local scratch on compute nodes
- **OS**: Debian Linux
- **Modules**: Environment modules system (module add/load/avail)

## Critical Rules
1. NEVER run computations on frontends - only job preparation and submission
2. ALWAYS use scratch_local for I/O intensive jobs
3. ALWAYS copy results back to home before job ends
4. ALWAYS call clean_scratch at the end
5. Use qsub for submission, qstat for monitoring, qdel for deletion

## SSH Connection Template
```bash
ssh username@tarkil.metacentrum.cz
# or any frontend closer to your location
```

## Basic PBS Job Script Template
```bash
#!/bin/bash
#PBS -N job_name
#PBS -l walltime=HH:MM:SS
#PBS -l select=1:ncpus=N:mem=Xgb:scratch_local=Ygb
#PBS -m abe
#PBS -M your_email@institution.cz

echo "Job started at: $(date)"
echo "Running on host: $(hostname)"
echo "Job ID: $PBS_JOBID"
echo "Scratch dir: $SCRATCHDIR"

# Load required modules
module add python
# module add vasp
# module add gpaw

# Copy inputs to scratch
cp $PBS_O_WORKDIR/input.* $SCRATCHDIR/
cd $SCRATCHDIR

# Run calculation
python script.py > output.log 2>&1

# Copy outputs back
cp output.log $PBS_O_WORKDIR/
cp results.* $PBS_O_WORKDIR/

# Cleanup
clean_scratch
```

## Resource Request Syntax
- `select=1:ncpus=4:mem=8gb:scratch_local=10gb` - 1 node, 4 CPUs, 8GB RAM, 10GB scratch
- `walltime=24:00:00` - 24 hours max
- `scratch_local` is fast local SSD on compute node
- `scratch_shared` for shared network storage (slower)

## Essential PBS Commands
| Command | Purpose |
|---------|---------|
| `qsub script.sh` | Submit job |
| `qstat -u username` | List your running/queued jobs |
| `qstat -x -u username` | List all jobs including finished |
| `qdel JOBID` | Delete/cancel job |
| `qstat -f JOBID` | Full job details |
| `pbsnodes -a` | List all nodes (admin only) |
| `qsub -I -l ...` | Interactive job |

## Job States
- Q = Queued
- R = Running
- F = Finished
- E = Exiting
- H = Held

## Environment Variables
- `$PBS_JOBID` - Job identifier
- `$PBS_O_WORKDIR` - Directory where qsub was called
- `$SCRATCHDIR` - Local scratch directory on compute node
- `$PBS_NODEFILE` - File containing list of allocated nodes

## Software Modules for Computational Chemistry
```bash
module avail *vasp*      # List VASP versions
module avail *python*     # List Python versions
module avail *gpaw*       # List GPAW versions
module avail *qchem*      # List Q-Chem versions
module add vasp/6.3.0     # Load specific VASP version
module add python/3.11    # Load Python 3.11
module list               # Show loaded modules
```

## Troubleshooting Failed Jobs
1. Check `jobname.eJOBID` for stderr
2. Check `jobname.oJOBID` for stdout
3. Verify module loaded correctly: `module list`
4. Check resource limits: `qstat -f JOBID | grep resources_used`
5. Verify input files exist and are readable
6. Check scratch space usage: `du -sh $SCRATCHDIR`

## Advanced: Job Arrays
```bash
#PBS -J 1-100
# Use $PBS_ARRAY_INDEX for parameter sweep
```

## Advanced: GPU Jobs
```bash
#PBS -l select=1:ncpus=4:ngpus=1:mem=16gb:scratch_local=10gb
#PBS -q gpu
```
