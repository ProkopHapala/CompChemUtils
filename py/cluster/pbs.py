"""
cluster/pbs.py — PBS job script generation for Metacentrum (LUNA).
"""

import os
from typing import List, Optional
from .resources import ResourceSpec


def write_pbs_script(job_name: str, commands: List[str], resources: ResourceSpec,
                     outdir: str, modules: Optional[List[str]] = None,
                     script_name: str = 'job.pbs') -> str:
    """Write a PBS job script.

    Parameters
    ----------
    job_name   : PBS job name
    commands   : shell commands to execute in the job
    resources  : ResourceSpec instance
    outdir     : directory to write the script into
    modules    : list of module names to load (module load ...)
    script_name: output filename (default job.pbs)

    Returns
    -------
    Absolute path to the written script.
    """
    os.makedirs(outdir, exist_ok=True)
    fpath = os.path.join(outdir, script_name)

    with open(fpath, 'w') as f:
        f.write("#!/bin/bash\n")
        f.write(f"#PBS -N {job_name}\n")
        f.write(f"#PBS -l nodes={resources.n_nodes}:ppn={resources.n_cores}")
        if resources.gpu and resources.n_gpu > 0:
            f.write(f":gpus={resources.n_gpu}")
        f.write("\n")
        f.write(f"#PBS -l mem={resources.mem_mb()}mb\n")
        f.write(f"#PBS -l walltime={resources.walltime_str()}\n")
        if resources.queue:
            f.write(f"#PBS -q {resources.queue}\n")
        for extra in resources.extra:
            f.write(f"#PBS {extra}\n")
        f.write("\n")
        f.write("cd $PBS_O_WORKDIR\n\n")
        if modules:
            for mod in modules:
                f.write(f"module load {mod}\n")
            f.write("\n")
        for cmd in commands:
            f.write(cmd + "\n")

    return os.path.abspath(fpath)


def write_array_pbs(job_name: str, job_dirs: List[str], run_cmd: str,
                    resources: ResourceSpec, outdir: str,
                    modules: Optional[List[str]] = None,
                    script_name: str = 'array_job.pbs') -> str:
    """Write a PBS array job that runs run_cmd in each of job_dirs.

    job_dirs[i] is selected via PBS_ARRAYID.
    """
    os.makedirs(outdir, exist_ok=True)
    fpath = os.path.join(outdir, script_name)
    n = len(job_dirs)

    # write the directory list file
    listfile = os.path.join(outdir, 'job_dirs.txt')
    with open(listfile, 'w') as lf:
        for d in job_dirs:
            lf.write(d + "\n")

    with open(fpath, 'w') as f:
        f.write("#!/bin/bash\n")
        f.write(f"#PBS -N {job_name}\n")
        f.write(f"#PBS -J 0-{n-1}\n")
        f.write(f"#PBS -l nodes=1:ppn={resources.n_cores}")
        if resources.gpu and resources.n_gpu > 0:
            f.write(f":gpus={resources.n_gpu}")
        f.write("\n")
        f.write(f"#PBS -l mem={resources.mem_mb()}mb\n")
        f.write(f"#PBS -l walltime={resources.walltime_str()}\n")
        if resources.queue:
            f.write(f"#PBS -q {resources.queue}\n")
        for extra in resources.extra:
            f.write(f"#PBS {extra}\n")
        f.write("\n")
        f.write("cd $PBS_O_WORKDIR\n")
        if modules:
            for mod in modules:
                f.write(f"module load {mod}\n")
        f.write(f"\nDIR=$(sed -n \"${{PBS_ARRAY_INDEX}}p\" {listfile})\n")
        f.write("cd $DIR\n")
        f.write(run_cmd + "\n")

    return os.path.abspath(fpath)
