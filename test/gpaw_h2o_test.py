from ase.build import molecule
from gpaw import GPAW

atoms = molecule('H2O', vacuum=4.0)
atoms.calc = GPAW(mode='lcao', txt='h2o_lcao.txt')
E = atoms.get_potential_energy()
print(f"H2O LCAO energy: {E:.6f} eV")
