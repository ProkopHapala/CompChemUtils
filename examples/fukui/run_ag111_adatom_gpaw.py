#!/usr/bin/env python3
"""Compute Fukui functions for Ag(111) surface with adatom using GPAW (periodic DFT).

Uses GPAW with periodic boundary conditions in x,y and vacuum in z.
"""

import os
import sys
import numpy as np
from ase import Atoms
from ase.build import fcc111, add_adsorbate
from gpaw import GPAW, PW, FermiDirac
from gpaw import setup_paths

fukui_dir = os.path.dirname(os.path.abspath(__file__))


def create_ag111_adatom():
    """Create Ag(111) 2x2x2 surface with one adatom.
    
    Returns
    -------
    slab : ase.Atoms
        Ag(111) surface with adatom, periodic in x,y.
    """
    # Create Ag(111) surface: 2x2 unit cells, 2 layers
    # a=4.086 Å for Ag
    slab = fcc111('Ag', size=(2, 2, 2), a=4.086, vacuum=10.0, periodic=True)
    
    # Add adatom on top of the surface
    add_adsorbate(slab, 'Ag', height=2.0, position=(0.5, 0.5))
    
    # Center in z-direction
    slab.center(vacuum=10.0, axis=2)
    
    return slab


def run_gpaw_calc(slab, charge, spin, tag, outdir):
    """Run GPAW calculation for given charge and spin.
    
    Parameters
    ----------
    slab : ase.Atoms
        Surface structure.
    charge : int
        Total charge.
    spin : float
        Total spin (2*S = Nalpha - Nbeta).
    tag : str
        Identifier for output files.
    outdir : str
        Output directory.
    
    Returns
    -------
    calc : GPAW
        GPAW calculator object.
    """
    print(f"  Running GPAW calculation: charge={charge}, spin={spin}")
    
    # Use plane-wave mode with appropriate cutoff
    # For Ag, 400 eV is reasonable
    calc = GPAW(
        mode=PW(400),
        xc='PBE',
        charge=charge,
        occupations=FermiDirac(0.1),
        kpts={'size': (4, 4, 1)},  # k-point sampling for surface
        txt=os.path.join(outdir, f'{tag}.txt'),
        convergence={'energy': 1e-5, 'density': 1e-5},
    )
    
    slab.calc = calc
    energy = slab.get_potential_energy()
    print(f"    Energy = {energy:.6f} eV")
    
    return calc


def write_density_cube_gpaw(slab, calc, fname):
    """Write electron density cube file from GPAW calculation.
    
    Parameters
    ----------
    slab : ase.Atoms
        Structure.
    calc : GPAW
        GPAW calculator with converged density.
    fname : str
        Output cube file path.
    """
    from gpaw.utilities.dos import ElectronDensity
    density = ElectronDensity(calc)
    density.write_cube(fname, slab)


def compute_fukui_gpaw(slab, outdir):
    """Compute Fukui functions using GPAW with periodic BCs.
    
    Parameters
    ----------
    slab : ase.Atoms
        Surface structure.
    outdir : str
        Output directory.
    """
    os.makedirs(outdir, exist_ok=True)
    
    print("="*60)
    print("GPAW Fukui function calculation with periodic BCs")
    print("="*60)
    print(f"  Number of atoms: {len(slab)}")
    print(f"  Cell: {slab.get_cell()}")
    print(f"  Periodic: {slab.pbc}")
    
    # Run calculations for N, N+1, N-1
    # For 9 Ag atoms: 9*47 = 423 electrons (odd)
    # Neutral: spin=1 (doublet)
    # Anion: spin=2 (triplet) 
    # Cation: spin=0 (singlet)
    
    print("\n  Neutral (N)...")
    calc_N = run_gpaw_calc(slab.copy(), charge=0, spin=1, 
                          tag='gpaw_N', outdir=outdir)
    write_density_cube_gpaw(slab, calc_N, os.path.join(outdir, 'rho_N_gpaw.cube'))
    
    print("\n  Anion (N+1)...")
    calc_A = run_gpaw_calc(slab.copy(), charge=-1, spin=2,
                          tag='gpaw_A', outdir=outdir)
    write_density_cube_gpaw(slab, calc_A, os.path.join(outdir, 'rho_A_gpaw.cube'))
    
    print("\n  Cation (N-1)...")
    calc_C = run_gpaw_calc(slab.copy(), charge=1, spin=0,
                          tag='gpaw_C', outdir=outdir)
    write_density_cube_gpaw(slab, calc_C, os.path.join(outdir, 'rho_C_gpaw.cube'))
    
    print("\n" + "="*60)
    print(f"Results saved to: {outdir}")
    print("="*60)


def main():
    print("="*60)
    print("Creating Ag(111) 2x2x2 surface with adatom")
    print("="*60)
    
    slab = create_ag111_adatom()
    print(f"\nSurface structure:")
    print(f"  Number of atoms: {len(slab)}")
    print(f"  Periodic: {slab.pbc}")
    print(f"  Cell vectors (Å):")
    for i, vec in enumerate(slab.get_cell()):
        print(f"    {i}: {vec}")
    
    outdir = os.path.join(fukui_dir, 'results', 'Ag111_2x2x2_adatom_GPAW_PBE')
    
    compute_fukui_gpaw(slab, outdir)


if __name__ == '__main__':
    main()
