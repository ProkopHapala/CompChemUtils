
# MetaCentrum Exploration Log (2025-07-03)

Connected via `ssh prokop@metafzu.fzu.cz` with persistent SSH master connection (`~/.ssh/controlmasters/`, ControlPersist 8h).

---

## Available Chemistry Modules (verified by `module avail`)

All modules are under `/packages/run/modules-5/debian12zen`:

| Module | Variants | Notes |
|--------|----------|-------|
| `vasp/` | `vasp46/`, `vasp52/`, `vasp53/` | VASP (licensed) |
| `vaspkit/`, `p4vasp/` | | VASP pre/post-processing |
| `gpaw/`, `py-gpaw/` | | GPAW |
| `xtb/` | | Extended Tight Binding |
| `cp2k/` | | CP2K |
| `nwchem/` | | NWChem |
| `orca/` | | ORCA |
| `turbomole/` | | TURBOMOLE |
| `siesta/` | | SIESTA |
| `quantum-espresso/`, `espresso/`, `espresso_md/` | | Quantum ESPRESSO |
| `wannier90/` | | Wannier90 |
| `phonopy/`, `py-phonopy/` | | Phonopy |
| `ase/`, `py-ase/` | | Atomic Simulation Environment |
| `crystal/` | | CRYSTAL |
| `cfour/` | | CFOUR |
| `wien2k/` | | WIEN2k |
| `columbus/` | | COLUMBUS |
| `plumed/` | | PLUMED (MD enhanced sampling) |
| `vmd/`, `xcrysden/` | | Visualization |

## Python / Conda Environment

| Module | Version |
|--------|---------|
| `python/` | base system python |
| `mambaforge/` | Python 3.10.6, conda 22.9.0 |
| `conda-modules/` | conda infrastructure |
| `py-pip/` | pip |

**conda base environment is read-only** at `/afs/ics.muni.cz/software/mambaforge/22.9.0-3/`.
User conda envs go to `/storage/praha1/home/prokop/.conda/envs/`.

## conda Channel Problem

The system `.condarc` at `/afs/ics.muni.cz/software/mambaforge/22.9.0-3/.condarc` contains broken S3 mirror channels:
```
channels:
  - https://s3.cl5.du.cesnet.cz/.../bioconda-s3chnl
  - https://s3.cl5.du.cesnet.cz/.../conda-forge-s3chnl
```
These S3 URLs return HTTP 000 CONNECTION FAILED. This breaks ALL default `conda install` / `conda search` / `conda create` commands.

**Workaround:** Use `--override-channels` flag with `-c conda-forge` explicitly:
```bash
conda create -n myenv -c conda-forge python=3.11 --override-channels -y
```
This works — conda-forge is reachable directly, only the S3 mirrors are down.

User `~/.condarc` has:
```
channels:
  - conda-forge
  - defaults
```
But the system `.condarc` channels still get loaded and break things without `--override-channels`.

---

## PySCF Installation — SUCCESS

PySCF is NOT available as a module. Installed via pip:

```bash
module add mambaforge
pip3 install --user pyscf
```

Result: `Successfully installed h5py-3.16.0 numpy-2.2.6 pyscf-2.13.1 scipy-1.15.3`

Installed to `/storage/praha1/home/prokop/.local/` (user site-packages).

**Tested successfully:**
```python
from pyscf import gto, scf
mol = gto.M(atom="H 0 0 0; H 0 0 1.2", basis="sto3g")
mf = scf.RHF(mol)
print("PySCF energy:", mf.kernel())
```
Output: `converged SCF energy = -1.00510670656849` — works correctly.

**Note:** pip has internet access on the frontend (PyPI is reachable). Only conda channels (S3 mirrors) are broken.

---

## Psi4 Installation — FAILED (multiple attempts)

Psi4 is NOT available as a module and could not be installed. Attempts:

### Attempt 1: pip install psi4
```bash
pip3 install --user psi4
```
Result: `ERROR: Could not find a version that satisfies the requirement psi4 (from versions: none)`
Psi4 is not on PyPI.

