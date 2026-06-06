
https://gemini.google.com/share/a6c272f42332
https://chat.deepseek.com/share/lx6fgvzyeynj6qbiju
https://www.kimi.com/share/19e9e9e2-33d2-84a5-8000-0000c62064a4

# USER

I wonder how can I efficiently use AI LLM agents like Hermes, devin, opencode, antigravity to prepare submit and control my calculations on MetaCentrum. I can allow them to login via ssh from my computer and prepare some resident Crom so they control if jobs run or crash. I have also problem navigate and configure the system setup 
There are docs. Perhaps it would be good to prepare some skill files to setup jobs with PBS system or slurm and to babysit calculations (typically DFT, pyscf, PS4, gpaw, Vasp)

There are docs 
https://docs.metacentrum.cz/en/docs/welcome

---

# Gemini

Offloading the orchestration of quantum chemistry and molecular dynamics calculations on MetaCentrum to AI agents is a powerful way to eliminate the repetitive friction of cluster management. However, clusters like MetaCentrum present a specific challenge for AI agents: **Kerberos authentication expires, and standard cluster nodes lack outbound internet access.**

To make agents like Hermes, Devin, or local OpenCL/Rust custom agents work efficiently, you need a split architecture: an **Agent Skill Layer** on your local machine and a **Resident Babysitter Daemon** on the cluster frontend.

### 1. The Architecture: Split Local Agent & Cluster Daemon

Because MetaCentrum enforces Kerberos tickets (which expire after 12 hours) and prompts for passwords interactively on command lines if tickets are missing, a standard AI agent running blindly via SSH will constantly break or get stuck on auth prompts.

```
+--------------------------+                 +----------------------------+
|    Local Workstation     |                 |  MetaCentrum Frontend      |
|                          |                 |  (e.g., skirit / tarkil)   |
|  [LLM Agent / Coding]    |  SSH (Keys/Krb) |                            |
|  - Generates inputs      | --------------->|  [Resident Python Daemon]  |
|  - Compiles skill files  |                 |  - Polls `qstat -u`        |
|  - Triggers submissions  |                 |  - Inspects `.e` / `.o`    |
|                          |                 |  - Handles `scratch` fixes |
+--------------------------+                 +----------------------------+

```

### 2. Creating the "Skill Files" for the AI Agent

To train your agent to interact with MetaCentrum's **OpenPBS (PBS Pro)** scheduler, you should supply it with context files (System Prompts or Markdown guides in its workspace) that define MetaCentrum-specific constraints.

Give your agent the following two specifications:

#### Skill A: Standard MetaCentrum PBS Template Generator

Agents often default to basic Slurm scripts. MetaCentrum requires explicit handling of `scratch_local` and the environment. Provide this template to your agent's knowledge base:

```bash
#!/bin/bash
#PBS -N QM_JOB_NAME
#PBS -l select=1:ncpus=16:mem=64gb:scratch_local=100gb
#PBS -l walltime=24:00:00
#PBS -j oe

# 1. Catch unexpected termination (out of walltime, qdel) to save data
trap 'clean_scratch' EXIT

clean_scratch() {
    echo "Job caught signal or exited. Moving remaining outputs..."
    cp -r $SCRATCHDIR/* $PBS_O_WORKDIR/
    rm -rf $SCRATCHDIR/*
}

# 2. Navigate to execution directory and setup scratch
cd $PBS_O_WORKDIR
MODULES_TO_LOAD=("python" "gpaw" "vasp") # Agent modifies this dynamically

for mod in "${MODULES_TO_LOAD[@]}"; do
    module load "$mod"
done

# 3. Copy files to ultra-fast local scratch
cp input.com $SCRATCHDIR/
cd $SCRATCHDIR

# 4. Run execution (Example: PySCF / GPAW / VASP)
# Agent replaces this with the target binary call
python3 execution_script.py > output.log 2>&1

# 5. Clean cleanup happens automatically via trap, but explicit copy minimizes data loss
cp -r * $PBS_O_WORKDIR/

```

#### Skill B: Error Code Dictionary for Agent Diagnostics

When an agent reads the exit state or logs, it needs to know what went wrong. Provide it this mapping:

* **Exit Status -23:** Missing Kerberos ticket inside the job environment.
* **Exit Status -25:** Exceeded allocated CPU limits.
* **Exit Status -27:** Out of Memory (OOM) — need to scale up `mem=`.
* **Exit Status -29:** Walltime exceeded. Agent needs to resubmit a restarted checkpoint with an adjusted walltime limit.
* **Exit Status 271:** Job was manually killed via `qdel`.

