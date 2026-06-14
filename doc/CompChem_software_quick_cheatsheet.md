# Quantum Chemistry Software Quick Cheatsheet

**Last Updated:** June 14, 2026

For machine-specific paths, see `EVIROMENTS_AND_MACHINES/Prokop_Desktop_GTX3090.md`.

---

## 1. Which Software for Which Task?

| Task | Software | Method |
|------|----------|--------|
| Small molecule DFT (<50 atoms) | pySCF, Psi4, ORCA | B3LYP, PBE |
| Large molecule DFT (50-500 atoms) | DFTB+, xtb | GFN-xTB, DFTB |
| Post-HF (MP2, CCSD) | Psi4, ORCA, pySCF | MP2, CCSD(T) |
| Periodic solids | DFTB+, GPAW, CP2K | DFT, DFTB |
| Classical MD | LAMMPS | Force fields |
| Geometry optimization | Any | `Opt`, `--opt` |
| Frequencies | Psi4, ORCA, xtb | `Freq`, `--hess` |
| RESP charges | Psi4 | RESP |
| Phonons | DFTB+ + Phonopy | Finite differences |

## 1.5 GUIs and Visualization Tools

### JupyterLab + nglview + py3Dmol (Interactive Notebooks)

**Purpose:** Interactive 3D molecular visualization inside Jupyter notebooks. Best for:
- Teaching, scripting, and reproducible workflows
- Viewing trajectories, orbitals, and charge densities
- Combining computation (pySCF, ASE, xtb) with live 3D views

**Usage:**
```python
import nglview
import py3Dmol
view = nglview.show_ase(atoms)  # ASE Atoms object
view  # renders in notebook
```

### ASE-GUI (Atomistic Viewer)

**Purpose:** Lightweight viewer/editor for atomic structures. Best for:
- Quick inspection of XYZ, CIF, and trajectory files
- Setting up unit cells and supercells
- Viewing geometry optimization progress

**Usage:** `ase gui structure.xyz`

### Avogadro 2 + avo_xtb Plugin (3D Builder + xTB)

**Purpose:** Full 3D molecular builder with integrated xTB/CREST. Best for:
- Drawing molecules and clicking "Optimize" (GFN-xTB)
- Conformer searches (CREST) with result loading
- Visualizing orbitals and vibrational modes

**Install plugin:** Open Avogadro2 → Extensions → Plugin Downloader → search "avo_xtb" → Download Selected → Restart

### ASH (Python Workflow Wrapper)

**Purpose:** Scriptable multi-scale quantum chemistry workflows. Best for:
- Chaining xTB → ORCA → QM/MM calculations
- Automating geometry optimizations and MD
- Bridging ASE, pySCF, DFTB+, MOPAC, and ORCA in one Python script

**Usage:**
```python
from ash import *
frag = Fragment(pdbfile="molecule.pdb")
xtb = xTBTheory(xtbmethod="GFN2-xTB")
Singlepoint(theory=xtb, fragment=frag)
```

### Atomistica Desktop GUIs (Standalone)

**Purpose:** Point-and-click launchers for xTB and ORCA. Best for:
- Beginners who want no command-line
- Live job monitoring with CPU/disk tracking
- Batch modeling and teaching

**Binaries:** `xtb_GUI` (xTB) and `atomistica_1_10_linux` (ORCA launcher)

### Gabedit (Universal QC GUI)

**Purpose:** Mature input builder and output parser. Best for:
- Building ORCA, MOPAC, Gaussian input files visually
- Plotting IR/Raman/UV-Vis spectra from output
- Visualizing molecular orbitals and electron density

**Usage:** Download from https://gabedit.sourceforge.net/ → extract → `./gabedit`

## 2. One-Liner Commands

```bash
# pySCF (Python)
python -c "from pyscf import gto,dft; mol=gto.M(atom='H 0 0 0; H 0 0 0.74',basis='6-31g'); mf=dft.RKS(mol); mf.xc='b3lyp'; print(mf.kernel())"

# DFTB+
dftb+ < dftb_in.hsd

# CP2K (parallel)
mpiexec -n 4 cp2k.psmp input.inp

# LAMMPS
lmp_serial -in input.lammps

# ORCA
orca input.inp > output.out

# xtb single point
xtb molecule.xyz --sp

# xtb optimization
xtb molecule.xyz --opt

# Psi4
python -c "import psi4; mol=psi4.geometry('H\nH 1 0.74'); print(psi4.energy('b3lyp/cc-pvdz'))"

# GPAW (Python)
python -c "from gpaw import GPAW,PW; from ase import Atoms; a=Atoms('H2',[[0,0,0],[0,0,0.74]]); a.calc=GPAW(mode=PW(300)); print(a.get_potential_energy())"
```