### Attempt 2: pip with psicode.org extra index
```bash
pip3 install --user psi4 --extra-index-url https://psicode.org/psi4pip/
pip3 install --user "psi4>=1.7" --only-binary :all: --extra-index-url https://psicode.org/psi4pip/
pip3 install --user "psi4==1.8.2" --only-binary :all: --extra-index-url https://psicode.org/psi4pip/
```
Result: Same error — `No matching distribution found for psi4`.
The `https://psicode.org/psi4pip/` URL returns HTTP 404 (checked with `curl -sI`). The Psi4 pip index appears to be down or moved.

### Attempt 3: conda create + conda install
```bash
conda create -n psi4env -c conda-forge python=3.11 --override-channels -y  # SUCCESS
conda install -n psi4env -c conda-forge psi4 --override-channels -y        # NEVER COMPLETED
```
The conda create worked (with `--override-channels`), but `conda install psi4` was taking extremely long (solving environment hangs). Cancelled by user after waiting too long.

### Why Psi4 is problematic on MetaCentrum
1. **Not on PyPI** — `pip install psi4` finds nothing
2. **psicode.org pip index returns 404** — the custom pip repository is down
3. **conda channels broken** — system `.condarc` has dead S3 mirrors that block all conda operations unless `--override-channels` is used
4. **conda install psi4 extremely slow** — even with `--override-channels -c conda-forge`, the dependency solving for Psi4 hangs (Psi4 has many binary dependencies: Intel MKL, QCElemental, etc.)
5. **No module available** — MetaCentrum does not provide Psi4 as a system module

### Possible paths forward for Psi4 (not yet tried)
- `conda install -n psi4env -c conda-forge psi4 --override-channels -y` with more patience (let it run for 30+ minutes)
- Use `mamba` instead of `conda` for faster dependency solving: `mamba install -n psi4env -c conda-forge psi4`
- Build Psi4 from source in scratch with cmake (complex, many deps)
- Ask MetaCentrum support (meta@cesnet.cz) to install Psi4 as a module
- Download Psi4 conda package on local machine and transfer via scp

---

## Software Available on MetaCentrum — Organized by Basis Set

### Plane-Wave / Pseudopotential

| Module | Code | Notes |
|--------|------|-------|
| `vasp/`, `vasp46/`, `vasp52/`, `vasp53/` | VASP | PAW pseudopotentials. Licensed — check access. Variants: vasp46, vasp52, vasp53 |
| `quantum-espresso/`, `espresso/`, `espresso_md/` | Quantum ESPRESSO | PW + norm-conserving/PAW/ultrasoft. `espresso_md` for Car-Parrinello MD |
| `abinit/` | ABINIT | PW pseudopotential, DFPT, GW, BSE |
| `gpaw/`, `py-gpaw/` | GPAW | PW / finite-difference / LCAO modes. Python interface via `py-gpaw` |
| `cp2k/` | CP2K | Gaussian+PW (GPW hybrid). Also Quickstep DFT with localized basis |

### Full-Potential LAPW (Linearized Augmented Plane Wave)

| Module | Code | Notes |
|--------|------|-------|
| `wien2k/` | WIEN2k | Full-potential LAPW, all-electron |
| `elk/` | Elk | Full-potential LAPW, all-electron, open source |

### Gaussian / Localized Orbital Basis

| Module | Code | Notes |
|--------|------|-------|
| `crystal/` | CRYSTAL | Gaussian basis, all-electron / ECP, periodic |
| `turbomole/` | TURBOMOLE | Gaussian basis, molecular, RI-J/S2 methods |
| `nwchem/` | NWChem | Gaussian + PW hybrid, molecular & periodic, many methods |
| `cfour/` | CFOUR | Gaussian basis, molecular, high-accuracy coupled cluster |
| `columbus/` | COLUMBUS | Gaussian basis, molecular, multireference CI/CC |

### Tight-Binding / Semi-Empirical

| Module | Code | Notes |
|--------|------|-------|
| `dftbplus/` | DFTB+ | DFT-based tight-binding, fast approximate DFT |
| `xtb/` | xtb | Extended tight-binding (GFN-xTB), very fast, molecular |
| `siesta/` | SIESTA | Localized numerical atomic orbitals, order-N, periodic |

### Real-Space Grid

