
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

---

## GPAW Fukui Cluster — PBS Script Issues & Fixes (2025-07-03)

### Context

`/storage/praha1/home/prokop/Fukui_AFM/gpaw_fukui_cluster/jobs/` contains 32 baked PBS scripts (24 single-point + 8 post-processing) generated by `generate_jobs.py`. Three issues were found and patched manually before submission.

### Issues Found

#### 1. Wrong module name: `module add gpaw` → `module add py-gpaw/24.1.0-gcc-10.2.1-fojjhkw`

**Problem:** All PBS scripts used `module add gpaw` which loads the old `gpaw/1.4.0-py34` (Python 3.4, Intel toolchain). This module sets `GPAW_SETUP_PATH` automatically but is ancient and incompatible with modern scripts.

**Fix:** Changed to `module add py-gpaw/24.1.0-gcc-10.2.1-fojjhkw` (GPAW 24.1.0, Python 3.9, GCC toolchain) — the tested and working module.

**Lesson for LLM:** Always check `module avail *gpaw*` on the target cluster. The `gpaw/` and `py-gpaw/` naming convention is confusing — `py-gpaw` is the newer spack-built version. See "GPAW Installation" section above for the full module comparison.

#### 2. Missing `GPAW_SETUP_PATH` export

**Problem:** `py-gpaw/24.1.0` does **NOT** set `GPAW_SETUP_PATH` (unlike the old `gpaw/1.4.0`). Without it, GPAW fails with `FileNotFoundError: Could not find required PAW dataset file "O.LDA"`.

**Fix:** Added `export GPAW_SETUP_PATH=/software/gpaw/1.4.0/setup_files/gpaw-setups-0.9.20000` after the module load line.

**Lesson for LLM:** This is a known issue documented above. The `py-gpaw` module reuses old setup files from `gpaw/1.4.0`. `gpaw install-data` fails on frontend (HTTP 403). Any PBS script using `py-gpaw` must manually export `GPAW_SETUP_PATH`.

#### 3. Missing `-q luna` queue directive

**Problem:** No `#PBS -q` directive — jobs would go to the default queue (shared, lower priority, longer wait).

**Fix:** Added `#PBS -q luna` to all 32 PBS scripts.

**Lesson for LLM:** Always use `-q luna` on Metacentrum — it's the dedicated FZU queue with priority access. This applies to both `qsub` batch jobs and `qsub -I` interactive jobs.

#### 4. Wrong executable: `gpaw-python` → `python3`

**Problem:** PBS scripts used `mpirun -np $PBS_NUM_PPN gpaw-python run_*.py` but `gpaw-python` does not exist in the `py-gpaw/24.1.0` spack build. Error: `mpirun was unable to find the specified executable file`.

**Fix:** Changed to `mpirun -np $PBS_NUM_PPN python3 run_*.py`. GPAW is imported as a Python module — `python3` with `mpirun` works for MPI parallelism.

**Lesson for LLM:** The `gpaw-python` wrapper exists in some GPAW installations but not in the spack-built `py-gpaw/24.1.0` on Metacentrum. Always check `which gpaw-python` before using it. When in doubt, use `python3` directly — it works universally.

#### 5. Wrong convergence keyword: `maxiter` → `maximum_iterations`

**Problem:** Used `convergence=dict(..., maxiter=500)` but GPAW 24.1.0 doesn't recognize `maxiter`. Error: `InputError: The convergence keyword "maxiter" was supplied, which we do not know how to handle`.

**Fix:** Use `maxiter=500` as a GPAW **constructor argument**, NOT in the `convergence` dict. The convergence dict keys use spaces (e.g. `'maximum iterations'`), not underscores. Cleanest approach:
```python
calc = GPAW(..., maxiter=500, convergence=dict(energy=1e-5, density=1e-5, bands='occupied'))
```

**Lesson for LLM:** GPAW's `maxiter` is a constructor parameter, not a convergence dict key. The convergence dict uses keys with spaces: `'energy'`, `'density'`, `'eigenstates'`, `'forces'`, `'work function'`, `'minimum iterations'`, `'maximum iterations'`. Do NOT use underscores in convergence dict keys. When in doubt, use the `maxiter` constructor argument instead.

#### 6. Anion SCF convergence failure (small molecules)

