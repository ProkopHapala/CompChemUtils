"""
tasks/bake_jobs.py — Generic infrastructure for baking standalone cluster job scripts.

Given a set of molecules and a backend-specific script template function,
this module handles all the common plumbing:
  - Reading XYZ geometries
  - Boxing molecules with vacuum (for periodic codes)
  - Iterating over charge states (N, N+1, N-1)
  - Writing baked Python scripts + PBS submission scripts
  - Writing post-processing scripts (Fukui grid subtraction)
  - Copying geometries to the output directory

Backend-specific parts (the actual run script content) are provided as
callback functions. This keeps the module backend-agnostic.

Usage example (GPAW):
    from py.tasks.bake_jobs import bake_fukui_jobs, GPAWConfig

    bake_fukui_jobs(
        molecules=MOLECULES,
        geom_dir='geometries',
        out_dir='jobs',
        backend='gpaw',
        bake_run_fn=GPAWConfig.bake_run_script,
        mpi=True,
        mpi_runner='gpaw-python',   # GPAW-specific MPI executable
        module_name='py-gpaw/24.1.0-gcc-10.2.1-fojjhkw',
        params=dict(ecut=500, vacuum=12, xc='PBE'),
    )

Usage example (PySCF):
    bake_fukui_jobs(
        molecules=MOLECULES,
        geom_dir='geometries',
        out_dir='jobs',
        backend='pyscf',
        bake_run_fn=PySCFConfig.bake_run_script,
        mpi=False,                   # PySCF uses OpenMP, not MPI
        module_name='mambaforge',
        params=dict(basis='def2-SVP', xc='PBE', resolution=0.15, margin=4.0),
    )
"""

import os, shutil
import numpy as np
from typing import Dict, List, Tuple, Callable, Optional

B2A = 0.529177210903

# Default charge states for Fukui: (tag, charge)
CHARGE_STATES = [('N', 0), ('A', -1), ('C', 1)]


# ===================== Geometry helpers =====================

def read_xyz(fname) -> Tuple[List[str], np.ndarray]:
    """Read XYZ file, return (symbols, positions_ångström)."""
    with open(fname) as f:
        lines = f.readlines()
    natm = int(lines[0].strip())
    syms, ps = [], []
    for i in range(2, 2 + natm):
        parts = lines[i].split()
        syms.append(parts[0])
        ps.append([float(parts[1]), float(parts[2]), float(parts[3])])
    return syms, np.array(ps)


def box_positions(ps: np.ndarray, vacuum: float) -> Tuple[np.ndarray, np.ndarray]:
    """Center molecule in a periodic box with vacuum padding.
    Returns (boxed_positions, cell_vectors)."""
    rmin = ps.min(axis=0); rmax = ps.max(axis=0)
    extent = rmax - rmin
    cell = extent + 2 * vacuum
    shift = 0.5 * cell - 0.5 * (rmin + rmax)
    return ps + shift, cell


def spin_for_charge(nelec: int, charge: int) -> int:
    """Return spin (nalpha - nbeta) for a given electron count and charge.
    Even electrons -> 0 (singlet), odd -> 1 (doublet)."""
    n = nelec - charge
    return 0 if n % 2 == 0 else 1


# ===================== PBS templates =====================