| Module | Code | Notes |
|--------|------|-------|
| `octopus/` | Octopus | Real-space grid TDDFT, finite-difference, molecular & periodic |

### Python-Native (no module — install manually)

| Code | Install method | Status |
|------|---------------|--------|
| PySCF | `module add mambaforge; pip3 install --user pyscf` | **INSTALLED & TESTED OK** (v2.13.1) — Gaussian basis, molecular, all-electron |
| Psi4 | conda install (needs `--override-channels`) | **FAILED** — not on PyPI, psicode.org 404, conda hangs. See details above |

### Post-Processing & Tools

| Module | Code | Purpose |
|--------|------|---------|
| `wannier90/` | Wannier90 | Wannier functions (interfaces VASP, QE, ABINIT) |
| `vaspkit/`, `p4vasp/` | VASPKIT, p4vasp | VASP pre/post-processing |
| `phonopy/`, `py-phonopy/` | Phonopy | Phonons (interfaces VASP, QE, etc.) |
| `ase/`, `py-ase/` | ASE | Atomic Simulation Environment (Python wrapper for many codes) |
| `uspex/` | USPEX | Crystal structure prediction (calls VASP/QE as engine) |
| `pexsi/` | PEXSI | Pole expansion for density matrix (scales to large systems) |
| `plumed/` | PLUMED | Enhanced sampling MD (metadynamics, etc.) |
| `vmd/` | VMD | Visualization (structures, trajectories) |
| `xcrysden/` | XCrySDen | Visualization (crystal structures, isosurfaces) |
| `vesta/` | VESTA | Visualization (structures, charge density, electron localization) |

---

## GPAW Installation — TESTED OK (with workaround)

### Available modules

| Module | Version | Notes |
|--------|---------|-------|
| `gpaw/1.4.0-py34` | 1.4.0 | Old, Python 3.4, Intel toolchain. **Sets `GPAW_SETUP_PATH` automatically** |
| `py-gpaw/21.1.0-gcc-10.2.1-ujtynac` | 21.1.0 | GCC 10.2.1 toolchain |
| `py-gpaw/24.1.0-gcc-10.2.1-fojjhkw` | 24.1.0 | **Newest, recommended**. Includes ASE 3.22.1, Python 3.9, numpy 1.22, scipy 1.8, matplotlib 3.5 |

### Critical issue: `GPAW_SETUP_PATH` not set by `py-gpaw` module

The `py-gpaw/24.1.0` module does **NOT** set `GPAW_SETUP_PATH`. Without it, GPAW fails with:
```
FileNotFoundError: Could not find required PAW dataset file "O.LDA".
```

`gpaw install-data` (which would download setups) also fails — HTTP 403 Forbidden (frontend has no access to the GPAW setup download server).

**Workaround:** Reuse the old setup files from `gpaw/1.4.0` module:
```bash
module add py-gpaw/24.1.0-gcc-10.2.1-fojjhkw
export GPAW_SETUP_PATH=/software/gpaw/1.4.0/setup_files/gpaw-setups-0.9.20000
```

These are `gpaw-setups-0.9.20000` (old but functional for LCAO/LDA calculations). Located at `/software/gpaw/1.4.0/setup_files/gpaw-setups-0.9.20000/`.

**Warning:** These old setups may not support all XC functionals or features of GPAW 24.1.0. If newer setups are needed, they must be downloaded on a machine with internet access and transferred to Metacentrum (e.g. to `~/.gpaw/` or `$HOME/gpaw-setups/`).

### H2O test calculation — SUCCESS

Test script: `/storage/praha1/home/prokop/git/CompChemUtils/test/gpaw_h2o_test.py`
PBS script: `/storage/praha1/home/prokop/git/CompChemUtils/test/gpaw_h2o_test.pbs`

```python
from ase.build import molecule
from gpaw import GPAW
atoms = molecule('H2O', vacuum=4.0)
atoms.calc = GPAW(mode='lcao', txt='h2o_lcao.txt')
E = atoms.get_potential_energy()
print(f"H2O LCAO energy: {E:.6f} eV")
```

**PBS resources:** 1 CPU, 2GB RAM, 10min walltime — sufficient for this tiny calculation.