**Problem:** Anion (charge=-1) calculations for small molecules (H2O, CH2O, CH2NH, pyridine) failed to converge SCF — energy oscillated over 333 iterations. Larger molecules (pentacene, PTCDA, C2H4, pyrrol) converged fine.

**Root cause:** Small molecule anions have diffuse electrons in a large vacuum cell. The extra electron may be weakly bound or unbound (SOMO above vacuum level), causing charge sloshing. The default density mixer (beta=0.1) is too aggressive.

**Fix:** Added `mixer=Mixer(0.05, 5, 1.0)` (gentler mixing, beta=0.05) and `maxiter=500` (constructor argument) to anion scripts.

**Note:** If the anion is truly unbound (SOMO > 0 eV), no mixer settings will help — the calculation will never converge. In that case, the Fukui f+ function is not physically meaningful for that molecule. Consider using a larger cell or checking the HOMO/LUMO energy of the neutral molecule first.

**Lesson for LLM:** For charged systems (especially anions of small molecules), always use gentler density mixing (`Mixer(0.05, 5, 1.0)`) and more iterations. If SCF still doesn't converge, check if the anion is physically bound by examining the LUMO energy of the neutral system.

### Patch Applied

One-liner to fix all PBS scripts in `jobs/` directory:

```bash
# Fix single-point scripts (module + setup path + queue + executable)
for f in submit_*_N.pbs submit_*_A.pbs submit_*_C.pbs; do
  sed -i 's/^module add gpaw$/module add py-gpaw\/24.1.0-gcc-10.2.1-fojjhkw\nexport GPAW_SETUP_PATH=\/software\/gpaw\/1.4.0\/setup_files\/gpaw-setups-0.9.20000/' "$f"
  sed -i '/^#PBS -m bae/a #PBS -q luna' "$f"
  sed -i 's/mpirun -np \$PBS_NUM_PPN gpaw-python/mpirun -np $PBS_NUM_PPN python3/' "$f"
done

# Fix post-processing scripts (module + queue)
for f in submit_*_post.pbs; do
  sed -i 's/^module add python$/module add py-gpaw\/24.1.0-gcc-10.2.1-fojjhkw/' "$f"
  sed -i '/^#PBS -j oe/a #PBS -q luna' "$f"
done
```

### Also Fixed: `generate_jobs.py` Source

The `generate_jobs.py` script should be updated so future regeneration produces correct PBS scripts. In `bake_p()` and `bake_postprocess_pbs()`, change:
- `module add gpaw` → `module add py-gpaw/24.1.0-gcc-10.2.1-fojjhkw` + `export GPAW_SETUP_PATH=...`
- `module add python` → `module add py-gpaw/24.1.0-gcc-10.2.1-fojjhkw`
- `mpirun -np $PBS_NUM_PPN gpaw-python` → `mpirun -np $PBS_NUM_PPN python3`
- Add `#PBS -q luna` directive

### Post-processing: Not Needed on Cluster

Post-processing (`postprocess_*.py`) only needs NumPy to compute `f+ = ρ(N+1) - ρ(N)`, `f- = ρ(N) - ρ(N-1)`. This can be done locally after downloading the `.npy` density files. No need to submit post-processing PBS jobs.

---

## CO Rigid Scan Jobs — Issues & Fixes (2025-07-03)

### Context

`/storage/praha1/home/prokop/Fukui_AFM/jobs_CO_scan/` contains 28 baked Python scripts + 28 PBS scripts for CO rigid scan over selected atoms of each molecule. Each script scans CO at 24 distances (2.0–6.0 Å in 0.1 steps, then 0.25 steps, then 15.0 Å reference) and computes interaction energy `E_int(r) = E_total(r) - E_mol - E_CO`.

### Issues Found (same PBS bugs + restart logic)

#### 1–4. Same PBS issues as Fukui jobs

All 28 PBS scripts had the same 4 issues: wrong module name, missing `GPAW_SETUP_PATH`, missing `-q luna`, wrong executable (`gpaw-python` → `python3`). Fixed with the same sed commands.

#### 5. Broken restart logic — cell changes between frames