---

## 3. pySCF

### Install
```bash
pip install pyscf
# GPU: pip install gpu4pyscf-cuda12x
# Extras: pip install pyscf-dispersion pyscf-semiempirical
```

### Minimal Example
```python
from pyscf import gto, dft
mol = gto.M(atom='H 0 0 0; H 0 0 0.74', basis='6-31g')
mf = dft.RKS(mol); mf.xc = 'b3lyp'
print(mf.kernel())  # energy in Hartree
```

### Methods
```python
from pyscf import scf, mp, cc, ci, tdscf

mf = scf.RHF(mol).run()      # HF
mf = dft.RKS(mol).run()      # DFT (set mf.xc = 'b3lyp')
mp2 = mp.MP2(mf).run()       # MP2
ccsd = cc.CCSD(mf).run()     # CCSD
cisd = ci.CISD(mf).run()     # CISD
td = tdscf.TDRKS(mf).run()   # TD-DFT
```

### GPU
```python
from gpu4pyscf.dft import rks
mf = rks.RKS(mol); mf.xc = 'b3lyp'; mf.kernel()
```

### Geometry / Freq
```python
from pyscf import geomopt, hessian
mol_eq = geomopt.optimize(mf)           # optimization
hess = hessian.RHF(mf).kernel()          # hessian
freq = hessian.freq_analysis(hess)       # frequencies
```

---

## 4. DFTB+

### Install
```bash
conda install -c conda-forge dftbplus   # or build from source
```

### Minimal Input (dftb_in.hsd)
```hsd
Geometry = GenFormat { { C  C 2  0.0 0.0 0.0  0.0 0.0 1.54 } }
Hamiltonian = DFTB {
  SCC = Yes
  SlaterKosterFiles = Type2FileNames {
    Prefix = "/path/to/slakos/"  Separator = "-"  Suffix = ".skf"
  }
  MaxAngularMomentum { C = p }
}
Options { WriteResultsTag = Yes }
Analysis { CalculateForces = Yes }
```

### Run
```bash
dftb+
```

### ASE Interface
```python
from ase.calculators.dftb import Dftb
calc = Dftb(Hamiltonian_SCC='Yes',
    Hamiltonian_MaxAngularMomentum_C='"p"',
    Hamiltonian_SlaterKosterFiles_Prefix='/path/to/slakos/',
    kpts=(1,1,1))
atoms.set_calculator(calc)
print(atoms.get_potential_energy())
```

### Phonons (with Phonopy)
```bash
phonopy -d --dim="2 2 2" --dftb+               # generate displacements
for d in disp-*/; do (cd "$d" && dftb+); done  # run all
phonopy -f disp-*/results.tag --dftb+          # collect
phonopy -p band.conf --dim="2 2 2" --dftb+     # bands
```

---

## 5. CP2K

### Install
```bash
conda create -n cp2k_env -c conda-forge cp2k
```

### Minimal Input (input.inp)
```
&FORCE_EVAL
  METHOD DFT
  &DFT
    &XC
      &XC_FUNCTIONAL PBE
      &END
    &END
  &END
  &SUBSYS
    &KIND H;  BASIS_SET DZVP-MOLOPT-GTH;  POTENTIAL GTH-PBE;  &END
    &COORD
      H 0.0 0.0 0.0
      H 0.0 0.0 0.74
    &END
  &END
&END
&GLOBAL;  RUN_TYPE ENERGY;  &END
```

### Run
```bash
cp2k.psmp input.inp
mpiexec -n 4 cp2k.psmp input.inp   # parallel
```

### Keywords
```
RUN_TYPE  GEO_OPT   # geometry optimization
RUN_TYPE  MD        # molecular dynamics
RUN_TYPE  ENERGY    # single point

&MOTION
  &GEO_OPT;  OPTIMIZER BFGS;  MAX_ITER 100;  &END
  &MD;  ENSEMBLE NVT;  STEPS 1000;  TIMESTEP 1.0;  TEMPERATURE 300.0;  &END
&END
```

---

