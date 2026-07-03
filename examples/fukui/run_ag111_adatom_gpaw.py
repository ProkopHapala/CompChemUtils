#!/usr/bin/env python3
"""Compute Fukui functions for M(111) surface with adatom using GPAW (periodic DFT).

Supports Ag, Au, Cu. Uses PBE, small vacuum in z, and 2x2 k-sampling.
Writes electron-density .cube files for N, N+1, N-1 charge states,
then computes f+, f-, f0 Fukui grids as both .npy and .cube files.

Usage:
    venvML && python run_ag111_adatom_gpaw.py --metal Ag
    venvML && python run_ag111_adatom_gpaw.py --metal Au
    venvML && python run_ag111_adatom_gpaw.py --metal Cu

Results: results_metal/{metal}111_2x2x2_adatom_GPAW_PBE/
"""

import os
import sys
import argparse
import numpy as np
from ase.build import fcc111, add_adsorbate
from ase.io import write
from gpaw import GPAW, PW, FermiDirac

fukui_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, fukui_dir)
from fukui_backend import read_cube

# GPAW calc defaults
ECUT = 300          # eV plane-wave cutoff
KPTS = (2, 2, 1)    # k-point grid
FD_WIDTH = 0.05     # Fermi-Dirac smearing width (eV)
VACUUM = 6.0        # vacuum above+below slab (Å)

# Metal properties: lattice constant (Å), valence electrons
METAL_PROPS = {
    'Ag': {'a': 4.086, 'valence': 47},
    'Au': {'a': 4.078, 'valence': 79},
    'Cu': {'a': 3.615, 'valence': 11},
}


def create_m111_adatom(metal):
    """Create M(111) 2x2 surface, 2 layers, one adatom."""
    a = METAL_PROPS[metal]['a']
    slab = fcc111(metal, size=(2, 2, 2), a=a, vacuum=VACUUM, periodic=True)
    add_adsorbate(slab, metal, height=1.8, position='fcc')
    return slab


def run_gpaw(slab, charge, spin, tag, outdir):
    """Run GPAW SCF and return calculator."""
    print(f"  GPAW: charge={charge}, spin={spin}, tag={tag}")
    calc = GPAW(
        mode=PW(ECUT),
        xc='PBE',
        charge=charge,
        spinpol=spin != 0,  # enable spin polarization if spin != 0
        occupations=FermiDirac(FD_WIDTH),
        kpts={'size': KPTS},
        txt=os.path.join(outdir, f'{tag}.txt'),
        convergence={'energy': 1e-5, 'density': 1e-5, 'bands': 'occupied'},
    )
    slab = slab.copy()
    slab.calc = calc
    energy = slab.get_potential_energy()
    print(f"    Energy = {energy:.6f} eV")
    return slab, calc


def write_density_cube(atoms, calc, fname):
    """Write all-electron density cube via ASE."""
    rho = calc.get_all_electron_density()
    write(fname, atoms, data=rho)
    print(f"    Cube: {fname}")


def compute_fukui_gpaw(metal, outdir):
    """Run N, N+1, N-1 and write density cubes + Fukui grids."""
    os.makedirs(outdir, exist_ok=True)
    slab = create_m111_adatom(metal)
    valence = METAL_PROPS[metal]['valence']
    natoms = len(slab)
    nelectrons = natoms * valence

    print("=" * 60)
    print(f"{metal}(111) 2x2x2 + adatom  |  GPAW PBE  |  Fukui functions")
    print("=" * 60)
    print(f"  Atoms: {natoms}")
    print(f"  Valence e- per atom: {valence}")
    print(f"  Total valence e-: {nelectrons}")
    print(f"  Cell:  {slab.cell.diagonal()}")
    print(f"  PBC:   {slab.pbc}")

    # Determine spin states based on electron count parity
    neutral_is_odd = (nelectrons % 2) == 1
    spin_N = 1 if neutral_is_odd else 0
    spin_A = 0 if neutral_is_odd else 1
    spin_C = 1 if neutral_is_odd else 0

    print(f"  Spin states: N={spin_N}, A={spin_A}, C={spin_C}")

    print("\n  Neutral (N)   ...")
    slab_N, calc_N = run_gpaw(slab, charge=0, spin=spin_N, tag='N', outdir=outdir)
    write_density_cube(slab_N, calc_N, os.path.join(outdir, 'rho_N.cube'))

    print("\n  Anion (N+1)   ...")
    slab_A, calc_A = run_gpaw(slab, charge=-1, spin=spin_A, tag='A', outdir=outdir)
    write_density_cube(slab_A, calc_A, os.path.join(outdir, 'rho_A.cube'))

    print("\n  Cation (N-1)  ...")
    slab_C, calc_C = run_gpaw(slab, charge=1, spin=spin_C, tag='C', outdir=outdir)
    write_density_cube(slab_C, calc_C, os.path.join(outdir, 'rho_C.cube'))

    print("\n  Computing Fukui grids ...")
    rho_N, origin, shape, vecs, atoms = read_cube(os.path.join(outdir, 'rho_N.cube'))
    rho_A, _, _, _, _ = read_cube(os.path.join(outdir, 'rho_A.cube'))
    rho_C, _, _, _, _ = read_cube(os.path.join(outdir, 'rho_C.cube'))

    f_plus = rho_A - rho_N
    f_minus = rho_N - rho_C
    f_zero = 0.5 * (f_plus + f_minus)

    for tag, grid in [('f_plus', f_plus), ('f_minus', f_minus), ('f_zero', f_zero)]:
        np.save(os.path.join(outdir, f'{tag}.npy'), grid)
        # Write cube file for VESTA
        from fukui_backend import write_cube
        write_cube(os.path.join(outdir, f'{tag}.cube'), grid, origin, vecs, atoms,
                   comment1=f'{metal}(111) adatom Fukui {tag}', comment2='GPAW PBE')
        print(f"    {tag}: range [{grid.min():.3e}, {grid.max():.3e}] (npy + cube)")

    # Integrated totals
    dx, dy, dz = vecs[0][0], vecs[1][1], vecs[2][2]
    dV = abs(dx * dy * dz)
    print(f"\n  Integrated f+: {np.sum(f_plus)*dV:.4f} e")
    print(f"  Integrated f-: {np.sum(f_minus)*dV:.4f} e")
    print(f"  Integrated f0: {np.sum(f_zero)*dV:.4f} e")

    print("\n" + "=" * 60)
    print(f"Results: {outdir}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description='Compute Fukui functions for M(111)+adatom with GPAW')
    parser.add_argument('--metal', type=str, default='Ag', choices=['Ag', 'Au', 'Cu'],
                        help='Metal element (default: Ag)')
    args = parser.parse_args()

    metal = args.metal
    outdir = os.path.join(fukui_dir, 'results_metal', f'{metal}111_2x2x2_adatom_GPAW_PBE')
    compute_fukui_gpaw(metal, outdir)


if __name__ == '__main__':
    main()