**Problem:** The scan uses `gpaw_restart()` to reuse wavefunctions between frames, but the cell z-dimension grows from 27.1 Å (r=2) to 40.1 Å (r=15). In PW mode, the plane-wave basis is tied to the cell — different cell means different G-vectors, so restart is useless. Additionally, the restart code only updated positions (`prev_atoms.positions = boxed`) but NOT the cell, so calculations ran with the wrong cell.

**Fix:** Use a constant cell (the largest one, `CELLS_PER_R[-1]`) for all frames. This ensures the PW basis is identical across frames, making restart effective. Added `prev_atoms.set_cell(cell, scale_atoms=False)` for safety.

**Lesson for LLM:** In GPAW PW mode, restart only works when the cell is identical between frames. If the cell changes, the wavefunctions are on a different G-grid and can't be reused. Use a constant cell (large enough for all frames) when doing scans with restart.

#### 6. Wrong convergence keyword `maxiter` → `maximum_iterations`

Same issue as Fukui anion jobs. Fixed in all 28 Python scripts.

#### 7. Duplicate atom in `MOL_BOXED` — generator bug

**Problem:** All 28 GPAW CO scan scripts had `MOL_BOXED` with one extra position — the target atom (ATOM_IDX) was duplicated and appended to the end. This caused `ValueError: Array "positions" has wrong length: 4 != 3` when creating the isolated molecule `Atoms(symbols=MOL_SYMS, positions=MOL_BOXED)`.

**Root cause:** The `generate_CO_scan_jobs.py` generator incorrectly included the target atom position in `MOL_BOXED` (which should only contain the original molecule atoms in the boxed cell).

**Fix:** Removed the last entry from `MOL_BOXED` in all 28 scripts. The PySCF scan scripts were not affected (they use `MOL_ATOM_STR` string format, not separate arrays).

**Lesson for LLM:** When baking scripts with molecule positions, verify that `len(MOL_SYMS) == len(MOL_BOXED)`. The generator should not mix combined-system positions (mol+CO) with molecule-only positions.

### Walltime Assessment

| Molecule group | Atoms (mol+CO) | CPUs | Memory | Walltime | Estimated runtime |
|---|---|---|---|---|---|
| H2O, CH2O, CH2NH, C2H4 | 5–8 | 4 | 8GB | 2h | ~40 min |
| pyrrol, pyridine | 12–13 | 8 | 16GB | 4h | ~1h |
| pentacene, PTCDA | 38–40 | 16 | 32GB | 12h | ~2h |

Walltimes are adequate with margin. The constant cell adds ~1.7x overhead for early frames, but restart savings (3-5 iterations vs 20+) more than compensate.

---

## PySCF Fukui Jobs — Issues & Fixes (2025-07-03)

### Context

`/storage/praha1/home/prokop/Fukui_AFM/pyscf_fukui_cluster/jobs/` contains 24 single-point + 8 post-processing baked scripts for computing Fukui functions using PySCF with Gaussian basis sets (def2-SVP/PBE). PySCF uses isolated-molecule all-electron DFT — no periodic box, no vacuum needed.

### PySCF on Metacentrum

PySCF is NOT available as a system module. It's installed via `pip install --user pyscf` (v2.13.1) in `~/.local` on top of the `mambaforge` module. PBS scripts use `module add mambaforge` which provides Python 3.10 + pip-installed PySCF.

**Key difference from GPAW:** PySCF uses OpenMP (threads), not MPI. Set `OMP_NUM_THREADS=$PBS_NUM_PPN`. No `mpirun`, just `python3 script.py`.

### Issues Found & Fixed

#### 1. Missing `-q luna` queue directive

Same issue as GPAW jobs. Added `#PBS -q luna` to all 32 PBS scripts.

#### 2. No density fitting — slow for large molecules

**Problem:** Original scripts used plain `dft.RKS(mol)` / `dft.UKS(mol)` without density fitting. For pentacene (~360 basis functions) and PTCDA (~420), the 4-center electron repulsion integrals (ERIs) scale as O(N⁴) — extremely slow.

**Fix:** Added `mf = mf.density_fit()` after setting `mf.xc`. This uses the RI-JK approximation, reducing scaling to O(N³) with automatic auxiliary basis selection. For large molecules this gives ~10x speedup with negligible accuracy loss.