### 3. The Resident Babysitter Script (Run as a Cron/Daemon)

Instead of the LLM checking status via continuous SSH shell polling (which drops and hits password walls), your agent should deploy a resident lightweight daemon inside a `tmux` session or via local cron on the frontend.

Here is a structural script your agent can write and monitor to "babysit" your calculations:

```python
#!/usr/bin/env python3
import subprocess
import json
import os
import time
from pathlib import Path

WATCH_DIR = Path("~/metacentrum_watch").expanduser()
WATCH_DIR.mkdir(exist_ok=True)
STATE_FILE = WATCH_DIR / "tracked_jobs.json"

def get_active_jobs():
    """Queries PBS to find currently running or queued jobs."""
    try:
        # Running qstat with JSON or XML parsing flag if available, 
        # or fallback to custom parser
        result = subprocess.run(["qstat", "-u", os.getlogin()], capture_output=True, text=True)
        return result.stdout
    except Exception as e:
        return str(e)

def parse_job_errors(job_id, submit_dir):
    """Inspects the .e files automatically for known convergence failures."""
    stderr_files = list(Path(submit_dir).glob(f"*.e*{job_id}*"))
    if not stderr_files:
        return "No stderr file found yet."
    
    with open(stderr_files[0], 'r') as f:
        content = f.read()
        
    # Heuristics for the agent to consume later
    if "Segmentation fault" in content:
        return "CRASH_SEGFAULT"
    if "Energy not converging" in content or "Convergence failure" in content:
        return "CHEM_CONVERGENCE_FAIL"
    return "UNKNOWN_OR_RUNNING"

def loop_and_report():
    while True:
        raw_jobs = get_active_jobs()
        # Log to file where your local AI agent can read it via an SSH file pull
        with open(WATCH_DIR / "status.log", "w") as f:
            f.write(f"Timestamp: {time.time()}\n")
            f.write(raw_jobs)
        
        # Throttle polling to prevent spamming the cluster management head node
        time.sleep(300) 

if __name__ == "__main__":
    loop_and_report()

```

### 4. Step-by-Step Agent Workflow Setup

Configure your agent to execute the following sequence to automate your computational pipeline:

1. **Establish Persistent SSH Session:** Local Machine.
Set up a ControlMaster configuration in your local `~/.ssh/config` so the agent can reuse an existing Kerberos authentication connection without spawning fresh interactive password challenges.

2. **Generate Structure Inputs via Agent:** Local / Workspace.
Have the agent evaluate your coordinates or molecular files and formulate inputs specific to the driver (e.g., configuring `gth-szv` baselines for PySCF or k-points settings for VASP).

3. **Inject Code Template and Submit:** MetaCentrum Frontend.
The agent pushes scripts to MetaCentrum via `scp` and passes execution to `qsub`. It captures the returned job ID (e.g., `13010171.pbs-m1.metacentrum.cz`).

4. **Automated Verification Loop:** Resident Daemon Context.
The background Python babysitter logs status changes. The local agent pulls `status.log` via the open SSH channel, tracks when state switches from `R` (Running) to `F` (Finished), and automatically initiates convergence check routines if anomalies arise.

### Tips for Specific Software Environments

* **PySCF / GPAW (Python-based):** Ensure your agent includes a step to initialize `module load mambaforge` or sets up an isolated environment on the scratch partition. The agent should pass the environment variables explicitly (`export OMP_NUM_THREADS=$PBS_NUM_PPN`) to prevent parallel Python libraries from over-allocating threads beyond what PBS reserved.
* **VASP:** Have your agent check for the existence of `WAVECAR` or `CHGCAR` checkpoints in the submission directory prior to writing the PBS script. If they exist, the script can automatically copy them *into* the scratch space to allow effortless continuation of interrupted runs.

---

# DeepSeek-V4-flash

Your goal is very advanced and ambitious. It sits right at the crossroads of several cutting-edge fields: autonomous agents, HPC (High-Performance Computing) workload management, and computational science.

Right now, there isn't a single ready-made solution that connects the agents you mentioned directly to MetaCentrum. However, you have a very solid collection of components. The true innovation and value will come from integrating them into a custom system tailored to your specific workflow.

Here’s a breakdown of the available pieces and how you can start assembling them.

### 🎭 Understanding the "Agents"

The agents you've listed are quite distinct, each designed with different primary strengths:

*   **Hermes**: A "self-improving" framework that learns from its history and can create its own tools. It has a significant advantage for your project because it natively supports **SSH** as a backend, meaning it can be configured to log directly into MetaCentrum from your computer.
*   **Devin**: An autonomous agent designed to act like a software engineer. Its framework is built for deep customization using `.devin/` config files, `AGENTS.md` rules, and "Skills".
*   **OpenCode**: A powerful, open-source coding agent known for its extensibility and ability to coordinate teams of specialized sub-agents.
*   **Antigravity**: An environment focused on task delegation, allowing you to spin off long-running jobs (like your calculations) into background agents to manage in parallel.

### 🔧 Practical Guidance for Self-Hosted Agents with SSH

Implementing the "resident cron" concept you're interested in can be done by leveraging built-in features of these frameworks:

*   **Hermes**: This agent has a built-in **cron scheduler**. You can give it natural language instructions like "every day at 2 AM, connect to MetaCentrum via SSH, check the status of my queued jobs, and send me a report".
*   **Devin**: To achieve a similar effect, you would likely combine its scripting capabilities with your computer's native `cron` system.
*   **OpenCode**: Similarly, you can use external schedulers or plugins to trigger OpenCode sessions for periodic monitoring.

### 🤖 Building a Meta-Agent System

Your idea of a "meta-agent" is excellent for orchestrating all the components. One approach is to designate one agent as the "Manager":

1.  **Manager Agent (Central Brain)**: A single Hermes or Devin process that runs continuously, making decisions.
2.  **Worker Sub-Agents**: For specific tasks. For example, OpenCode could spawn a specialized sub-agent to parse `qstat` output, while another analyzes crash logs. Antigravity could similarly create background agents for individual calculations. Hermes can also spawn isolated "subagents" for parallel work.

### 💻 Autonomous Job Management Scripts (The "Skills")

This is where you can truly customize the agent's abilities. You will need to teach it specific "Skills" or "Rules" for MetaCentrum and your software.

#### 1. Core MetaCentrum PBS Commands
Your agent will need to know these essential PBS commands:
*   `qsub`: To submit a new job.
*   `qstat`: To check the status of jobs.
*   `qdel`: To kill a job.
*   `pbsnodes`: To get info about compute nodes and their properties.

#### 2. "Skill" Files to Create
You should prepare structured text files (e.g., `.md` files) for your agent to use as instructions. Here are a few critical ones you can draft:

**`METACENTRUM_SETUP.md`**
This file would teach the agent the initial setup steps on a login node:
*   Load required software modules using `module add`.
*   Navigate to the correct storage directory (e.g., `/storage/...`).
*   Understand data movement: Copy inputs to the job's `$SCRATCHDIR` and results back to your storage.

**`JOB_SUBMISSION_TEMPLATE.pbs`**
This is a template for a PBS submission script. The agent would copy this, fill in the placeholders, and then submit it using `qsub`.
```bash
#!/bin/bash
#PBS -N {JOB_NAME}
#PBS -l select=1:ncpus={CORES}:mem={MEMORY}gb
#PBS -l walltime={WALLTIME}
#PBS -q {QUEUE_NAME}

cd $PBS_O_WORKDIR
# --- Copy input data to scratch ---
cp -r ./input_data/* $SCRATCHDIR/
cd $SCRATCHDIR

# --- Load necessary modules ---
module add {YOUR_SOFTWARE_MODULE}

# --- Run the calculation ---
{YOUR_SOFTWARE_COMMAND} > ${PBS_O_WORKDIR}/output.log

# --- Copy results back ---
cp -r * $PBS_O_WORKDIR/
```

**`MONITORING_CRITERIA.md`**
This file would define the rules for "babysitting". The agent can use this to interpret the output of `qstat` and decide on an action.
*   **Check Frequency**: Check job status every 15 minutes.
*   **OK Conditions**: Job status is `R` (Running) or `Q` (Queued). Walltime is below `X` hours.
*   **CRASH Conditions**: Job status is `E` (Exiting). Job status is `F` (Finished) but exit code != 0. A specific error string appears in the output log (e.g., "Segmentation fault").
*   **Actions**: If CRASH is detected, re-submit the job using a backup input file or with corrected parameters (e.g., `--nodes=2`).

### 📊 Tool Summary & Suggested Starting Point

This table summarizes the key frameworks and HPC tools you'll be working with:

