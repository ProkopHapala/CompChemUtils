#!/usr/bin/env python3
"""Compute Fukui function grids from cube files.

Subtracts electron density cube files to obtain:
  f+ = ρ(N+1) - ρ(N)  (electrophilic Fukui function)
  f- = ρ(N) - ρ(N-1)  (nucleophilic Fukui function)
  f0 = 0.5 * (f+ + f-) (average)
"""

import os
import sys
import numpy as np

fukui_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, fukui_dir)
from fukui_backend import read_cube, write_cube


def compute_fukui_grids(resdir):
    """Compute Fukui function grids from cube files in results directory.
    
    Parameters
    ----------
    resdir : str
        Path to results directory containing rho_N.cube, rho_A.cube, rho_C.cube
    """
    cube_N = os.path.join(resdir, 'rho_N.cube')
    cube_A = os.path.join(resdir, 'rho_A.cube')
    cube_C = os.path.join(resdir, 'rho_C.cube')
    
    if not all(os.path.exists(f) for f in [cube_N, cube_A, cube_C]):
        raise FileNotFoundError(f"Cube files not found in {resdir}")
    
    print(f"Reading cube files from {resdir}...")
    rho_N, origin, shape, vecs, atoms = read_cube(cube_N)
    rho_A, _, _, _, _ = read_cube(cube_A)
    rho_C, _, _, _, _ = read_cube(cube_C)
    
    print(f"  Grid shape: {shape}")
    print(f"  Number of atoms: {len(atoms)}")
    
    # Compute Fukui functions
    print("Computing Fukui functions...")
    f_plus = rho_A - rho_N
    f_minus = rho_N - rho_C
    f_zero = 0.5 * (f_plus + f_minus)
    
    print(f"  f+ range: [{f_plus.min():.3e}, {f_plus.max():.3e}]")
    print(f"  f- range: [{f_minus.min():.3e}, {f_minus.max():.3e}]")
    print(f"  f0 range: [{f_zero.min():.3e}, {f_zero.max():.3e}]")
    
    # Write Fukui function cube files
    print("Writing Fukui function cube files...")
    write_cube(
        os.path.join(resdir, 'fukui_f_plus.cube'),
        f_plus, origin, vecs, atoms,
        comment1='Fukui f+ (electrophilic)',
        comment2='f+ = rho(N+1) - rho(N)'
    )
    print(f"  Saved: fukui_f_plus.cube")
    
    write_cube(
        os.path.join(resdir, 'fukui_f_minus.cube'),
        f_minus, origin, vecs, atoms,
        comment1='Fukui f- (nucleophilic)',
        comment2='f- = rho(N) - rho(N-1)'
    )
    print(f"  Saved: fukui_f_minus.cube")
    
    write_cube(
        os.path.join(resdir, 'fukui_f_zero.cube'),
        f_zero, origin, vecs, atoms,
        comment1='Fukui f0 (average)',
        comment2='f0 = 0.5 * (f+ + f-)'
    )
    print(f"  Saved: fukui_f_zero.cube")
    
    # Also save as .npy for easier Python access
    np.save(os.path.join(resdir, 'fukui_f_plus.npy'), f_plus)
    np.save(os.path.join(resdir, 'fukui_f_minus.npy'), f_minus)
    np.save(os.path.join(resdir, 'fukui_f_zero.npy'), f_zero)
    print(f"  Saved NumPy arrays: fukui_f_*.npy")
    
    print(f"\nFukui function grids saved to {resdir}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Compute Fukui function grids from cube files.')
    parser.add_argument('resdir', help='Results directory containing rho_N.cube, rho_A.cube, rho_C.cube')
    args = parser.parse_args()
    
    compute_fukui_grids(args.resdir)


if __name__ == '__main__':
    main()
