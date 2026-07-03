#!/usr/bin/env python3
"""
cluster/interactive_job.py — Extract PBS interactive job environment for SSH access to compute node.

When you run `qsub -I` in one terminal, PBS sets environment variables (SCRATCHDIR, PBS_O_WORKDIR, etc.)
only in that shell. This script parses `qstat -f JOBID` output, extracts the compute node hostname
and all PBS variables, and writes them to:
  - JSON file (machine-readable, for AI agents)
  - shell source file (sourceable in SSH sessions to the compute node)

Usage:
    python3 -m py.cluster.interactive_job JOBID [--outdir DIR]
    python3 py/cluster/interactive_job.py JOBID [--outdir DIR]

Example workflow:
    # Terminal 1 (user): start interactive job
    qsub -I -q luna -l walltime=02:00:00 -l select=1:ncpus=1:mem=2gb

    # Terminal 2 (agent): extract env, then SSH to compute node
    python3 py/cluster/interactive_job.py 21824758
    # → writes job_env.json and job_env.sh in current dir
    # → prints: NODE=luna106

    ssh luna106 'source /storage/praha1/home/prokop/git/CompChemUtils/job_env.sh && \
                 module add py-gpaw/24.1.0-gcc-10.2.1-fojjhkw && \
                 python3 script.py'
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

# Variables to export in the shell file (skip PBS_O_PATH to avoid breaking module system)
SKIP_VARS = {'PBS_O_PATH'}

# Variables that are useful and should be extracted
USEFUL_VARS = [
    'SCRATCHDIR', 'SCRATCH', 'SINGULARITY_TMPDIR', 'SINGULARITY_CACHEDIR',
    'PBS_O_WORKDIR', 'PBS_O_HOME', 'PBS_O_SHELL', 'PBS_O_QUEUE', 'PBS_O_HOST',
    'PBS_JOBID', 'PBS_NUM_PPN', 'PBS_NCPUS', 'PBS_NGPUS', 'PBS_NUM_NODES',
    'PBS_RESC_MEM', 'PBS_RESC_TOTAL_MEM', 'PBS_RESC_TOTAL_PROCS',
    'PBS_RESC_TOTAL_WALLTIME', 'TORQUE_RESC_MEM', 'TORQUE_RESC_PROC',
    'TORQUE_RESC_TOTAL_MEM', 'TORQUE_RESC_TOTAL_PROCS', 'TORQUE_RESC_TOTAL_WALLTIME',
    'SCRATCH_VOLUME', 'PBS_RESC_SCRATCH_VOLUME', 'TORQUE_RESC_SCRATCH_VOLUME',
    'SCRATCH_TYPE', 'PBS_RESC_TOTAL_SCRATCH_VOLUME', 'TORQUE_RESC_TOTAL_SCRATCH_VOLUME',
]


def parse_qstat(jobid: str) -> dict:
    """Run `qstat -f JOBID` and parse output into a dict of fields."""
    result = subprocess.run(['qstat', '-f', jobid], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ERROR: qstat -f {jobid} failed (exit {result.returncode})", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(1)

    raw = result.stdout
    fields = {}
    current_key = None
    current_val = []

    for line in raw.splitlines():
        stripped = line.strip()
        # New field: indented with 4 spaces (not tab), contains '='
        if line.startswith('    ') and not line.startswith('\t') and '=' in stripped:
            if current_key:
                fields[current_key] = ' '.join(current_val).strip()
            key, val = stripped.split('=', 1)
            current_key = key.strip()
            current_val = [val.strip()]
        elif stripped == '' and current_key:
            fields[current_key] = ' '.join(current_val).strip()
            current_key = None
            current_val = []
        elif current_key and line.startswith('\t'):
            # Continuation line (tab-indented in qstat output)
            current_val.append(stripped)

    if current_key:
        fields[current_key] = ' '.join(current_val).strip()

    return fields


def extract_node(fields: dict) -> str:
    """Extract compute node hostname from exec_host field.

    exec_host format: 'luna106/6' or 'luna106.fzu.cz:15002/6'
    """
    exec_host = fields.get('exec_host', '')
    if not exec_host:
        print("ERROR: no exec_host field found — job may not be running yet", file=sys.stderr)
        sys.exit(1)

    # Take first entry before '/' or ':'
    node = re.split(r'[/:(]', exec_host.strip())[0]
    return node.strip()


def extract_variables(fields: dict) -> dict:
    """Parse Variable_List from qstat output into a dict of key=value pairs."""
    var_str = fields.get('Variable_List', '')
    if not var_str:
        return {}

    # Variable_List is comma-separated key=value, but values may contain commas
    # in paths — so we split on commas that are followed by a KEY= pattern
    # Strategy: split on commas, then re-join fragments that don't contain '='
    parts = var_str.replace('\n', ' ').strip().split(',')
    pairs = []
    buf = ''
    for part in parts:
        part = part.strip()
        if '=' in part and buf == '':
            buf = part
        elif '=' in part and buf:
            # New key=value starts here — but check if this is actually a new key
            # PBS variable names are uppercase with underscores
            if re.match(r'^[A-Z_]+=', part):
                pairs.append(buf)
                buf = part
            else:
                buf += ',' + part
        else:
            buf += ',' + part
    if buf:
        pairs.append(buf)

    variables = {}
    for pair in pairs:
        if '=' in pair:
            key, val = pair.split('=', 1)
            key = key.strip()
            val = val.strip()
            if key in USEFUL_VARS and key not in SKIP_VARS:
                variables[key] = val

    return variables


def write_json(variables: dict, node: str, jobid: str, outpath: Path):
    """Write JSON file with job info."""
    data = {
        'jobid': jobid,
        'node': node,
        'variables': variables,
    }
    with open(outpath, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"JSON: {outpath}")


def write_shell(variables: dict, node: str, jobid: str, outpath: Path):
    """Write sourceable shell script that exports PBS variables + module init."""
    lines = [
        f"# Auto-generated from qstat -f {jobid}",
        f"# Source this on the compute node ({node}) to restore PBS environment",
        f"# Usage: ssh {node} 'source {outpath} && module add ... && python3 script.py'",
        "",
        "# Module system init (not available in non-interactive SSH by default)",
        "source /cvmfs/software.metacentrum.cz/modulefiles/5.3.1/loadmodules",
        "",
        f"export PBS_JOBID={jobid}",
    ]
    for key, val in sorted(variables.items()):
        # Quote values that may contain spaces or special chars
        if any(c in val for c in ' \t"\'$()'):
            lines.append(f'export {key}="{val}"')
        else:
            lines.append(f'export {key}={val}')

    with open(outpath, 'w') as f:
        f.write('\n'.join(lines) + '\n')
    print(f"SHELL: {outpath}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    jobid = sys.argv[1]
    outdir = Path('.')
    if '--outdir' in sys.argv:
        idx = sys.argv.index('--outdir')
        outdir = Path(sys.argv[idx + 1])
    outdir = outdir.resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    fields = parse_qstat(jobid)

    if fields.get('job_state') != 'R':
        print(f"ERROR: job {jobid} state is '{fields.get('job_state', '?')}', not 'R' (running)", file=sys.stderr)
        sys.exit(1)

    node = extract_node(fields)
    variables = extract_variables(fields)

    json_path = outdir / 'job_env.json'
    sh_path = outdir / 'job_env.sh'

    write_json(variables, node, jobid, json_path)
    write_shell(variables, node, jobid, sh_path)

    print(f"NODE={node}")
    print(f"JOBID={jobid}")
    print(f"\nNow run commands on the compute node:")
    print(f"  ssh {node} 'source {sh_path} && module add py-gpaw/24.1.0-gcc-10.2.1-fojjhkw && python3 script.py'")


if __name__ == '__main__':
    main()