| Agent/Framework | Key Capability | Relevance for Your Goal |
| :--- | :--- | :--- |
| **Hermes** | Self-improving, learns from experience, SSH backend, built-in cron | **Best for the "Manager" role**. Can autonomously learn and optimize the babysitting process. |
| **Devin** | Deeply customizable, custom subagents, rule-based behavior | **Best for structured workflows**. Its rule system is ideal for defining precise job submission and monitoring logic. |
| **OpenCode** | Open-source, multi-agent coordination, extensible | **Best for team-based approaches**. Can coordinate specialized sub-agents for specific software or monitoring tasks. |
| **Antigravity** | Asynchronous background tasks, parallel agent management | **Best for running and monitoring many calculations in parallel** without blocking your primary workflow. |
| **MetaCentrum (PBS)** | MetaCentrum's core scheduler; manage jobs with `qsub`, `qstat`, `qdel` | **The system to master**. Your entire automation revolves around controlling it. |
| **Target Software** | VASP, PySCF, PSI4, GPAW (require specific PBS submission scripts) | **Your final output**. Your agent must generate the correct input files and submit these. |

**My recommendation for a starting point is to first master the basics of MetaCentrum using their own AI support tools to get a feel for the platform before diving into the complexities of agent integration.**

MetaCentrum has integrated an AI chat interface directly into its documentation, with two helpful models:
1.  **Local Search**: Ask specific questions about their internal documentation (e.g., "What are the available storage options?").
2.  **Problem Solver**: Paste error messages or ask for help generating and debugging PBS scripts.

This built-in tool can be a quick way to get custom `qsub` scripts for VASP, GPAW, or PySCF without starting from scratch.

I hope this detailed analysis gives you a clear, actionable path forward. This is a complex but very rewarding project. Please let me know if any of these steps or concepts need more clarification.

---

# Kimi 2.6

I'll help you set up an efficient AI-agent-driven workflow for MetaCentrum. Let me first check the current MetaCentrum documentation and gather relevant information about these AI agents.
Here's a comprehensive guide for efficiently using AI agents with MetaCentrum, plus ready-to-use skill files and monitoring tools.

## MetaCentrum Architecture Overview

MetaCentrum uses **OpenPBS** (not Slurm) as its job scheduler across distributed compute clusters . The ecosystem consists of:

- **Frontends** (login nodes): `tarkil.metacentrum.cz`, `skirit.ics.muni.cz`, etc. — for job preparation and submission only
- **Compute nodes** — where calculations actually run
- **Storage**: NFS home directories + fast local `scratch` on compute nodes
- **Modules**: Software is loaded via `module add` (e.g., `module add vasp`, `module add python`)

**Critical rule**: Never run computations on frontends. Always submit via `qsub` and use `$SCRATCHDIR` for I/O-intensive work .

## 1. SSH Setup for AI Agents

The cleanest approach is creating a dedicated SSH key and persistent connection for your AI agents:

```bash
# Generate AI-specific key
ssh-keygen -t ed25519 -f ~/.ssh/metacentrum_ai -C "ai-agent"

# Copy to MetaCentrum
ssh-copy-id -i ~/.ssh/metacentrum_ai.pub username@tarkil.metacentrum.cz

# Add to ~/.ssh/config
Host metacentrum-ai
    HostName tarkil.metacentrum.cz
    User YOUR_USERNAME
    IdentityFile ~/.ssh/metacentrum_ai
    ServerAliveInterval 60
    ControlMaster auto
    ControlPath ~/.ssh/control-%r@%h:%p
    ControlPersist 4h
```

This gives agents a stable, low-latency tunnel to execute PBS commands remotely.

## 2. Skill Files for AI Agents

I've created three skill files that teach your agents the MetaCentrum environment and DFT babysitting:

### [metacentrum_pbs_skill.md](sandbox:///mnt/agents/output/metacentrum_pbs_skill.md)
Contains:
- OpenPBS command reference (`qsub`, `qstat`, `qdel`)
- Job script templates with proper `scratch_local` usage
- Resource request syntax (`select=1:ncpus=8:mem=32gb`)
- Environment variables (`$PBS_JOBID`, `$SCRATCHDIR`, `$PBS_O_WORKDIR`)
- Module system guide for computational chemistry software

### [dft_babysitter_skill.md](sandbox:///mnt/agents/output/dft_babysitter_skill.md)
Contains:
- **Pre-flight checklists** for resource estimation (VASP: ~1GB/atom, PySCF: ~2GB per 100 basis functions)
- **Code-specific PBS templates** for PySCF, GPAW, VASP, and Psi4
- **Crash detection patterns** (SCF convergence, memory overflow, walltime exceeded)
- **Automatic restart strategies** (e.g., copying WAVECAR for VASP restart)
- **Post-calculation validation** rules

### How to load these into your agents:

