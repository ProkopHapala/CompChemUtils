#!/usr/bin/env python3
"""Generate Ag4 tetrahedron cluster from bulk structure and compute FUKUI functions.

Uses ASE to create tetrahedral cluster from bulk Ag crystal structure.
"""

import os
import sys
import numpy as np
from ase import Atoms
from ase.build import bulk
from ase.cluster import Octahedron

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


def create_ag_tetrahedron():
    """Create Ag4 tetrahedron cluster from bulk structure.
    
    Returns
    -------
    ase_atoms : ase.Atoms
        Tetrahedral Ag4 cluster.
    """
    # Get bulk Ag structure (FCC)
    bulk_ag = bulk('Ag', 'fcc', a=4.086)  # Ag lattice constant in Angstrom
    
    # Extract positions for tetrahedron
    # In FCC, a tetrahedron can be formed by:
    # - One corner atom
    # - Three face-centered atoms adjacent to that corner
    positions = np.array([
        [0.0, 0.0, 0.0],           # Corner
        [0.5, 0.5, 0.0],           # Face center
        [0.5, 0.0, 0.5],           # Face center
        [0.0, 0.5, 0.5],           # Face center
    ]) * 4.086  # Scale by lattice constant
    
    # Center the cluster
    centroid = np.mean(positions, axis=0)
    positions -= centroid
    
    tetrahedron = Atoms('Ag4', positions=positions)
    return tetrahedron


def main():
    print("="*60)
    print("Creating Ag4 tetrahedron cluster from bulk structure")
    print("="*60)
    
    # Create tetrahedron
    ag4 = create_ag_tetrahedron()
    print(f"\nAg4 cluster:")
    print(f"  Number of atoms: {len(ag4)}")
    print(f"  Positions (Angstrom):")
    for i, (sym, pos) in enumerate(zip(ag4.get_chemical_symbols(), ag4.get_positions())):
        print(f"    Ag{i+1}: {pos[0]:10.6f} {pos[1]:10.6f} {pos[2]:10.6f}")
    
    # Check tetrahedron geometry
    pos = ag4.get_positions()
    distances = []
    for i in range(len(pos)):
        for j in range(i+1, len(pos)):
            d = np.linalg.norm(pos[i] - pos[j])
            distances.append(d)
    print(f"\n  Interatomic distances (Angstrom): {np.array(distances)}")
    
    # Convert to pySCF format
    geom_str = ase_to_pyscf_geom(ag4)
    print(f"\n  pySCF geometry string:\n    {geom_str}")
    
    # Run FUKUI calculation
    print("\n" + "="*60)
    print("Running FUKUI function calculation")
    print("="*60)
    
    outdir = os.path.join(fukui_dir, 'results')
    tag = 'Ag4_tetrahedron_DZVP_b3lyp'
    
    # Use DZVP (double zeta valence polarized) basis set
    resdir = run_fukui_for_molecule(
        tag, geom_str, outdir,
        basis='DZVP', xc_func='b3lyp',
        resolution=0.15, margin=4.0
    )
    
    print("\n" + "="*60)
    print(f"Results saved to: {resdir}")
    print("="*60)


if __name__ == '__main__':
    main()
