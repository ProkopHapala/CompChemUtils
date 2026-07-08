# cluster

HPC job plumbing for PBS clusters (Metacentrum LUNA) — resource specs, script generation, and interactive-session environment capture for remote SSH workflows.

- **resources.py** — `ResourceSpec` dataclass (cores, nodes, RAM, walltime, GPU, queue) with PBS formatting helpers (`walltime_str`, `mem_mb`)
- **pbs.py** — PBS job script writer (`write_pbs_script`, `write_array_pbs`) from `ResourceSpec` + shell command list
- **interactive_job.py** — parse `qstat -f JOBID`, extract compute node and PBS env vars to `job_env.json` / `job_env.sh` for agent/SSH use (`python3 -m py.cluster.interactive_job JOBID`)
- **__init__.py** — exports `ResourceSpec`, `parse_qstat`, `extract_node`, `extract_variables`