| Agent | Where to put skills |
|-------|-------------------|
| **OpenCode** | `.opencode/skills/` or reference in config |
| **Claude Code** | `.claude/CLAUDE.md` project context |
| **Antigravity** | Upload to Agent Manager knowledge base |
| **Devin** | Add to repository + system prompt |
| **Hermes** | Include in MCP tool descriptions |

## 3. Resident Monitor ("Crom") — Job Babysitter

You mentioned wanting a resident daemon to watch if jobs run or crash. I've built a Python monitor that can run as a cron job, systemd service, or tmux session:

### [metacentrum_monitor.py](sandbox:///mnt/agents/output/metacentrum_monitor.py)

**Features:**
- SSHs to MetaCentrum and polls `qstat` for your jobs
- Detects finished jobs and checks their `.oJOBID`/`.eJOBID` files for errors
- Recognizes failure patterns: "out of memory", "segmentation fault", "not converged", "walltime exceeded"
- **Optional auto-resubmit** with configurable max retries
- Saves state to JSON so it remembers what's been notified
- Can trigger notifications (desktop, email, Slack) via custom command

**Usage examples:**

```bash
# One-time check
python3 metacentrum_monitor.py --user novak --frontend tarkil.metacentrum.cz

# Cron (every 10 minutes)
*/10 * * * * python3 /path/to/metacentrum_monitor.py --user novak --frontend tarkil.metacentrum.cz

# Daemon mode (continuous)
python3 metacentrum_monitor.py --user novak --frontend tarkil.metacentrum.cz --daemon --interval 300

# With auto-resubmit for failed jobs
python3 metacentrum_monitor.py --user novak --frontend tarkil.metacentrum.cz --auto-resubmit --max-resubmits 2
```

**Systemd service** setup is included in the integration guide below.

## 4. AI Agent Integration Guide

### [ai_agent_integration_guide.md](sandbox:///mnt/agents/output/ai_agent_integration_guide.md)

This covers:
- **SSH configuration** for each agent type
- **Workflow patterns**: (A) Agent prepares/you submit, (B) Full autonomy with guardrails, (C) Batch parameter sweeps
- **Agent-specific tips**:
  - Terminal agents (OpenCode, Claude Code): Use `ssh metacentrum-ai` prefix, `scp`/`rsync` for transfers
  - IDE agents (Antigravity): Mount via SSHFS (`sshfs metacentrum-ai:/home/user ~/meta-remote`)
  - Autonomous agents (Devin, Hermes): Implement approval gates for `qdel` and `rm -rf`
- **Security**: Dedicated keys, no sudo, rate limiting, audit logging
- **Troubleshooting**: Common agent-HPC integration failures

## 5. Quickstart Setup Script

### [setup_metacentrum_ai.sh](sandbox:///mnt/agents/output/setup_metacentrum_ai.sh)

A one-command setup that:
1. Generates the SSH key
2. Copies it to MetaCentrum
3. Configures `~/.ssh/config`
4. Tests the connection
5. Creates the workspace directory structure
6. Installs the monitor and skill files
7. Creates a systemd service file

```bash
chmod +x setup_metacentrum_ai.sh
./setup_metacentrum_ai.sh novak tarkil.metacentrum.cz
```

## 6. Code-Specific MetaCentrum Tips

### PySCF
- Usually installed via `module add python` + pip/conda. Check `module avail *pyscf*`
- Use `python calculation.py` directly in PBS script
- Save checkpoint files (`.chk`) for restart: `mf.chkfile = 'calc.chk'`
- For large systems, use density fitting to reduce memory

### GPAW
- Load via `module add gpaw`
- Set `GPAW_SETUP_PATH` for pseudopotentials
- Use `mpirun -np N gpaw-python script.py` for parallel
- LCAO mode is much faster than PW for molecules

### VASP
- Load via `module add vasp/6.x.x`
- Requires standard input files: `POSCAR`, `POTCAR`, `INCAR`, `KPOINTS`
- Use `mpirun -np N vasp_std` (or `vasp_gam` for Gamma-only)
- Always save `WAVECAR` and `CHGCAR` for restart (`ISTART=1` in INCAR)

### Psi4
- Load via `module add psi4`
- Input format: `psi4 -n 8 input.in output.out`
- Can use `memory 32 GB` in input file to match PBS request

## 7. Recommended Agent Workflow

