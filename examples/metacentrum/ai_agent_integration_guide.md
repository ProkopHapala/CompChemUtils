# AI Agent Integration Guide for MetaCentrum HPC
# How to use Hermes, Devin, OpenCode, Antigravity with MetaCentrum
# Last updated: 2026-06-06

## Overview

This guide explains how to configure AI coding agents (Hermes, Devin, OpenCode, Antigravity, Claude Code) to efficiently manage computational chemistry workflows on MetaCentrum. The agents connect via SSH from your local machine and use skill files to understand the PBS environment.

## Architecture

```
Your Local Machine (AI Agent runs here)
    |
    | SSH (with key auth)
    v
MetaCentrum Frontend (tarkil.metacentrum.cz)
    |
    | qsub / qstat / qdel
    v
MetaCentrum Compute Nodes (OpenPBS)
```

## 1. SSH Setup for AI Agents

### Generate dedicated SSH key (recommended)
```bash
ssh-keygen -t ed25519 -f ~/.ssh/metacentrum_ai -C "ai-agent@yourmachine"
ssh-copy-id -i ~/.ssh/metacentrum_ai.pub username@tarkil.metacentrum.cz
```

### Configure SSH for persistent connections
Add to `~/.ssh/config`:
```
Host metacentrum-ai
    HostName tarkil.metacentrum.cz
    User YOUR_USERNAME
    IdentityFile ~/.ssh/metacentrum_ai
    ServerAliveInterval 60
    ServerAliveCountMax 3
    ControlMaster auto
    ControlPath ~/.ssh/control-%r@%h:%p
    ControlPersist 4h
```

### Test connection
```bash
ssh metacentrum-ai "qstat -u YOUR_USERNAME"
```

## 2. Skill Files Setup for Each Agent

### OpenCode
Place skill files in `.opencode/skills/` or reference them in `.opencode/config`:
```json
{
  "skills": [
    "metacentrum_pbs_skill.md",
    "dft_babysitter_skill.md"
  ],
  "system_prompt": "You are an HPC workflow assistant. Always use PBS for MetaCentrum. Never run computations on frontends."
}
```

### Claude Code
Create `.claude/CLAUDE.md` in your project:
```markdown
# HPC Workflow Context
- System: MetaCentrum (OpenPBS)
- Frontend: tarkil.metacentrum.cz
- Codes: PySCF, GPAW, VASP, Psi4
- Always: use qsub, copy to scratch, clean_scratch
- Never: run calculations on frontend
```

### Antigravity (Google)
Use the Manager view to spawn agents for different tasks:
- Agent 1: Job preparation and submission
- Agent 2: Output analysis and convergence checking
- Agent 3: Error recovery and resubmission

Upload skill files to the knowledge base for each agent.

### Devin (Cognition)
Configure Devin with:
- SSH credentials for MetaCentrum
- Access to skill files in repository
- Custom tools for `qsub`, `qstat`, `qdel`

### Hermes
If using a local Hermes instance, configure MCP (Model Context Protocol) tools:
```json
{
  "tools": [
    {
      "name": "qsub",
      "command": "ssh metacentrum-ai qsub"
    },
    {
      "name": "qstat", 
      "command": "ssh metacentrum-ai qstat"
    }
  ]
}
```

## 3. Workflow Patterns

### Pattern A: Agent Prepares, You Submit
1. Agent writes PBS script and input files locally
2. Agent uses SCP to transfer to MetaCentrum
3. You review and run `qsub` manually
4. Agent monitors via SSH and reports status

### Pattern B: Full Agent Autonomy (with guardrails)
1. Agent has SSH access to frontend
2. Agent prepares, submits, and monitors jobs
3. Agent reads output files and decides next steps
4. You review artifacts (plans, screenshots, logs)

### Pattern C: Batch Workflow Automation
1. Agent creates parameter sweep (e.g., 50 geometries)
2. Agent generates job array script
3. Agent submits and monitors array
4. Agent collects results and generates summary

## 4. Resident Monitoring Setup