## 6. LAMMPS

### Install
```bash
conda install -c conda-forge lammps   # or build from source
```

### Minimal Input (in.lammps)
```
units metal
atom_style atomic
read_data system.data
pair_style tersoff
pair_coeff * * Si.tersoff Si
run 0
```

### Run
```bash
lmp_serial -in in.lammps
```

### Python
```python
from lammps import lammps
lmp = lammps()
lmp.file("in.lammps")
print(lmp.get_thermo("pe"))
```

### Potentials
```
pair_style tersoff;    pair_coeff * * Si.tersoff Si
pair_style sw;         pair_coeff * * Si.sw Si
pair_style meam;       pair_coeff * * library.meam Si.meam Si NULL Si
```

---

## 7. GPAW (Python)

### Install
```bash
pip install gpaw
# Datasets: gpaw install-data
```

### Minimal Example
```python
from gpaw import GPAW, PW
from ase import Atoms
a = Atoms('H2', positions=[[0,0,0],[0,0,0.74]])
a.calc = GPAW(mode=PW(300), xc='PBE')
print(a.get_potential_energy())
```

### Common Settings
```python
# Band structure
calc = GPAW(mode=PW(300), xc='PBE', kpts=(4,4,4))

# DOS
from gpaw import DOS
dos = DOS(calc)

# Geometry optimization
from ase.optimize import BFGS
BFGS(a).run(fmax=0.05)
```

---

## 8. Psi4 (Python)

### Install
```bash
conda create -n psi4_env -c conda-forge psi4
conda install -c psi4 resp
```

### Minimal Example
```python
import psi4
mol = psi4.geometry("H\nH 1 0.74")
print(psi4.energy('b3lyp/cc-pvdz'))
```

### Methods
```python
psi4.energy('hf/cc-pvdz')        # Hartree-Fock
psi4.energy('b3lyp/cc-pvdz')     # DFT
psi4.energy('mp2/cc-pvdz')       # MP2
psi4.energy('ccsd/cc-pvdz')      # CCSD
psi4.energy('ccsd(t)/cc-pvdz')   # CCSD(T)
```

### Tasks
```python
psi4.optimize('b3lyp/cc-pvdz')      # geometry optimization
psi4.frequency('b3lyp/cc-pvdz')     # frequencies
psi4.properties('dipole')           # properties
```

### RESP Charges
```python
import resp
resp.resp([mol], [options])
```

---

## 9. ORCA

### Install
Download from ORCA forum (academic license required).

### Minimal Input (input.inp)
```
! B3LYP def2-SVP Opt

%pal nprocs 4 end

* xyz 0 1
C 0.0 0.0 0.0
H 0.0 0.0 1.09
*
```

### Run
```bash
orca input.inp > output.out
```

### Keywords
```
! HF def2-SVP          # Hartree-Fock
! B3LYP def2-TZVP      # DFT
! MP2 def2-TZVP        # MP2
! CCSD(T) def2-TZVP    # CCSD(T)

! Opt     # optimization
! Freq    # frequencies
! SP      # single point
! NumFreq # numerical frequencies

! D3BJ    # D3 dispersion with BJ damping

%pal nprocs 4 end       # parallel
%maxcore 1000           # memory per core (MB)

%cpcm
  epsilon 78.4          # water solvent
end
```

---

## 10. xtb (GFN-xTB)

### Install
```bash
conda install -c conda-forge xtb
```

### Commands
```bash
xtb molecule.xyz --sp              # single point
xtb molecule.xyz --opt             # optimization
xtb molecule.xyz --hess            # frequencies
xtb molecule.xyz --ohess           # opt + hess

xtb molecule.xyz --gfn 1           # GFN1-xTB
xtb molecule.xyz --gfn 2           # GFN2-xTB (default)
xtb molecule.xyz --alpb water     # implicit solvent
xtb molecule.xyz --chrg -1 --uhf 1  # charge and spin
```

### CREST (Conformer Search)
```bash
crest molecule.xyz --gfn 2
```

---

## 12. MOPAC

### Install
Download from MOPAC website (commercial license required).

### Minimal Input (input.mop)
```
PM7 CHARGE=0 SINGLET OPT
Title

C 0.0 0.0 0.0
H 0.0 0.0 1.09
```

### Run
```bash
mopac input.mop
```