1. **You**: "Run a B3LYP geometry optimization on water with 6-31G* basis"
2. **Agent**: Reads `dft_babysitter_skill.md`, estimates resources (~4GB, 2 CPUs, 1 hour)
3. **Agent**: Writes `water.in` (Psi4) or `water.py` (PySCF) + `water_pbs.sh`
4. **Agent**: `scp water* metacentrum-ai:~/jobs/`
5. **Agent**: `ssh metacentrum-ai "cd jobs && qsub water_pbs.sh"` → gets job ID
6. **Monitor** (daemon): Checks every 10 min, detects completion
7. **Agent** (on your next prompt): `scp metacentrum-ai:~/jobs/water.out ./` and reports energy, convergence, next steps

## 8. Navigating MetaCentrum System Setup

If you're struggling with the system configuration:

- **Frontends by location**: Choose the closest to minimize latency (tarkil for Prague, skirit for Brno, alfrid for Plzeň)
- **Finding software**: `module avail *vasp*`, `module avail *python*`, `module avail *qchem*`
- **Interactive testing**: `qsub -I -l walltime=00:30:00 -l select=1:ncpus=1:mem=1gb` — gets you a compute node shell for testing
- **Data transfer**: Use `scp` for small files, `rsync` for large datasets, or `sftp` for interactive
- **Quota checking**: `quota -s` on the frontend
- **Scratch cleanup**: `clean_scratch` is automatically called, but verify your outputs are copied back before job ends

All files are ready to download and use. Start with the setup script, configure your agent with the skill files, and let the monitor handle the babysitting. If you need help adapting any of this for a specific code or agent, let me know!

---

# USER

I also heard that Czech MetaCentrum and IT4i have some LLM chatbot to provide help and also some automatic system to prepare jobs efficiently and manage them, can you find details?

---

# Gemini

Both MetaCentrum and IT4Innovations (under the unified national e-INFRA CZ umbrella) have rolled out dedicated local LLM initiatives specifically to tackle cluster configuration friction, privacy issues, and script generation.

Instead of routing your data to commercial external APIs, they run open-weight language models locally on their own hardware infrastructures.

### 1. The Central Chat Platform: `chat.ai.e-infra.cz`

Operated by the CERIT-SC team, **e-INFRA CZ Chat AI** provides an internal ChatGPT-style interface built on **OpenWebUI**.

