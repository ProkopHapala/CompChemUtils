https://gemini.google.com/share/f79fdbd90c6f

---

# USER

How secure is Hermes agent? openClaw is not... I want to try on my default machine, so I would like to limit it's range to just some folders or something

---

# Gemini

You are right to be cautious. OpenClaw’s security issues left a lot of self-hosted enthusiasts burned, mostly because it treated security as an afterthought.

**Hermes Agent (by Nous Research) is a massive step up.** Its engineering team treats security as a fundamental starting constraint rather than a bug class to fix later. However, **Hermes’ official security policy explicitly states that nothing inside the agent process itself constitutes containment.** If you run it natively on your bare-metal host, an adversarial LLM or a severe prompt-injection attack can still bypass prompt scanners, pattern matchers, or tool allowlists.

If you want to try Hermes on your default machine safely and strictly limit its range to just a few folders, **do not run it locally directly.** Instead, you should run it inside its official Docker container and explicitly limit what it can see.

Here is exactly how to lock Hermes down into a safe, restricted sandbox on your machine:

## 1. The Core Strategy: Docker Volume Mapping

The best way to isolate Hermes is to leverage Docker’s file system isolation. By default, a container cannot see anything on your host computer. It can *only* see what you explicitly hand over to it via mounts.

To restrict Hermes to specific folders, you will map **only those directories** into the container.

### Recommended Directory Structure

Create a dedicated space on your host machine to serve as Hermes' playground:

```bash
mkdir -p ~/hermes_sandbox/data
mkdir -p ~/hermes_sandbox/my_project

```

* `~/hermes_sandbox/data`: This will store Hermes' inner workings (its configuration, local database, memory, and skills).
* `~/hermes_sandbox/my_project`: This is the specific folder you actually want the agent to work on.

## 2. Launching Hermes via Docker (The Lockdown Command)

When you run the Docker container, use explicit volume (`-v`) flags. This tells Docker: *"Let the agent see this specific folder, and absolutely nothing else."*

Run this from your terminal:

```bash
docker run -d --name hermes_agent \
  --restart unless-stopped \
  -v ~/hermes_sandbox/data:/opt/data \
  -v ~/hermes_sandbox/my_project:/workspace \
  nousresearch/hermes-agent:latest

```

### Why this is secure:

* **Complete Host Isolation:** If Hermes (or a prompt injection) attempts to run `rm -rf /` or read `~/.ssh/id_rsa`, it will only affect the throwaway internal container filesystem. Your actual computer remains untouched.
* **Strict Scope:** The agent will only be able to view and modify files located inside `~/hermes_sandbox/my_project` (which appears to the agent as `/workspace`). It has zero awareness of the rest of your hard drive.

## 3. Extra Hardening Configurations

Once you have it isolated via Docker, you can fine-tune its behavior inside its configuration file (located in your host folder at `~/hermes_sandbox/data/config.yaml` after setup).

### Enable Command Approvals

Hermes has a built-in defense-in-depth layer for dangerous shell commands. Make sure its approval mode is set to `manual` or `smart`:

```yaml
approvals:
  mode: manual  # Always prompts you for permission before running a risky command
  timeout: 60   # Automatically denies the command if you don't approve it within 60 seconds

```

### Read-Only vs. Read-Write

If you want Hermes to look at a folder on your computer but want to **absolutely guarantee it cannot delete or change any files**, append `:ro` (Read-Only) to the end of your volume mapping:

```bash
-v /path/to/your/important_code:/workspace:ro

```

With `:ro` active, even if the AI hallucinates or gets malicious, Docker will block any write, delete, or modify actions on that host directory.

---

# USER

Ok I'm on Linux I would think I can restricted Hermes even without docker by user account give Hermes user or group with certain rights? Docker is slowing thing down right?

---

# Gemini

Yes, you can absolutely do that. On Linux, restricting a process by assigning it to a dedicated, unprivileged user account and group is a time-tested, rock-solid security practice.

However, your assumption about Docker is a very common misconception: **Docker does not slow down standard file-system operations or CPU execution.** It uses Linux *namespaces* and *cgroups* (the exact same underlying kernel features used for system isolation), so it runs at native, bare-metal speed.

That said, if you prefer avoiding Docker completely to keep your process tree clean, managing Hermes with standard Linux user permissions is highly effective. Here is how to set it up safely.

## The Linux User Group Approach

To restrict Hermes natively, you want to create a dedicated user (e.g., `hermesuser`), deny it access to your main home folder, and grant it access *only* to a shared directory.

### Step 1: Create the isolated user and group

Create a locked-down system user with its own home directory:

```bash
sudo useradd -m -s /bin/bash hermesuser

```

### Step 2: Set up the shared playground

Create the folder where you want to allow Hermes to work. You will make this folder accessible to a shared group or change its ownership so both you and the `hermesuser` can touch files.

```bash
# Create the project workspace
mkdir -p ~/hermes_projects/my_target_project

# Change ownership so the hermes user can read and write to it
sudo chown -R hermesuser:hermesuser ~/hermes_projects/my_target_project

```

*(Alternatively, you can add your primary user and `hermesuser` to a shared group and set the directory permissions to `770` if you both need active write access to the exact same files).*

### Step 3: Block access to your main home directory

By default on many Linux distributions, home directories are readable by other local users (`755`). You need to close this gap so Hermes cannot sneak a peek at your personal SSH keys or config files:

```bash
chmod 700 ~

```

Now, `hermesuser` is physically blocked by the Linux kernel from stepping foot inside your personal home directory.