**Result:**
- Energy: `-10.095179 eV` (LDA, LCAO mode)
- SCF converged in 9 iterations, ~1.2s total
- Gap: 8.327 eV
- Memory: 169 MiB
- Compute node: `eluo1-4.hw.elixir-czech.cz`

### GPAW on Metacentrum — key facts

- **LCAO mode** is fastest for molecules (as noted in `Prokop_Metacentrum.md`)
- Python 3.9.12 (from spack), not system Python
- ASE 3.22.1 bundled with the module
- `gpaw` CLI tool available at `$PATH/bin/gpaw` (supports `gpaw install-data`, `gpaw info`, etc.)
- MPI parallel: `mpirun -np N gpaw-python script.py` (OpenMPI 4.1.3 bundled)
- libxc 4.3.4 bundled (for XC functionals)

---

## Persistent Interactive PBS Job via tmux (AI Agent Workflow)

### Problem

`qsub -I` opens an interactive shell on a compute node, but each `run_command` call from an AI agent (Cascade) is a **separate process** — there's no way to keep an interactive shell open across calls. Running `qsub -I` directly from `run_command` would block forever or time out.

### Solution: tmux as persistent wrapper

Use a **detached tmux session** on the frontend node to hold the `qsub -I` shell open. Then send commands into it via `tmux send-keys` and read output via `tmux capture-pane`.

#### 1. Create a detached tmux session

```bash
tmux new-session -d -s mc -x 200 -y 50
```

- `-d` = detached (no terminal attached)
- `-s mc` = session name `mc` (short for metacentrum)
- `-x 200 -y 50` = wide pane so long lines don't wrap (important for reading output)

#### 2. Launch interactive job inside tmux

```bash
tmux send-keys -t mc 'qsub -I -l walltime=02:00:00 -l select=1:ncpus=1:mem=2gb' Enter
```

Wait ~10-30s for the job to start (queue wait time varies). Check status:

```bash
sleep 10 && tmux capture-pane -t mc -p
```

You should see:
```
qsub: waiting for job 21824553.pbs-m1.metacentrum.cz to start
qsub: job 21824553.pbs-m1.metacentrum.cz ready

(BOOKWORM)prokop@tarkil16:~$
```

The prompt now shows the **compute node hostname** (e.g. `tarkil16`), confirming you're on the compute node, not the frontend.

#### 3. Load modules inside the session

```bash
tmux send-keys -t mc 'module purge && module add py-gpaw/24.1.0-gcc-10.2.1-fojjhkw && export GPAW_SETUP_PATH=/software/gpaw/1.4.0/setup_files/gpaw-setups-0.9.20000' Enter
```

Wait for module loading to finish (~5-10s), then verify:

```bash
sleep 10 && tmux capture-pane -t mc -p -S -10
```

#### 4. Run commands / scripts

Send any command to the compute node shell:

```bash
tmux send-keys -t mc 'cd /storage/praha1/home/prokop/git/CompChemUtils/test && python3 gpaw_h2o_test.py' Enter
```

Read output after a few seconds:

```bash
sleep 8 && tmux capture-pane -t mc -p -S -10
```

#### 5. Reading output reliably

- `tmux capture-pane -t mc -p` — prints current visible pane content
- `tmux capture-pane -t mc -p -S -30` — includes 30 lines of scrollback history
- `tmux capture-pane -t mc -p -S -` — entire scrollback buffer (can be very long)
- Always `sleep N` before capturing to give the command time to produce output

#### 6. Check if the job is still alive

From the frontend (outside tmux):

```bash
qstat -u prokop
```

Or check the tmux pane — if the job ended, you'll see the frontend prompt again (`metafzu` instead of compute node name).

#### 7. Kill the session when done

```bash
tmux kill-session -t mc
```

Or exit the interactive job by sending `exit`:

```bash
tmux send-keys -t mc 'exit' Enter
```

### Key notes