def bake_pbs(job_prefix: str, mol: str, tag: str, spec: dict,
             script_name: str, module_name: str, scratch_gb: int = 10,
             mpi: bool = False, mpi_runner: str = 'python3',
             omp_threads: Optional[str] = None,
             comment: str = '') -> str:
    """Generate a PBS submission script for one job.

    Parameters
    ----------
    job_prefix   : prefix for job name (e.g. 'fukui' or 'pyscf_fukui')
    mol          : molecule name
    tag          : charge state tag ('N', 'A', 'C')
    spec         : dict with 'ncpus', 'mem', 'walltime'
    script_name  : name of the baked script to run (e.g. 'run_H2O_N.py')
    module_name  : module to load (e.g. 'gpaw', 'mambaforge')
    scratch_gb   : scratch_local size in GB
    mpi          : if True, run via 'mpirun -np $PBS_NUM_PPN <mpi_runner> <script>'
    mpi_runner   : executable for MPI runs (e.g. 'gpaw-python' for GPAW, 'python3' for others)
    omp_threads  : OMP_NUM_THREADS value. None=1 (default for MPI),
                   '$PBS_NUM_PPN' for OpenMP parallelism
    comment      : extra comment line in PBS header
    """
    if omp_threads is None:
        omp_threads = '1'
    run_line = f"mpirun -np $PBS_NUM_PPN {mpi_runner} {script_name} 2>&1" if mpi \
        else f"python3 {script_name} 2>&1"
    return f'''#!/bin/bash
#PBS -N {job_prefix}_{mol}_{tag}
#PBS -l select=1:ncpus={spec['ncpus']}:mem={spec['mem']}:scratch_local={scratch_gb}gb
#PBS -l walltime={spec['walltime']}
#PBS -j oe
#PBS -q luna
#PBS -m bae

# {comment}
# {spec['ncpus']} CPUs, {spec['mem']} RAM, {spec['walltime']}

trap 'cp -r $SCRATCHDIR/* $PBS_O_WORKDIR/ 2>/dev/null; rm -rf $SCRATCHDIR/* 2>/dev/null' EXIT

cd $PBS_O_WORKDIR
module purge
module add {module_name}
export OMP_NUM_THREADS={omp_threads}

echo "=== {job_prefix}_{mol}_{tag} === $(date)"

cp $PBS_O_WORKDIR/{script_name} $SCRATCHDIR/
cd $SCRATCHDIR
export TMPDIR=$SCRATCHDIR
export TMP=$SCRATCHDIR
export TEMP=$SCRATCHDIR
{run_line}

echo "Finished: $(date)"
cp -r $SCRATCHDIR/results $PBS_O_WORKDIR/ 2>/dev/null
'''


def bake_postprocess_pbs(job_prefix: str, mol: str, results_subdir: str,
                         module_name: str = 'python') -> str:
    """Generate PBS script for post-processing (1 CPU, 15 min, reads .npy files)."""
    return f'''#!/bin/bash
#PBS -N {job_prefix}_{mol}_post
#PBS -l select=1:ncpus=1:mem=4gb:scratch_local=5gb
#PBS -l walltime=00:15:00
#PBS -j oe
#PBS -q luna

trap 'cp -r $SCRATCHDIR/* $PBS_O_WORKDIR/ 2>/dev/null; rm -rf $SCRATCHDIR/* 2>/dev/null' EXIT

cd $PBS_O_WORKDIR
module purge
module add {module_name}
export OMP_NUM_THREADS=1

echo "=== post {mol} === $(date)"

cp $PBS_O_WORKDIR/postprocess_{mol}.py $SCRATCHDIR/
mkdir -p $SCRATCHDIR/results/{results_subdir}
cp $PBS_O_WORKDIR/results/{results_subdir}/rho_*.npy $SCRATCHDIR/results/{results_subdir}/ 2>/dev/null

cd $SCRATCHDIR
python3 postprocess_{mol}.py 2>&1

echo "Finished: $(date)"
cp -r $SCRATCHDIR/results $PBS_O_WORKDIR/ 2>/dev/null
'''


# ===================== Post-processing script =====================