* **The URL:** [https://chat.ai.e-infra.cz](https://chat.ai.e-infra.cz)
* **Authentication:** You log in natively using your standard **e-INFRA CZ / MetaCentrum credentials**.
* **Data Isolation:** The entire service runs completely within the secure boundaries of the national research infrastructure. Your prompts, raw data, molecular coordinate formats, or custom script files never leak to third-party entities.
* **Capabilities Available:**
* **Model Selection:** They maintain a list of *Guaranteed Models* (stably deployed long-term) and *Experimental Models* (for testing emerging capabilities).
* **Document Context & RAG:** You can directly attach configuration files, logs (`.e` / `.o`), or documentation pages to the chat to let the model troubleshoot stack traces or compilation errors.
* **Python Sandbox:** It features an isolated execution environment. If you paste data or raw text, you can instruct it to run data processing or log analysis directly within the interface.
* **Persistence Command:** It supports native UI state additions. For instance, typing `remember my MetaCentrum login is xnovak12` updates its core context so it formats user scripts accurately down the line.

### 2. Integrated Documentation Assistance

The main MetaCentrum portal (`docs.metacentrum.cz`) features a redesigned **AI Chat Assistance** layer built directly into the site.

* **Local vs. Global Context:** When querying the embedded documentation widget, you can toggle a **"Local" mode**. This strictly confines the LLM’s Retrieval-Augmented Generation (RAG) to the verified contents of MetaCentrum's exact user guides.
* **Target Use Case:** It specializes in translating natural language intent directly into structural scheduler scripts, optimizing resource boundaries (like specifying nodes or memory), and handling common cluster troubleshooting paths without requiring manual searches across the wiki.

### 3. Automatic Job Managers & Portals

While the LLMs solve the script-generation and diagnostic side, e-INFRA CZ provides a couple of automated middleware systems to abstract away manual terminal operations entirely:

#### OpenDemand (Web-Based Cluster Management)

Instead of manipulating raw terminal connections for everything, MetaCentrum provides **OpenDemand**. It gives you an interactive browser-based dashboard to manage files, monitor current active jobs, and open terminal instances directly on a node without wrestling with persistent SSH setups. It also features interactive app templates (e.g., launching an instantaneous JupyterNotebook server pre-wired to the cluster cluster nodes).

#### usegalaxy.cz (Workflow Orchestration)

If your tasks (like running Python pipelines, PySCF, or data-heavy steps) can benefit from a visual graph interface, you can leverage **usegalaxy.cz**. Log in with your e-INFRA credentials to access a web interface that completely manages underlying PBS queuing, schedules tasks automatically, provides large default data quotas (250 GB), and eliminates the need to write custom submission scripts.

### Action Plan for Your Local Setup

If you want to feed your autonomous local agents (like Devin, OpenCode, or Hermes) high-fidelity information regarding the cluster, you can utilize the e-INFRA platform to bootstrap them:

1. Log into **`chat.ai.e-infra.cz`** using your MetaCentrum account.
2. Use the local assistant to generate an exact base profile or "System Prompt" tailored to your resource requirements (for instance, parsing standard `scratch_local` handling or identifying OpenPBS environment traps).
3. Save that generated context directly into your local workspace as a markdown specification file. Your local development agent can then reference it to reliably write syntactically sound scripts without stumbling over MetaCentrum-specific edge cases.

---

# DeepSeek-V4-flash

Yes, MetaCentrum and the wider Czech e-infrastructure (e-INFRA CZ) have integrated several AI tools exactly for the purposes you're exploring—particularly for getting help with documentation and for orchestrating workflows.

### 🤖 AI Assistants for Documentation & General Help
You're correct that both systems provide AI chatbots focused on answering questions based on their official guides:

*   **MetaCentrum's AI Integration**: The official MetaCentrum documentation portal (docs.metacentrum.cz) has an on-page AI chat in the bottom-right corner. It features a 'Local' mode for semantic search of the docs and a 'Problem Solving' mode to help interpret error messages.
*   **Unified e-INFRA CZ Chatbot**: This is a central, cross-platform chatbot covering e-INFRA CZ services (including MetaCentrum), accessible at `https://chat.ai.e-infra.cz`. Built on Open WebUI, it provides access to various LLMs and requires a MetaCentrum account.
*   **CERIT-SC AI Tools**: This platform offers an OpenAI API-compatible interface and low-code workflow builders like **n8n AI Agents**, which are relevant for creating autonomous job management systems.

### 🧠 Automatic Job Management Systems
While there's no single "auto-submit" button, the key infrastructure for building your own AI supervisor is in place.

*   **The Oven Node**: A special frontend (`oven.metacentrum.cz`) perfectly suited for your "resident cron" agent. It's designed for **light, non-demanding control jobs** (like submitting/resubmitting or monitoring) and allows a **walltime of up to 1 month**.
*   **The MetaCentrum Grid**: Your agent will need to interface with the **PBS scheduling system**, using `qsub` to submit jobs, `qstat` to check status, and `qdel` to terminate them.
*   **`chat.ai.e-infra.cz` API**: This service provides an OpenAI-compatible REST API, which your agent can call to access LLMs directly from scripts for automated reasoning and decision-making.
*   **Workflow Automation with n8n**: Platforms like n8n allow you to build visual, autonomous workflows that can integrate APIs and logic, with a web UI to trigger and monitor them.

### 🖥️ Key Resources at IT4Innovations (IT4I)
IT4I's documentation portal at `docs.it4i.cz` is the main resource for their supercomputers (like **Karolina** and **Barbora**). You can find detailed guides on infrastructure access, and their HelpDesk (Request Tracker) allows you to formalize requests.

You have a solid foundation of official tools at your disposal. Now, the main task is to architect the logic that connects them—essentially building the "brain" for your agent.

As you continue designing this system, which part of the connection do you want to focus on next? For example, I can help you draft the PBS submission script for one of your quantum chemistry codes, or we can look into the specifics of calling the AI API from a command-line script.

---

# Kimi-2.6

Based on my search, here's what I found about the tools you heard about:

## 1. MetaCentrum: Qsub Assembler (PBSmon)

MetaCentrum does have a **web-based visual tool for assembling PBS job commands**, but it's not an LLM chatbot — it's a GUI form-based assembler built into **PBSmon** (PBS Monitor).

**What it does:**
- **Interactive web form** with dropdown menus for every PBS resource parameter: `ncpus`, `mem`, `ngpus`, `scratch_local`, `walltime`, `cluster`, `cpu_vendor`, `cuda_version`, etc. 
- **Live node matching**: After selecting resources, it shows you exactly which machines match your criteria and how many are currently free vs. busy 
- **Outputs correct syntax** in two formats:
  - Command-line: `qsub -I walltime=1:0:0 -l select=1:ncpus=1:ngpus=2:mem=400mb:scratch_local=400mb`
  - Shell script with `#PBS` directives ready to paste into your job script 

**Access:** [https://metavo.metacentrum.cz/pbsmon2/qsub_pbspro](https://metavo.metacentrum.cz/pbsmon2/qsub_pbspro) (via PBSmon)

**PBSmon also provides:**
- Live job/node/queue monitoring
- Hardware specifications database
- News and outage announcements
- User quota overview
- Licensed software agreements (e.g., VASP, Orca) 

**However, I found no evidence of a dedicated LLM chatbot** for MetaCentrum support. The portal mentions "nástroje pro umělou inteligenci" (tools for artificial intelligence), but this refers to **AI computing resources** (GPUs, frameworks), not an AI support assistant .

## 2. IT4Innovations: HEAppE — The "Automatic Job System"

The system you likely heard about is **HEAppE** (High-End Application Execution Middleware), developed by IT4Innovations. This is a sophisticated middleware framework for **HPC-as-a-Service** that automates job preparation, submission, and management .

**Key features:**
- **Command Templates**: Pre-prepared job definitions with exposed input parameters. Users submit jobs by filling in parameters rather than writing shell scripts from scratch. This is the "automatic job preparation" aspect — admins create templates for common workflows, users just provide values 
- **REST API**: Full OpenAPI interface for programmatic job submission — perfect for AI agents to call directly 
- **Multi-scheduler support**: Works with both **PBS** (MetaCentrum-style) and **Slurm** (IT4I's Karolina/Salomon/Barbora) 
- **Job management**: Submission, monitoring, file transfer, encryption, notifications, job arrays, dependencies, and extremely long-running job support 
- **Security mapping**: External user accounts are mapped to internal HPC service accounts, so your AI agent can authenticate via HEAppE without needing direct cluster credentials 

**How it works for automated job prep:**
1. An admin or power user creates a **Command Template** (e.g., "VASP calculation" or "PySCF geometry optimization")
2. The template defines the executable, required modules, resource defaults, and **input parameters** (e.g., `inputFile`, `basisSet`, `functional`)
3. Your AI agent (or you) calls the HEAppE API with just the parameter values
4. HEAppE translates this into a proper job script, submits it to the scheduler, monitors it, and notifies on completion

**Projects using HEAppE:**
- **LEXIS Platform** (H2020): Large-scale execution for industry
- **Floreon+**: Crisis decision support with What-If analysis on HPC
- **ExCaPE**: Drug discovery platform
- **Moldimed**: NGS data analysis
- **ESA Urban-TEP**: Docker sandbox execution on clusters 

**Documentation:** [https://heappe.eu/docs](https://heappe.eu/docs) and [https://heappe.it4i.cz/docs](https://heappe.it4i.cz/docs) 

## 3. How This Relates to Your AI Agent Setup

**For MetaCentrum (OpenPBS):**
- Use the **Qsub Assembler** manually to learn valid parameter combinations, then teach your AI agent the patterns
- Your agent can query PBSmon via web scraping or you can provide the skill files I created earlier
- The `metacentrum_monitor.py` I provided essentially does what HEAppE does for monitoring — but via SSH polling instead of API

**For IT4I (Slurm/PBS):**
- If you get access to IT4I's HEAppE instance, your AI agents could submit jobs via **REST API** instead of SSH, which is much cleaner
- The command template system means you could pre-define templates for PySCF/GPAW/VASP runs and let the agent just vary parameters
- HEAppE handles the babysitting (monitoring, restart, notification) natively

**Gap:** Neither MetaCentrum nor IT4I appears to have a public **LLM chatbot** for user support yet. The "AI" references are about compute resources, not conversational interfaces. If you want AI-assisted support, you'd need to bring your own agent (Hermes, Devin, etc.) and feed it the documentation + skill files.

## Summary Table

| Feature | MetaCentrum | IT4I |
|---------|-------------|------|
| **Job prep GUI** | Qsub Assembler (PBSmon) | HEAppE Command Templates |
| **Scheduler** | OpenPBS | Slurm (Karolina) |
| **Monitoring** | PBSmon web + qstat | HEAppE API + dashboard |
| **API for agents** | SSH + qsub commands | REST API (OpenAPI) |
| **Auto-resubmit** | Not built-in | Supported via HEAppE |
| **LLM chatbot** | ❌ Not found | ❌ Not found |
| **HPC-as-a-Service** | Limited | HEAppE middleware |

If you want to explore HEAppE further for your workflows, I can help you understand how to set up command templates for your DFT codes, or how to adapt the MetaCentrum monitor to work with IT4I's Slurm environment.