### Option 1: Cron (simplest)
```bash
# Edit crontab: crontab -e
*/10 * * * * /usr/bin/python3 /path/to/metacentrum_monitor.py --user YOUR_USERNAME --frontend tarkil.metacentrum.cz >> /path/to/monitor.log 2>&1
```

### Option 2: Systemd Service
Create `~/.config/systemd/user/metacentrum-monitor.service`:
```ini
[Unit]
Description=MetaCentrum Job Monitor
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /path/to/metacentrum_monitor.py --user YOUR_USERNAME --frontend tarkil.metacentrum.cz --daemon --interval 300
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
```

Enable and start:
```bash
systemctl --user daemon-reload
systemctl --user enable metacentrum-monitor
systemctl --user start metacentrum-monitor
```

### Option 3: Tmux Session (for interactive monitoring)
```bash
tmux new-session -d -s mc-monitor "python3 metacentrum_monitor.py --user YOUR_USERNAME --frontend tarkil.metacentrum.cz --daemon --interval 300"
# Reattach: tmux attach -t mc-monitor
```

## 5. Agent-Specific Tips

### For Terminal-Based Agents (OpenCode, Claude Code)
- Use `ssh metacentrum-ai` as a single command prefix
- Create shell aliases: `alias mc-qstat='ssh metacentrum-ai qstat -u YOUR_USERNAME'`
- Use `scp` for file transfers
- Leverage `rsync` for large dataset synchronization

### For IDE-Based Agents (Antigravity, Cursor)
- Mount remote filesystem via SSHFS for file browsing:
  ```bash
  sshfs metacentrum-ai:/home/YOUR_USERNAME ~/meta-remote
  ```
- Agent can read/write files as if local
- Use terminal integration for PBS commands

### For Autonomous Agents (Devin, Hermes)
- Provide explicit guardrails in system prompt
- Limit SSH scope: use dedicated key, restrict commands if possible
- Implement approval gates for destructive actions (qdel, rm -rf)
- Use the monitor script for oversight rather than direct agent monitoring

## 6. Security Considerations

1. **Dedicated SSH key**: Never use your primary MetaCentrum credentials
2. **Key restrictions**: Consider using `command="..."` in authorized_keys to restrict agent capabilities
3. **No sudo**: Agent should never need or have sudo access
4. **Audit logging**: Monitor what commands the agent executes
5. **Rate limiting**: Don't let agent spam qstat (every 30s is reasonable)
6. **Frontend etiquette**: Agent should not run heavy commands on frontends

## 7. Troubleshooting Agent-HPC Integration

### Problem: Agent can't connect via SSH
- Solution: Verify key permissions (600), test manually, check firewall

### Problem: Agent submits jobs but they fail immediately
- Solution: Check module loading, verify input files copied to scratch, review .eJOBID files

### Problem: Agent can't parse qstat output
- Solution: Use `qstat -x -f -F json` for structured output (if available) or provide parsing examples in skill file

### Problem: Agent runs commands on frontend instead of compute nodes
- Solution: Reinforce in system prompt: "ALWAYS use qsub for calculations. Frontends are for job management ONLY."

### Problem: Jobs run out of walltime
- Solution: Teach agent to estimate walltime from previous similar jobs, use checkpointing

## 8. Example Agent Conversation Flow

**User**: "Run a B3LYP/6-31G* calculation on benzene using PySCF"

**Agent**:
1. Writes `benzene.py` input file
2. Writes `benzene_pbs.sh` PBS script with proper resources
3. SCPs files to MetaCentrum home directory
4. SSHs to frontend and runs `qsub benzene_pbs.sh`
5. Reports job ID and estimated start time
6. (After interval) Checks `qstat` and reports job is running
7. (After completion) SCPs output back, reports energy and convergence status
8. Suggests next steps (frequency calculation, larger basis set, etc.)

## 9. Recommended File Structure

```
~/meta-workflows/
├── skills/
│   ├── metacentrum_pbs_skill.md
│   └── dft_babysitter_skill.md
├── scripts/
│   ├── metacentrum_monitor.py
│   └── submit_template.sh
├── inputs/
│   └── (your calculation inputs)
└── outputs/
    └── (downloaded results)
```