def bake_postprocess_script(mol: str, results_subdir: str) -> str:
    """Generate a post-processing script that reads rho_N/A/C.npy and
    computes Fukui f+, f-, f0. Only needs NumPy."""
    return f'''#!/usr/bin/env python3
"""Post-process {mol}: read rho_N/A/C.npy, compute Fukui f+,f-,f0, save as .npy.
Only needs NumPy. Run after all 3 single-point jobs are done.
"""
import os, numpy as np

OUTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "{results_subdir}")

rho_N = np.load(os.path.join(OUTDIR, 'rho_N.npy'))
rho_A = np.load(os.path.join(OUTDIR, 'rho_A.npy'))
rho_C = np.load(os.path.join(OUTDIR, 'rho_C.npy'))

f_plus  = rho_A - rho_N   # electrophilic: where electron goes
f_minus = rho_N - rho_C   # nucleophilic: where electron leaves
f_zero  = 0.5 * (f_plus + f_minus)

for name, grid in [('fukui_f_plus', f_plus), ('fukui_f_minus', f_minus), ('fukui_f_zero', f_zero)]:
    np.save(os.path.join(OUTDIR, name + '.npy'), grid)
    print(f"  {{name}}: [{{grid.min():.3e}}, {{grid.max():.3e}}]")

print(f"  sum f+ = {{f_plus.sum():.4f}}  sum f- = {{f_minus.sum():.4f}}  (ratio ~1.0 expected)")
print(f"  Done: {{OUTDIR}}")
'''


# ===================== Main orchestration =====================

def bake_fukui_jobs(
    molecules: Dict[str, dict],
    geom_dir: str,
    out_dir: str,
    bake_run_fn: Callable,
    results_subdir_fn: Callable,
    job_prefix: str,
    module_name: str,
    mpi: bool = False,
    mpi_runner: str = 'python3',
    omp_threads: Optional[str] = None,
    scratch_gb: int = 10,
    charge_states: List[Tuple[str, int]] = None,
    params: dict = None,
    box_vacuum: Optional[float] = None,
    verbose: bool = True,
) -> int:
    """Bake standalone single-point scripts + PBS + post-processing for Fukui calculations.

    Parameters
    ----------
    molecules       : {name: {natoms, nelec, ncpus, mem, walltime}}
    geom_dir        : directory containing <mol>.xyz files
    out_dir         : output directory for baked scripts
    bake_run_fn     : callback(mol, syms, ps, tag, charge, spec, params) -> str
                      Returns the content of a standalone Python script.
                      If box_vacuum is set, ps will be boxed positions and
                      params will include 'cell'.
    results_subdir_fn : callback(mol, params) -> str (e.g. "H2O_PBE_500eV")
    job_prefix      : prefix for PBS job names (e.g. 'fukui', 'pyscf_fukui')
    module_name     : module to load in PBS (e.g. 'gpaw', 'mambaforge')
    mpi             : use mpirun in PBS
    mpi_runner      : MPI executable (e.g. 'gpaw-python' for GPAW, 'python3' for others)
    omp_threads     : OMP_NUM_THREADS value
    scratch_gb      : scratch_local size
    charge_states   : list of (tag, charge), default [('N',0),('A',-1),('C',1)]
    params          : dict of backend-specific parameters passed to bake_run_fn
    box_vacuum      : if set, molecule is boxed with this vacuum (for periodic codes)
    verbose         : print progress

    Returns
    -------
    n_scripts : int (number of single-point scripts generated)
    """
    if charge_states is None:
        charge_states = CHARGE_STATES
    if params is None:
        params = {}

    os.makedirs(out_dir, exist_ok=True)
    geom_dst = os.path.join(out_dir, 'geometries')
    os.makedirs(geom_dst, exist_ok=True)

    n_scripts = 0
    for mol, spec in molecules.items():
        xyz_path = os.path.join(geom_dir, f'{mol}.xyz')
        if not os.path.isfile(xyz_path):
            print(f"  WARNING: {xyz_path} not found, skipping {mol}")
            continue
        shutil.copy2(xyz_path, geom_dst)

        syms, ps = read_xyz(xyz_path)
        if box_vacuum is not None:
            ps, cell = box_positions(ps, box_vacuum)
            params['cell'] = cell

        for tag, charge in charge_states:
            py_content = bake_run_fn(mol, syms, ps, tag, charge, spec, params)
            py_name = f'run_{mol}_{tag}.py'
            py_path = os.path.join(out_dir, py_name)
            with open(py_path, 'w') as f: f.write(py_content)
            os.chmod(py_path, 0o755)

            results_sub = results_subdir_fn(mol, params)
            pbs = bake_pbs(job_prefix, mol, tag, spec, py_name, module_name,
                           scratch_gb, mpi, mpi_runner, omp_threads,
                           comment=f"{mol} {tag} (charge={charge})")
            with open(os.path.join(out_dir, f'submit_{mol}_{tag}.pbs'), 'w') as f: f.write(pbs)

            n_scripts += 1
            if verbose:
                spin = spin_for_charge(spec['nelec'], charge)
                print(f"  {mol:12s} {tag}  charge={charge:+d}  spin={spin}  "
                      f"cpus={spec['ncpus']:2d}  mem={spec['mem']:5s}  {spec['walltime']}")

        # Post-processing
        results_sub = results_subdir_fn(mol, params)
        pp = bake_postprocess_script(mol, results_sub)
        with open(os.path.join(out_dir, f'postprocess_{mol}.py'), 'w') as f: f.write(pp)
        os.chmod(os.path.join(out_dir, f'postprocess_{mol}.py'), 0o755)

        pp_pbs = bake_postprocess_pbs(job_prefix, mol, results_sub)
        with open(os.path.join(out_dir, f'submit_{mol}_post.pbs'), 'w') as f: f.write(pp_pbs)

    if verbose:
        print(f"\nGenerated {n_scripts} single-point scripts + {len(molecules)} post-process scripts")
        print(f"\nSubmit all single-points:")
        print(f"  cd {out_dir} && for f in submit_*_N.pbs submit_*_A.pbs submit_*_C.pbs; do qsub $f; done")
        print(f"\nAfter all 3 densities are done, submit post-processing:")
        first_mol = list(molecules.keys())[0]
        print(f"  qsub submit_{first_mol}_post.pbs   # example")

    return n_scripts


