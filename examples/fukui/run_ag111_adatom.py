#!/usr/bin/env python3
"""Generate Ag(111) 3x3x2 surface with adatom and compute FUKUI functions.

Uses ASE to create Ag(111) surface slab with adatom.
"""

import os
import sys
import argparse
import numpy as np
from ase import Atoms
from ase.build import fcc111, add_adsorbate

fukui_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, fukui_dir)
from fukui_backend import run_fukui_for_molecule


def ase_to_pyscf_geom(ase_atoms):
    """Convert ASE Atoms object to pySCF geometry string.
    
    Parameters
    ----------
    ase_atoms : ase.Atoms
        ASE Atoms object with positions in Angstrom.
    
    Returns
    -------
    geom_str : str
        pySCF geometry string (e.g. 'Ag 0 0 0; Ag 1 1 1').
    """
    symbols = ase_atoms.get_chemical_symbols()
    positions = ase_atoms.get_positions()
    geom_parts = []
    for sym, pos in zip(symbols, positions):
        geom_parts.append(f'{sym} {pos[0]:.6f} {pos[1]:.6f} {pos[2]:.6f}')
    return '; '.join(geom_parts)


def create_ag111_adatom(size=(2, 2, 2)):
    """Create Ag(111) surface with one adatom.
    
    Parameters
    ----------
    size : tuple of int
        Surface size (nx, ny, nz). Default (2, 2, 2).
    
    Returns
    -------
    ase_atoms : ase.Atoms
        Ag(111) surface with adatom.
    """
    # Create Ag(111) surface: nx x ny unit cells, nz layers
    # a=4.086 Å for Ag
    slab = fcc111('Ag', size=size, a=4.086, vacuum=10.0)
    
    # Add adatom on top of the surface at the fcc hollow site
    # (centered over the triangle formed by 3 top-layer surface atoms)
    # height=2.0 Å above surface
    add_adsorbate(slab, 'Ag', height=2.0, position='fcc')
    
    # Center the cluster in the unit cell
    slab.center(vacuum=10.0, axis=2)
    
    return slab

'''

# HOW TO USE

python run_ag111_adatom.py --generate-only --size 3 3 2
ase gui structures/Ag111_3x3x2_adatom.xyz -r 2,2,1 -b

'''


def main():
    parser = argparse.ArgumentParser(description='Generate Ag(111) surface with adatom and optionally compute FUKUI functions')
    parser.add_argument('--generate-only', action='store_true', help='Only generate structure files, skip FUKUI calculation')
    parser.add_argument('--size', type=int, nargs=3, default=[2, 2, 2], metavar=('NX', 'NY', 'NZ'), help='Surface size (default: 2 2 2)')
    args = parser.parse_args()

    size_tuple = tuple(args.size)
    print("="*60)
    print(f"Creating Ag(111) {size_tuple[0]}x{size_tuple[1]}x{size_tuple[2]} surface with adatom")
    print("="*60)
    
    # Create surface with adatom
    slab = create_ag111_adatom(size=size_tuple)
    print(f"\nSurface structure:")
    print(f"  Number of atoms: {len(slab)}")
    print(f"  Layers: {size_tuple[2]}")
    print(f"  Surface area: {size_tuple[0]}x{size_tuple[1]} unit cells")
    print(f"  Adatom: 1")
    print(f"\n  Positions (Angstrom):")
    for i, (sym, pos) in enumerate(zip(slab.get_chemical_symbols(), slab.get_positions())):
        print(f"    {sym}{i+1}: {pos[0]:10.6f} {pos[1]:10.6f} {pos[2]:10.6f}")
    
    # Identify which atom is the adatom (highest z coordinate)
    z_coords = slab.get_positions()[:, 2]
    adatom_idx = np.argmax(z_coords)
    print(f"\n  Adatom is atom index {adatom_idx} (highest z = {z_coords[adatom_idx]:.3f} Å)")
    
    # Save structure files for VESTA
    struct_dir = os.path.join(fukui_dir, 'structures')
    os.makedirs(struct_dir, exist_ok=True)
    
    # Generate filename based on size
    size_str = f"{size_tuple[0]}x{size_tuple[1]}x{size_tuple[2]}"
    
    # Save as POSCAR (VASP format) - VESTA can read this
    poscar_file = os.path.join(struct_dir, f'Ag111_{size_str}_adatom_POSCAR')
    slab.write(poscar_file, format='vasp')
    print(f"\n  Saved POSCAR: {poscar_file}")
    
    # Save as XYZ with cell information
    xyz_file = os.path.join(struct_dir, f'Ag111_{size_str}_adatom.xyz')
    slab.write(xyz_file, format='extxyz')
    print(f"  Saved XYZ: {xyz_file}")
    
    # Save as CIF (also VESTA compatible)
    cif_file = os.path.join(struct_dir, f'Ag111_{size_str}_adatom.cif')
    slab.write(cif_file, format='cif')
    print(f"  Saved CIF: {cif_file}")
    
    # Convert to pySCF format
    geom_str = ase_to_pyscf_geom(slab)
    
    # Skip FUKUI calculation if --generate-only flag is set
    if args.generate_only:
        print("\n" + "="*60)
        print("Structure generation complete (skipping FUKUI calculation)")
        print("="*60)
        return
    
    # Run FUKUI calculation
    print("\n" + "="*60)
    print("Running FUKUI function calculation")
    print(f"WARNING: {len(slab)} Ag atoms with DZVP basis + ECP")
    print("="*60)
    
    outdir = os.path.join(fukui_dir, 'results')
    tag = f'Ag111_{size_str}_adatom_DZVP_b3lyp'
    
    # Use DZVP basis set with ECP for Ag
    # Note: 9 Ag atoms = 423 electrons (odd), so need spin=1 for neutral
    # ECP 'def2-SVP' replaces core electrons for Ag
    resdir = run_fukui_for_molecule(
        tag, geom_str, outdir,
        basis='DZVP', xc_func='b3lyp',
        resolution=0.15, margin=4.0,
        spin_N=1, spin_A=2, spin_C=0,
        ecp='def2-SVP'
    )
    
    print("\n" + "="*60)
    print(f"Results saved to: {resdir}")
    print("="*60)


if __name__ == '__main__':
    main()