- **Walltime** is set at `qsub -I` launch (e.g. `walltime=02:00:00` = 2h). The job auto-terminates when walltime expires.
- **Modules must be reloaded** if the job ends and a new `qsub -I` is started in the same tmux session (new compute node = fresh environment).
- **tmux survives** even if the SSH session drops (as long as the frontend node stays up). Reattach with `tmux attach -t mc`.
- **Multiple commands**: send them one at a time with `sleep` between send and capture. For multi-line scripts, use a heredoc or write a temp script file first.
- **Queue wait**: `qsub -I` blocks until the job starts. If the queue is busy, this can take minutes. The tmux session handles this gracefully — just poll with `tmux capture-pane`

---

## Persistent Interactive PBS Job via SSH to Compute Node (AI Agent Workflow — RECOMMENDED)

### Concept

Instead of tmux, use a simpler two-terminal approach:

1. **Terminal 1 (user):** `qsub -I` holds the job allocation open
2. **Terminal 2 (agent):** SSH directly to the compute node, run commands, get clean output

This is cleaner than tmux because:
- Each `ssh node 'command'` returns output directly — no `sleep` + `capture-pane` timing issues
- No scrollback limits, no line wrapping
- Exit codes work properly

### Important: Use `-q luna` queue

The `luna` queue is **dedicated for us** with priority. Always use:

```bash
qsub -I -q luna -l walltime=02:00:00 -l select=1:ncpus=1:mem=2gb
```

### Step-by-step

#### 1. User starts interactive job (Terminal 1)

```bash
qsub -I -q luna -l walltime=02:00:00 -l select=1:ncpus=1:mem=2gb
```

Wait for the prompt showing the compute node name (e.g. `luna106`). **Keep this terminal open** — it holds the job allocation.

#### 2. Agent extracts job info (Terminal 2 / run_command)

```bash
python3 py/cluster/interactive_job.py JOBID --outdir test
```

This parses `qstat -f JOBID` and writes:
- `job_env.json` — machine-readable (node name, all PBS variables)
- `job_env.sh` — sourceable shell script that exports all PBS variables + inits the module system

To find the JOBID if unknown: `qstat -u prokop` and look for `interactive` / `STDIN` jobs.

#### 3. Agent runs commands on compute node via SSH

```bash
ssh luna106 'source /path/to/job_env.sh && module add py-gpaw/24.1.0-gcc-10.2.1-fojjhkw && python3 script.py'
```

The `job_env.sh` script handles:
- **Module system init** — sources `/cvmfs/software.metacentrum.cz/modulefiles/5.3.1/loadmodules` (needed because non-interactive SSH doesn't load profile.d)
- **PBS variables** — exports `SCRATCHDIR`, `PBS_O_WORKDIR`, `PBS_NUM_PPN`, etc. so scripts that reference them work correctly

#### 4. Check job status

```bash
qstat -u prokop
```

Job state `R` = running. When walltime expires, the job ends and SSH to the node will fail.

### Script: `py/cluster/interactive_job.py`

**Location:** `py/cluster/interactive_job.py`
**Usage:**
```bash
python3 py/cluster/interactive_job.py JOBID [--outdir DIR]
```

**Output files (in `--outdir`, default `.`):**

| File | Purpose |
|------|---------|
| `job_env.json` | Machine-readable: `{"jobid": "...", "node": "...", "variables": {...}}` |
| `job_env.sh` | Sourceable: exports all PBS env vars + inits module system |

**Python API:**
```python
from py.cluster.interactive_job import parse_qstat, extract_node, extract_variables

fields = parse_qstat("21824758")     # → dict of all qstat -f fields
node = extract_node(fields)           # → "luna106"
variables = extract_variables(fields) # → {"SCRATCHDIR": "...", "PBS_O_WORKDIR": "...", ...}
```

### Key notes

- **`-q luna`** — always use the luna queue (dedicated, priority)
- **Module init** — `job_env.sh` sources the module system automatically; without it, `module` command is unavailable in non-interactive SSH
- **PBS_O_PATH skipped** — the original `$PBS_O_PATH` from the submission shell is not exported (it may break the module system on the compute node). The module system sets its own `$PATH`.
- **Each SSH is a fresh shell** — modules must be loaded in every SSH command. Use `&&` chaining or write a wrapper script.
- **Job must be running** — script checks `job_state == R` and exits with error if not
- **Walltime** — set at `qsub -I` launch; job auto-terminates when expired
- **SCRATCHDIR** — available in `job_env.sh` if the job has scratch allocated