# ===================== Vibration job baking =====================

def discover_init_xyz_cases(geom_root: str) -> List[Tuple[str, str]]:
    """Find all init.xyz under geom_root. Returns [(case_id, xyz_path), ...].

    case_id uses '_' instead of '/' (e.g. Si/R3p8 -> Si_R3p8).
    """
    root = os.path.abspath(geom_root)
    cases = []
    for dirpath, _, files in os.walk(root):
        if 'init.xyz' not in files:
            continue
        xyz = os.path.join(dirpath, 'init.xyz')
        rel = os.path.relpath(dirpath, root)
        case_id = rel.replace(os.sep, '_') if rel != '.' else os.path.basename(dirpath)
        cases.append((case_id, xyz))
    return sorted(cases, key=lambda x: x[0])


def vib_resource_spec(natoms: int) -> dict:
    """Heuristic PBS resources for PySCF relax + Hessian."""
    if natoms <= 10:
        return {'ncpus': 4, 'mem': '8gb', 'walltime': '02:00:00', 'scratch_gb': 10}
    if natoms <= 30:
        return {'ncpus': 8, 'mem': '16gb', 'walltime': '06:00:00', 'scratch_gb': 20}
    if natoms <= 60:
        return {'ncpus': 8, 'mem': '32gb', 'walltime': '12:00:00', 'scratch_gb': 30}
    return {'ncpus': 16, 'mem': '64gb', 'walltime': '24:00:00', 'scratch_gb': 50}


