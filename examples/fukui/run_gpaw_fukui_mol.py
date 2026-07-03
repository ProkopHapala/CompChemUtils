#!/usr/bin/env python3
"""Compute Fukui functions for isolated molecules using GPAW (plane-wave PBE).

Runs single-point DFT for N, N+1, N-1 charge states at fixed geometry,
writes all-electron density .cube files, then subtracts to obtain
f+, f-, f0 Fukui grids.

Molecules are placed in a periodic box with vacuum padding and computed
at gamma-point only (kpts=(1,1,1)).

Usage (local quick test):
    python run_gpaw_fukui_mol.py --mol H2O --ecut 200 --vacuum 8.0
    python run_gpaw_fukui_mol.py --mol CH2O --ecut 200 --vacuum 8.0

Usage (cluster, high cutoff):
    python run_gpaw_fukui_mol.py --mol pentacene --ecut 500 --vacuum 12.0
    python run_gpaw_fukui_mol.py --batch --ecut 500 --vacuum 12.0

Results: results_gpaw/<mol>_PBE_<ecut>eV/
"""

import os, sys, argparse
import numpy as np

fukui_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, fukui_dir)
from fukui_backend import read_cube, write_cube

XYZ_DIR = os.environ.get('CCU_XYZ_DIR', '/home/prokop/git/CompChemUtils/data/xyz')
OUTDIR  = os.path.join(fukui_dir, 'results_gpaw')

# Molecules to compute
MOLECULES = ['H2O', 'CH2O', 'CH2NH', 'C2H4', 'pyrrol', 'pentacene', 'PTCDA']


def read_xyz_to_atoms(fname):
    """Read XYZ file into ASE Atoms, centered in a vacuum box."""
    from ase.io import read
    atoms = read(fname)
    return atoms


def make_boxed_atoms(atoms, vacuum=10.0):
    """Center molecule in a cubic cell with vacuum padding."""
    from ase import Atoms
    pos = atoms.positions
    rmin = pos.min(axis=0)
    rmax = pos.max(axis=0)
    extent = rmax - rmin
    cell = extent + 2 * vacuum
    # Center molecule in cell
    center = 0.5 * cell
    mol_center = 0.5 * (rmin + rmax)
    shift = center - mol_center
    new_atoms = atoms.copy()
    new_atoms.positions = pos + shift
    new_atoms.cell = cell
    new_atoms.pbc = [True, True, True]
    return new_atoms


def count_valence_electrons(atoms):
    """Count total valence electrons (neutral)."""
    from ase.data import atomic_numbers
    # GPAW uses PAW datasets; valence e- = Z - core
    # For first-row (H, C, N, O) all electrons are valence in default setups
    return sum(atomic_numbers[a.symbol] for a in atoms)


def run_gpaw_sp(atoms, charge, spinpol, ecut, xc, outdir, tag, fd_width=0.05):
    """Run GPAW single-point and return (atoms, calc)."""
    from gpaw import GPAW, PW, FermiDirac
    calc = GPAW(
        mode=PW(ecut),
        xc=xc,
        charge=charge,
        spinpol=spinpol,
        occupations=FermiDirac(fd_width),
        kpts=(1, 1, 1),  # gamma only for isolated molecule
        symmetry='off',
        convergence={'energy': 1e-5, 'density': 1e-5, 'bands': 'occupied'},
        txt=os.path.join(outdir, f'{tag}.txt'),
    )
    a = atoms.copy()
    a.calc = calc
    E = a.get_potential_energy()
    print(f"    [{tag}] E = {E:.6f} eV  (charge={charge}, spinpol={spinpol})")
    return a, calc


def write_density_cube(atoms, calc, fname):
    """Write all-electron density cube via ASE.
    GPAW returns density in Å⁻³; cube files use Bohr grid vectors,
    so convert to Bohr⁻³ for consistency."""
    from ase.io import write
    B2A = 0.529177210903  # Bohr to Angstrom
    rho = calc.get_all_electron_density() * B2A**3  # Å⁻³ -> Bohr⁻³
    write(fname, atoms, data=rho)
    print(f"    Cube: {fname}")