### Step 4: Run Hermes as that user

When you want to spin up the agent, use `sudo -u` to execute it under the restricted identity:

```bash
sudo -u hermesuser hermes chat --path ~/hermes_projects/my_target_project

```

## ⚠️ The "Gotcha" with Native Linux Isolation

While this completely protects your **private files**, there is a major security gap you must keep in mind compared to Docker: **System-wide Read Access.**

An unprivileged Linux user can still read most of the root filesystem. If Hermes gets hit with a severe prompt-injection attack or runs a malicious script, it **cannot** modify your system, but it **can** read files like:

* `/etc/passwd` (list of user accounts)
* `/var/log/` (system logs, which might leak network activity or software versions)
* Any globally readable configuration files or environment variables in `/etc/`

If the agent has tools enabled that let it outbound-request the internet (like curl or python web requests), an attacker could theoretically read system configurations and exfiltrate them.

### The Performance Verdict: Docker vs. Native

If you were avoiding Docker because you are worried about simulation overhead, compilation lag, or memory throttling—**don't be.** Docker on Linux isn't a virtual machine; it doesn't emulate hardware.

If you want the absolute highest security boundary (blocking it from reading `/etc/` or seeing your network interface at all) without losing a single frame of performance, Docker is still the superior choice. But if your only threat model is *"I just don't want it accidentally deleting or reading my personal files/code projects,"* the **Linux User Account method** works beautifully.

---

# USER

What if I want Hermes to use some programs? Namely DFT Code which is installed under my account or in conda. I do not want to make separate installation in docker or separate conda environment because of disk space

---

# Gemini

That completely changes the equation. If you are dealing with complex scientific software like DFT codes (which usually rely on heavy compiled binaries, precise MPI configurations, shared libraries, and specific GPU/CUDA paths), trying to copy all of that into a clean Docker container or recreating a massive `conda` environment is a massive waste of disk space and a configuration nightmare.

Fortunately, Hermes Agent actually has **native support for Singularity/Apptainer containers and local user privilege switching** specifically to handle HPC and scientific workflows without duplicating giant environments.

To give Hermes access to your existing Conda environments and globally installed DFT codes *without* compromising your main account's safety, use the **Dual-User Conda Sharing** approach.

---

## The Strategy: "Read-Only" Conda Sharing

Instead of isolating Hermes in a box where it can't see your tools, you run Hermes under a restricted user account (`hermesuser`) but explicitly grant it permission to read and execute from your existing Conda installation.

Because `conda` environments are mostly just directories filled with binaries and Python packages, `hermesuser` can activate and run your DFT codes perfectly fine as long as it has **read** permissions to the conda path, but it won't have **write** permissions to change your environments or touch your personal data.

### Step 1: Fix Permissions on your Conda Installation

By default, Conda installs to your home directory (e.g., `~/miniconda3` or `~/anaconda3`). If your home directory is completely locked down (`700`), the `hermesuser` won't be able to reach the binaries.

You need to allow other users to read and execute files in your Conda directory:

```bash
# Allow read/execute permissions to your conda folder recursively
chmod -R a+rX ~/miniconda3

```

### Step 2: Create a Shared Terminal Wrapper for Hermes

Since Hermes works by spinning up shell instances to execute commands, you can provide it with a customized wrapper script that automatically sources your base shell and activates the exact Conda environment your DFT code lives in.

Create a script inside the shared workspace (e.g., `/home/hermesuser/run_dft.sh` or in a shared folder):

```bash
#!/bin/bash
# Target: Run a DFT calculation through Conda safely
source /home/yourusername/miniconda3/etc/profile.d/conda.sh
conda activate your_dft_env_name

# Execute the command passed by Hermes
exec "$@"

```

Make the script executable:

```bash
chmod +x /path/to/shared/run_dft.sh

```

### Step 3: Register the DFT Code as a Hermes "Skill" or Tool

Instead of giving Hermes a blanket terminal where it can wander around, you can restrict its toolset. In your Hermes configuration (`config.yaml`), you can explicitly map your DFT executables or the wrapper script as a tool:

```yaml
tools:
  allowed_commands:
    - "/path/to/shared/run_dft.sh"
    - "mpirun" # If your DFT code requires parallel execution

```

When Hermes needs to run a calculation, it will invoke it via the wrapper:

> **Hermes executes:** `/path/to/shared/run_dft.sh pw.x -in control.in > control.out`

---

## Alternative: The Singularity / Apptainer Route

If you ever *do* decide to containerize for absolute security, **do not use Docker for DFT codes.** Docker has a massive performance penalty when dealing with MPI (parallel cluster computing) and direct GPU access.

Instead, look at **Singularity (Apptainer)**, which Hermes natively supports.

* Singularity containers are just a single `.sif` file on your disk.
* Unlike Docker, Singularity automatically mounts your host network, environment, and GPU drivers at **zero performance cost**.
* You can build a Singularity image that simply "bind-mounts" your existing host Conda directory directly inside the container at runtime.

```bash
# Example of running a command via Singularity where your host conda is mapped inside
singularity exec --bind /home/yourusername/miniconda3:/opt/conda dft_container.sif python script.py

```

### Summary of the Best Path Forward:

Stick to the **unprivileged Linux user account**, open up *only* the read permissions (`chmod -R a+rX`) to your existing `miniconda3` or `anaconda3` directory, and use a wrapper script to let Hermes run the DFT calculations. You save hundreds of gigabytes of disk space, get bare-metal execution speeds for your simulations, and keep your private keys and root directory completely safe.