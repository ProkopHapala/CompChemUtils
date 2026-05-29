import subprocess
import numpy as np
from ase.io import read
from ase import units

atoms = read('/home/prokop/git/FireCore/cpp/common_resources/xyz/CH4.xyz')
atoms.center(vacuum=10.0)
atoms.pbc = True

# Write CP2K input
symbols = atoms.get_chemical_symbols()
pos = atoms.get_positions()
cell = atoms.get_cell()

inp = f"""&GLOBAL
   PROJECT ch4
   PRINT_LEVEL MEDIUM
&END GLOBAL

&FORCE_EVAL
   METHOD Quickstep
   &DFT
      BASIS_SET_FILE_NAME BASIS_MOLOPT
      POTENTIAL_FILE_NAME POTENTIAL
      &MGRID
         CUTOFF 400
         REL_CUTOFF 50
      &END MGRID
      &SCF
         MAX_SCF 200
         EPS_SCF 1.0E-5
         SCF_GUESS ATOMIC
         &OT
           MINIMIZER DIIS
         &END OT
         &OUTER_SCF
           MAX_SCF 10
           EPS_SCF 1.0E-5
         &END OUTER_SCF
      &END SCF
      &XC
         &XC_FUNCTIONAL
            &PBE
            &END PBE
         &END XC_FUNCTIONAL
      &END XC
   &END DFT
   &SUBSYS
      &COORD
"""
for s, p in zip(symbols, pos):
    inp += f"         {s} {p[0]:.10f} {p[1]:.10f} {p[2]:.10f}\n"

inp += """      &END COORD
      &CELL
         PERIODIC XYZ
"""
for i in range(3):
    inp += f"         {'ABC'[i]} {cell[i,0]:.10f} {cell[i,1]:.10f} {cell[i,2]:.10f}\n"
inp += """      &END CELL
      &KIND C
         BASIS_SET DZVP-MOLOPT-SR-GTH
         POTENTIAL GTH-PBE
      &END KIND
      &KIND H
         BASIS_SET DZVP-MOLOPT-SR-GTH
         POTENTIAL GTH-PBE
      &END KIND
   &END SUBSYS
&END FORCE_EVAL
"""

with open('ch4.inp', 'w') as f:
    f.write(inp)

# Run CP2K
result = subprocess.run(['mpirun', '-np', '4', 'cp2k.psmp', '-i', 'ch4.inp', '-o', 'ch4.out'],
                       capture_output=True, text=True)
print(f"Return code: {result.returncode}")

# Parse energy and forces from output
with open('ch4.out', 'r') as f:
    lines = f.readlines()

energy_ev = None
forces = []
reading_forces = False
for line in lines:
    if 'ENERGY| Total FORCE_EVAL ( QS ) energy [hartree]' in line:
        energy_hartree = float(line.split()[-1])
        energy_ev = energy_hartree * units.Hartree
        print(f"Energy: {energy_ev:.4f} eV")
    
    if 'ATOMIC FORCES in [a.u.]' in line or 'FORCES ON THE ATOMS' in line:
        reading_forces = True
        forces = []
        continue
    
    if reading_forces:
        parts = line.strip().split()
        if len(parts) >= 6 and parts[0].isdigit():
            # Parse force line: atom_idx element x y z fx fy fz
            fx, fy, fz = float(parts[-3]), float(parts[-2]), float(parts[-1])
            forces.append([fx, fy, fz])
        elif '&END' in line or len(parts) == 0:
            reading_forces = False

if forces:
    forces = np.array(forces)
    # Convert from Hartree/Bohr to eV/Angstrom
    forces_ev = forces * units.Hartree / units.Bohr
    fmax = np.linalg.norm(forces_ev, axis=1).max()
    print(f"Forces (eV/A):\n{forces_ev}")
    print(f"fmax: {fmax:.2f} eV/A")
else:
    print("No forces found in output")
    # Print last 50 lines to debug
    print("Last 50 lines of output:")
    for line in lines[-50:]:
        print(line.strip())