def compute_fukui_for_molecule(mol_name, ecut, vacuum, xc, outdir, xyz_dir=None):
    """Full GPAW Fukui workflow for one molecule."""
    from ase.io import read
    if xyz_dir is None:
        xyz_dir = XYZ_DIR

    os.makedirs(outdir, exist_ok=True)
    xyz_path = os.path.join(xyz_dir, f'{mol_name}.xyz')
    if not os.path.isfile(xyz_path):
        print(f"ERROR: {xyz_path} not found")
        sys.exit(1)

    atoms = read(xyz_path)
    natoms = len(atoms)
    nelec = count_valence_electrons(atoms)
    boxed = make_boxed_atoms(atoms, vacuum=vacuum)

    print(f"\n{'='*60}")
    print(f"  Molecule: {mol_name}  ({natoms} atoms, {nelec} e-)")
    print(f"  Method:   GPAW {xc}  PW({ecut} eV)")
    print(f"  Vacuum:   {vacuum} A  ->  cell = {boxed.cell.diagonal()}")
    print(f"  kpts:     gamma only")
    print(f"{'='*60}")

    # Spin: all our molecules have even e- -> neutral singlet, anion/cation doublet
    neutral_even = (nelec % 2) == 0
    spin_N = not neutral_even  # False for even (closed shell)
    spin_A = not spin_N        # anion: opposite spin
    spin_C = not spin_N        # cation: opposite spin
    # For even e-: N=spinpol False, A=spinpol True, C=spinpol True
    # For odd e-: N=spinpol True, A=spinpol False, C=spinpol False
    if neutral_even:
        spin_N, spin_A, spin_C = False, True, True
    else:
        spin_N, spin_A, spin_C = True, False, False

    print(f"  Spin: N={spin_N}, A={spin_A}, C={spin_C}")

    # Neutral (N)
    print("\n  Neutral (N)  ...")
    _, calc_N = run_gpaw_sp(boxed, charge=0, spinpol=spin_N, ecut=ecut, xc=xc, outdir=outdir, tag='N')
    write_density_cube(boxed, calc_N, os.path.join(outdir, 'rho_N.cube'))

    # Anion (N+1)
    print("  Anion (N+1) ...")
    _, calc_A = run_gpaw_sp(boxed, charge=-1, spinpol=spin_A, ecut=ecut, xc=xc, outdir=outdir, tag='A')
    write_density_cube(boxed, calc_A, os.path.join(outdir, 'rho_A.cube'))

    # Cation (N-1)
    print("  Cation (N-1) ...")
    _, calc_C = run_gpaw_sp(boxed, charge=1, spinpol=spin_C, ecut=ecut, xc=xc, outdir=outdir, tag='C')
    write_density_cube(boxed, calc_C, os.path.join(outdir, 'rho_C.cube'))

    # Compute Fukui grids
    print("\n  Computing Fukui grids ...")
    rho_N, origin, shape, vecs, atoms_cube = read_cube(os.path.join(outdir, 'rho_N.cube'))
    rho_A, _, _, _, _ = read_cube(os.path.join(outdir, 'rho_A.cube'))
    rho_C, _, _, _, _ = read_cube(os.path.join(outdir, 'rho_C.cube'))

    f_plus  = rho_A - rho_N
    f_minus = rho_N - rho_C
    f_zero  = 0.5 * (f_plus + f_minus)

    for tname, grid in [('fukui_f_plus', f_plus), ('fukui_f_minus', f_minus), ('fukui_f_zero', f_zero)]:
        np.save(os.path.join(outdir, f'{tname}.npy'), grid)
        write_cube(os.path.join(outdir, f'{tname}.cube'), grid, origin, vecs, atoms_cube,
                   comment1=f'{mol_name} Fukui {tname}', comment2=f'GPAW {xc} PW({ecut}eV)')
        print(f"    {tname}: range [{grid.min():.3e}, {grid.max():.3e}]")

    # Integrated totals (sanity check: f+ should integrate to ~+1, f- to ~+1)
    dx, dy, dz = vecs[0][0], vecs[1][1], vecs[2][2]
    dV = abs(dx * dy * dz)
    int_f_plus  = np.sum(f_plus)  * dV
    int_f_minus = np.sum(f_minus) * dV
    int_f_zero  = np.sum(f_zero)  * dV
    print(f"\n  Integrated f+: {int_f_plus:.4f} e  (expect ~+1)")
    print(f"  Integrated f-: {int_f_minus:.4f} e  (expect ~+1)")
    print(f"  Integrated f0: {int_f_zero:.4f} e  (expect ~+1)")

    # Save energy summary
    with open(os.path.join(outdir, 'summary.txt'), 'w') as f:
        f.write(f"Molecule: {mol_name}\n")
        f.write(f"Method: GPAW {xc} PW({ecut} eV)\n")
        f.write(f"Vacuum: {vacuum} A, cell = {boxed.cell.diagonal()}\n")
        f.write(f"Atoms: {natoms}, Electrons: {nelec}\n")
        f.write(f"Integrated f+: {int_f_plus:.6f}\n")
        f.write(f"Integrated f-: {int_f_minus:.6f}\n")
        f.write(f"Integrated f0: {int_f_zero:.6f}\n")

    print(f"\n  Results: {outdir}")
    return outdir


def main():
    parser = argparse.ArgumentParser(description='GPAW Fukui functions for isolated molecules')
    parser.add_argument('--mol', type=str, default=None, help='Molecule name (e.g. H2O, CH2O, pentacene)')
    parser.add_argument('--batch', action='store_true', help='Run all molecules in MOLECULES list')
    parser.add_argument('--ecut', type=float, default=400.0, help='Plane-wave cutoff in eV (default: 400)')
    parser.add_argument('--vacuum', type=float, default=10.0, help='Vacuum padding in Angstrom (default: 10)')
    parser.add_argument('--xc', type=str, default='PBE', help='XC functional (default: PBE)')
    parser.add_argument('--outdir', type=str, default=OUTDIR, help='Output root directory')
    parser.add_argument('--xyz-dir', type=str, default=XYZ_DIR, help='Directory containing .xyz files')
    args = parser.parse_args()

    if args.batch:
        mols = MOLECULES
    elif args.mol:
        mols = [args.mol]
    else:
        parser.error('Specify --mol <name> or --batch')

    for mol in mols:
        tag = f"{mol}_{args.xc}_{int(args.ecut)}eV"
        resdir = os.path.join(args.outdir, tag)
        compute_fukui_for_molecule(mol, ecut=args.ecut, vacuum=args.vacuum, xc=args.xc, outdir=resdir, xyz_dir=args.xyz_dir)

    print(f"\n{'='*60}")
    print(f"  All done. Results in: {args.outdir}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