def bake_vib_pbs(job_prefix: str, case_id: str, spec: dict, script_name: str,
                 module_name: str = 'mambaforge', scratch_gb: int = 20,
                 omp_threads: str = '$PBS_NUM_PPN', comment: str = '') -> str:
    """PBS script for one standalone vibration job (scratch -> workdir copy-all)."""
    return f'''#!/bin/bash
#PBS -N {job_prefix}_{case_id}
#PBS -l select=1:ncpus={spec['ncpus']}:mem={spec['mem']}:scratch_local={scratch_gb}gb
#PBS -l walltime={spec['walltime']}
#PBS -j oe
#PBS -m ae

# {comment}
# {spec['ncpus']} CPUs, {spec['mem']} RAM, {spec['walltime']}

trap 'echo "[trap] copy scratch -> workdir"; cp -a $SCRATCHDIR/* $PBS_O_WORKDIR/ 2>/dev/null; rm -rf $SCRATCHDIR/* 2>/dev/null' EXIT

if [ -z "$SCRATCHDIR" ]; then echo "Error: run via qsub (SCRATCHDIR empty)" >&2; exit 1; fi

cd $PBS_O_WORKDIR
module purge
module add {module_name}
export OMP_NUM_THREADS={omp_threads}
export PYTHONUNBUFFERED=1

echo "=== {job_prefix}_{case_id} === $(date)  OMP=$OMP_NUM_THREADS"

cp $PBS_O_WORKDIR/{script_name} $SCRATCHDIR/
cd $SCRATCHDIR
python3 {script_name} 2>&1 | tee run.log

echo "Finished: $(date)"
'''


def bake_vibration_jobs(
    cases: List[Tuple[str, str]],
    out_dir: str,
    bake_run_fn: Callable,
    job_prefix: str = 'pyscf_vib',
    module_name: str = 'mambaforge',
    omp_threads: str = '$PBS_NUM_PPN',
    params: dict = None,
    verbose: bool = True,
) -> int:
    """Bake standalone relax+vib Python scripts + PBS for each case.

    cases: list of (case_id, xyz_path) from discover_init_xyz_cases()
    bake_run_fn: (case_id, syms, ps, spec, params) -> python script source
    """
    if params is None:
        params = {}
    os.makedirs(out_dir, exist_ok=True)
    geom_dst = os.path.join(out_dir, 'geometries')
    os.makedirs(geom_dst, exist_ok=True)
    pbs_paths = []

    for case_id, xyz_path in cases:
        syms, ps = read_xyz(xyz_path)
        spec = vib_resource_spec(len(syms))
        dst_xyz = os.path.join(geom_dst, f'{case_id}.xyz')
        shutil.copy2(xyz_path, dst_xyz)

        py_content = bake_run_fn(case_id, syms, ps, spec, params)
        py_name = f'run_{case_id}.py'
        py_path = os.path.join(out_dir, py_name)
        with open(py_path, 'w') as f:
            f.write(py_content)
        os.chmod(py_path, 0o755)

        pbs = bake_vib_pbs(job_prefix, case_id, spec, py_name, module_name,
                           scratch_gb=spec['scratch_gb'], omp_threads=omp_threads,
                           comment=f'{case_id} natoms={len(syms)}')
        pbs_path = os.path.join(out_dir, f'submit_{case_id}.pbs')
        with open(pbs_path, 'w') as f:
            f.write(pbs)
        os.chmod(pbs_path, 0o755)
        pbs_paths.append(pbs_path)

        if verbose:
            print(f"  {case_id:20s}  natoms={len(syms):3d}  cpus={spec['ncpus']:2d}  "
                  f"mem={spec['mem']:5s}  {spec['walltime']}")

    submit_all = os.path.join(out_dir, 'submit_all.sh')
    with open(submit_all, 'w') as f:
        f.write('#!/bin/bash\n# Submit all PySCF vibration jobs\nset -euo pipefail\n')
        for p in pbs_paths:
            f.write(f'qsub {os.path.basename(p)}\n')
    os.chmod(submit_all, 0o755)

    if verbose:
        print(f"\nGenerated {len(cases)} scripts in {out_dir}")
        print(f"  cd {out_dir} && bash submit_all.sh")
    return len(cases)
