# DFT Calculation Babysitter Skill
# For AI agents managing quantum chemistry calculations on MetaCentrum
# Codes: PySCF, GPAW, VASP, PS4 (Psi4)
# Last updated: 2026-06-06

## Pre-Flight Checklist (Before Job Submission)
1. **Input validation**: Verify geometry files, basis sets, functional names
2. **Resource estimation**: 
   - VASP: ~1GB RAM per atom for standard DFT
   - PySCF: ~2GB RAM per 100 basis functions for HF/DFT
   - GPAW: ~0.5GB RAM per atom for LCAO mode
3. **Walltime estimation**: Use previous similar calculations as reference
4. **Scratch space**: Ensure 2-3x the expected output size
5. **Module compatibility**: Check if required modules exist and load without conflict

## Code-Specific Setup

### PySCF
```bash
#!/bin/bash
#PBS -N pyscf_calc
#PBS -l walltime=12:00:00
#PBS -l select=1:ncpus=8:mem=32gb:scratch_local=20gb

module add python/3.11
module add pyscf

# Or use conda environment if available
# source /path/to/conda/bin/activate pyscf_env

cd $SCRATCHDIR
cp $PBS_O_WORKDIR/*.py $SCRATCHDIR/
cp $PBS_O_WORKDIR/*.xyz $SCRATCHDIR/

python calculation.py > pyscf.log 2>&1

# Check convergence
grep "converged" pyscf.log || echo "WARNING: SCF may not have converged"

cp pyscf.log $PBS_O_WORKDIR/
cp *.chk $PBS_O_WORKDIR/ 2>/dev/null
clean_scratch
```

### GPAW
```bash
#!/bin/bash
#PBS -N gpaw_calc
#PBS -l walltime=24:00:00
#PBS -l select=1:ncpus=16:mem=64gb:scratch_local=50gb

module add gpaw
module add python/3.11

export GPAW_SETUP_PATH=/path/to/potentials

cd $SCRATCHDIR
cp $PBS_O_WORKDIR/*.py $SCRATCHDIR/

mpirun -np 16 gpaw-python calculation.py > gpaw.log 2>&1

cp gpaw.log $PBS_O_WORKDIR/
cp *.gpw $PBS_O_WORKDIR/
clean_scratch
```

### VASP
```bash
#!/bin/bash
#PBS -N vasp_calc
#PBS -l walltime=48:00:00
#PBS -l select=1:ncpus=24:mem=96gb:scratch_local=100gb

module add vasp/6.4.0

# VASP expects specific input filenames
cd $SCRATCHDIR
cp $PBS_O_WORKDIR/POSCAR $SCRATCHDIR/
cp $PBS_O_WORKDIR/POTCAR $SCRATCHDIR/
cp $PBS_O_WORKDIR/INCAR $SCRATCHDIR/
cp $PBS_O_WORKDIR/KPOINTS $SCRATCHDIR/

# Run VASP with MPI
mpirun -np 24 vasp_std > vasp.out 2>&1

# Check for convergence
grep "reached required accuracy" OUTCAR && echo "Converged" || echo "NOT converged"

cp OUTCAR $PBS_O_WORKDIR/
cp vasprun.xml $PBS_O_WORKDIR/
cp CHGCAR $PBS_O_WORKDIR/ 2>/dev/null
cp WAVECAR $PBS_O_WORKDIR/ 2>/dev/null
clean_scratch
```

### Psi4 (PS4)
```bash
#!/bin/bash
#PBS -N psi4_calc
#PBS -l walltime=12:00:00
#PBS -l select=1:ncpus=8:mem=32gb:scratch_local=20gb

module add psi4

cd $SCRATCHDIR
cp $PBS_O_WORKDIR/*.in $SCRATCHDIR/

psi4 -n 8 input.in output.out > psi4.log 2>&1

cp output.out $PBS_O_WORKDIR/
cp psi4.log $PBS_O_WORKDIR/
clean_scratch
```

## Crash Detection & Recovery

### Common Failure Patterns
1. **SCF convergence failure**: Increase MAXCYCLE, use different guess, or level shifting
2. **Memory overflow**: Request more memory or use density fitting
3. **Walltime exceeded**: Job killed by PBS - request more time or checkpoint
4. **Scratch full**: Clean up or request more scratch space
5. **Module not found**: Check `module avail` and use correct module name
6. **MPI errors**: Check node count matches requested CPUs

### Automatic Restart Strategy
```bash
# In job script - check for previous WAVECAR/CHGCAR and restart
if [ -f $PBS_O_WORKDIR/WAVECAR ]; then
    cp $PBS_O_WORKDIR/WAVECAR $SCRATCHDIR/
    # Set ISTART=1 in INCAR for VASP restart
fi
```

### Monitoring During Run (for interactive/debug)
```bash
# On compute node during interactive job:
watch -n 30 "grep 'F=' OSZICAR"  # VASP energy tracking
watch -n 30 "tail -20 pyscf.log" # PySCF progress
watch -n 30 "tail -20 gpaw.log"  # GPAW progress
```

## Post-Calculation Validation
1. Check output files exist and are non-empty
2. Verify energy is reasonable (not NaN, not absurdly large)
3. Check forces are below threshold for geometry optimization
4. Verify symmetry preserved (if requested)
5. Compare with literature values or previous calculations
6. Check for warnings in log files

## Output File Management
- Always save: log files, final geometries, energies
- Consider saving: wavefunctions (WAVECAR, .chk, .gpw) for restart
- Delete: temporary integrals, large scratch files after verification
- Use `tar czf results.tar.gz *.out *.log` for easy transfer
