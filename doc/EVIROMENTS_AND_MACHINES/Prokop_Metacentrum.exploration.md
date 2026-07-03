
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