### Keywords
```
PM6     # PM6 method
PM7     # PM7 method (recommended)
OPT     # optimization
FORCE   # frequencies
GRADIENTS

CHARGE=n    # charge
SINGLET     # spin state
DOUBLET
TRIPLET
```

---

## 13. ASE (Universal Interface)

### Install
```bash
pip install ase
```

### Minimal Example
```python
from ase import Atoms
from ase.calculators.emt import EMT

atoms = Atoms('H2', positions=[[0,0,0],[0,0,0.74]])
atoms.calc = EMT()
print(atoms.get_potential_energy())
```

### Calculators
```python
from ase.calculators.dftb import Dftb
from ase.calculators.psi4 import Psi4
from ase.calculators.orca import ORCA
from gpaw import GPAW

atoms.calc = Dftb(...)
atoms.calc = Psi4(method='b3lyp', basis='cc-pvdz')
atoms.calc = ORCA(orcasimpleinput='B3LYP def2-SVP')
atoms.calc = GPAW(mode=PW(300))
```

### Tasks
```python
from ase.optimize import BFGS
BFGS(atoms).run(fmax=0.05)           # optimization

from ase.md import Langevin
dyn = Langevin(atoms, timestep=0.5*ase.units.fs, temperature=300*ase.units.K)
dyn.run(1000)                         # MD

from ase.neb import NEB
images = [initial.copy() for _ in range(5)] + [final]
neb = NEB(images); neb.interpolate()
BFGS(neb).run(fmax=0.05)             # NEB
```

---

## 14. Common Workflows

### Geometry Optimization (ASE)
```python
from ase import Atoms
from ase.optimize import BFGS
from ase.calculators.emt import EMT

atoms = Atoms('H2', positions=[[0,0,0],[0,0,0.74]])
atoms.calc = EMT()
BFGS(atoms).run(fmax=0.05)
print(atoms.get_potential_energy())
```

### Frequencies (Psi4)
```python
import psi4
mol = psi4.geometry("O\nH 1 0.96\nH 1 0.96 2 104.5")
psi4.optimize('b3lyp/cc-pvdz')
psi4.frequency('b3lyp/cc-pvdz')
```

### Frequencies (ORCA)
```
! B3LYP def2-SVP Opt Freq
* xyz 0 1
O 0.0 0.0 0.0
H 0.0 0.76 0.59
H 0.0 -0.76 0.59
*
```

### Phonons (DFTB+ + Phonopy)
```bash
phonopy -d --dim="2 2 2" --dftb+
for d in disp-*/; do (cd "$d" && dftb+); done
phonopy -f disp-*/results.tag --dftb+
phonopy -p band.conf --dim="2 2 2" --dftb+
```

### PES Scan (Psi4)
```python
import psi4, numpy as np
mol = psi4.geometry("H\nH 1 0.74")
for d in np.linspace(0.5, 2.0, 20):
    mol.R(0, 1, d)
    print(d, psi4.energy('b3lyp/cc-pvdz'))
```

### MD (ASE + LAMMPS)
```python
from ase.md import Langevin
from ase.units import fs, K
dyn = Langevin(atoms, timestep=1.0*fs, temperature=300*K, friction=0.02)
dyn.run(10000)
```

---

## 15. Tips

### Choosing Method by System Size
| Size | Method | Speed |
|------|--------|-------|
| < 50 atoms | DFT (B3LYP, PBE) | Medium |
| 50-500 atoms | DFTB+, xtb | Fast |
| > 500 atoms | LAMMPS, MOPAC | Very fast |

### Troubleshooting
- **SCF not converging:** Try different guess, use damping/level shifting
- **Opt failing:** Check geometry, reduce step size, try different optimizer
- **Memory errors:** Reduce basis, decrease k-points, use density fitting

### Performance
- Use MPI for large systems, OpenMP for medium
- Use GPU (pySCF, GPAW) when available
- Start with small basis, scale up for production

---

## References

- **pySCF:** https://pyscf.org/  |  **DFTB+:** https://dftbplus.org/
- **CP2K:** https://www.cp2k.org/  |  **LAMMPS:** https://docs.lammps.org/
- **GPAW:** https://wiki.fysik.dtu.dk/gpaw/  |  **Psi4:** https://psicode.org/
- **ORCA:** https://orcaforum.cec.mpg.de/  |  **xtb:** https://xtb-docs.readthedocs.io/
- **ASE:** https://wiki.fysik.dtu.dk/ase/