**Lesson for LLM:** Always use `density_fit()` for PySCF DFT calculations on molecules with >50 basis functions. The call chain is:
```python
mf = dft.RKS(mol)
mf.xc = "PBE"
mf = mf.density_fit()  # returns new object with RI approximation
mf.kernel()
```
Note: `density_fit()` returns a NEW object — you must reassign `mf`.

### What Was Already Correct

- **`module add mambaforge`** — correct module for PySCF access
- **`OMP_NUM_THREADS=$PBS_NUM_PPN`** — correct, PySCF uses OpenMP not MPI
- **`python3 script.py`** — no `gpaw-python` or `mpirun` needed
- **UKS density matrix** — correctly sums alpha+beta DMs before cube generation (works around known PySCF `cubegen.density()` bug with UKS)
- **Cube grid** — `resolution=0.15` Bohr (~0.08 Å), `margin=4.0` Bohr (~2.1 Å) — reasonable for visualization
- **Scratch usage** — PBS scripts copy to `$SCRATCHDIR` and run there, avoiding slow AFS/home I/O

### Efficiency Notes

- **Density fitting** is the single most important PySCF optimization. Without it, ERIs scale O(N⁴); with RI-JK, O(N³). For pentacene/PTCDA this is hours vs minutes
- **No MPI** — PySCF parallelizes via threaded BLAS (OpenMP). Just set `OMP_NUM_THREADS`. No `mpirun` wrapper
- **Scratch disk is critical** — cube generation writes large files. Running on `$SCRATCHDIR` (local SSD) vs AFS/home can be 10x faster for I/O
- **Anion basis set** — `def2-SVP` lacks diffuse functions. For production anion calculations, use `def2-SVPD` or `def2-TZVPD` (diffuse functions essential for weakly bound anions). For testing, `def2-SVP` is acceptable
- **No SCF convergence issues expected** — PySCF with Gaussian basis sets handles anions much better than GPAW PW (no periodic image artifacts, no charge sloshing in large vacuum cells)

### Walltime Assessment

| Molecule | Atoms | Basis funcs (~def2-SVP) | CPUs | Memory | Walltime |
|---|---|---|---|---|---|
| H2O, CH2O, CH2NH, C2H4 | 3–6 | 25–48 | 4 | 8GB | 1h |
| pyrrol, pyridine | 10–11 | 100–110 | 4 | 8GB | 2h |
| pentacene, PTCDA | 36–38 | 360–420 | 8 | 16GB | 8h |

With density fitting, actual runtimes should be well under these limits. The 8h walltime for pentacene/PTCDA is generous.

### PySCF vs GPAW for Fukui Functions

| Aspect | PySCF | GPAW |
|---|---|---|
| Basis | Gaussian (def2-SVP) | Plane waves (PW 500 eV) |
| Periodicity | Isolated molecule | Periodic box + vacuum |
| Anion convergence | Generally fine (no PBC artifacts) | Problematic for small molecules (charge sloshing) |
| Parallelism | OpenMP (threads) | MPI |
| Module | `mambaforge` + pip | `py-gpaw/24.1.0-gcc-10.2.1-fojjhkw` |
| Key optimization | `density_fit()` | N/A (PW is inherently efficient) |
| Setup path | None needed | `GPAW_SETUP_PATH` must be set manually |
| Executable | `python3` | `python3` (NOT `gpaw-python`) |

---

## CO Rigid Scan — PySCF Jobs (`jobs_CO_scan_pyscf/`) (2025-07-03)

### Context

28 baked scripts for CO rigid scan using PySCF DFT PBE/def2-SVP. Each script computes E_mol, E_CO, then scans 24 distances. Uses `MOL_ATOM_STR` (string format) instead of separate arrays — no `MOL_BOXED` bug.

### Issues Found & Fixed

#### 1. Wrong module: `module add pyscf` → `module add mambaforge`

**Problem:** PBS scripts used `module add pyscf` but no such module exists on Metacentrum. PySCF is installed via `pip install --user pyscf` on top of `mambaforge`.

**Fix:** Changed to `module add mambaforge` in all 28 PBS scripts.

#### 2. Missing `-q luna`

Same as all previous jobs. Added `#PBS -q luna`.

#### 3. Hardcoded `OMP_NUM_THREADS` and `lib.num_threads`

