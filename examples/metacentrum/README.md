# metacentrum

Metacentrum (Czech national HPC) helpers: PBS job monitoring, AI-agent integration notes, and environment setup — complements `py/cluster/` (script generation) with operational runbooks.

- **metacentrum_monitor.py** — poll PBS queue, detect failed jobs, optional recovery hooks; cron/tmux daemon on frontend node
- **setup_metacentrum_ai.sh** — shell setup for agent SSH workflows (modules, paths)
- **ai_agent_integration_guide.md** — how agents use `py.cluster.interactive_job` + SSH to compute nodes
- **metacentrum_pbs_skill.md** — PBS directive patterns; **always `#PBS -q luna`** for FZU batch jobs
- **dft_babysitter_skill.md** — long-running DFT job babysitting checklist

Related library code: [`py/cluster/README.md`](/py/cluster/README.md).