**Problem:** PBS scripts had `export OMP_NUM_THREADS=4` (or 8) hardcoded, and Python scripts had `lib.num_threads = 4` (or 8) hardcoded. If the PBS resource allocation changes, these would be wrong.

**Fix:** Changed PBS to `export OMP_NUM_THREADS=$PBS_NUM_PPN` and Python to `lib.num_threads = int(os.environ.get("OMP_NUM_THREADS", 4))`.

#### 4. No density fitting

**Problem:** All 3 SCF objects per script (mol, CO, scan frames) used plain `dft.RKS()` without density fitting. For pentacene+CO (~380 basis functions), this is extremely slow.

**Fix:** Added `mf = mf.density_fit()` after `mf.xc = XC` for all 3 SCF objects (`mf_mol`, `mf_co`, `mf_tot`). Note: must be done AFTER setting `.xc` and BEFORE setting `.grids.level`.

**Lesson for LLM:** In scan scripts with multiple SCF calculations, apply `density_fit()` to ALL `mf` objects, not just the largest one. The overhead for small molecules is negligible.

### PySCF Scan vs GPAW Scan

| Aspect | PySCF scan | GPAW scan |
|---|---|---|
| Cell/box | No cell needed (molecular) | Constant cell for PW restart |
| Restart between frames | Not needed (fast SCF) | `gpaw_restart()` with constant cell |
| Init guess | `init_guess='vsap'` for ir>0 | Wavefunction restart from previous frame |
| Speed (small mol) | ~2 min total | ~40 min total |
| Speed (large mol) | ~30 min with density_fit | ~2h with restart |
| Generator bug risk | Low (uses string format) | High (uses separate arrays) |

---

## Summary of Recurring Issues — Lessons for LLM

### Module/Environment Issues (recurring across ALL job types)

1. **`module add gpaw` doesn't work** — must use `module add py-gpaw/24.1.0-gcc-10.2.1-fojjhkw`
2. **`module add pyscf` doesn't exist** — must use `module add mambaforge` (PySCF via pip)
3. **`GPAW_SETUP_PATH` must be set manually** — `export GPAW_SETUP_PATH=/software/gpaw/1.4.0/setup_files/gpaw-setups-0.9.20000`
4. **`#PBS -q luna` missing** — always add queue directive
5. **`gpaw-python` doesn't exist** — use `mpirun -np $PBS_NUM_PPN python3`
6. **PySCF uses OpenMP, not MPI** — `OMP_NUM_THREADS=$PBS_NUM_PPN`, no `mpirun`

**Action:** Always check `module avail <name>` before writing `module add` in PBS scripts. When a package is pip-installed, use the base Python module (`mambaforge`) not the package name.

### GPAW-Specific Issues

1. **`maxiter` is a constructor argument**, NOT a convergence dict key. Convergence dict uses spaces: `'maximum iterations'`, not underscores.
2. **PW restart requires constant cell** — different cell = different G-vectors = useless restart.
3. **Anion SCF convergence** — small molecule anions in PW may be unbound. Use `Mixer(0.05, 5, 1.0)` + `maxiter=500`. If still fails, the anion is likely physically unbound in that cell.

### PySCF-Specific Issues

1. **`density_fit()` is essential** for >50 basis functions. Returns NEW object — must reassign.
2. **No SCF convergence issues** with Gaussian basis sets for anions (no PBC artifacts).
3. **`def2-SVP` lacks diffuse functions** — use `def2-SVPD` for production anion work.

### Generator/Baking Issues

1. **`MOL_BOXED` duplicate atom** — generator appended target atom to molecule positions. Always verify `len(symbols) == len(positions)`.
2. **Bracket corruption when editing baked scripts** — using `sed` to remove array entries can leave unmatched brackets. Always run `python3 -c "compile(open(f).read(), f, 'exec')"` to verify syntax after editing.

### Process Lessons

1. **Always verify syntax after sed edits** — `compile()` check before submitting jobs.
2. **Always check job output immediately** — `cat *.o* | grep Error` within minutes of submission.
3. **Test one job before batch submission** — submit one, check output, then batch.
4. **Scratch disk is critical** — PBS scripts must copy to `$SCRATCHDIR` and run there. AFS/home I/O is 10x slower.
5. **Document every issue** — the same bugs recur across job sets from the same generator.