#!/usr/bin/env python3
"""Compare Fukui functions: clusters (M4) vs surface+adatom (M111+adatom).

Usage:
    venvML && python compare_cluster_surface_fukui.py
"""

import os
import sys
import numpy as np

fukui_dir = os.path.dirname(os.path.abspath(__file__))
METALS = ['Ag', 'Au', 'Cu']

# Directory paths
CLUSTER_DIRS = {
    'Ag': os.path.join(fukui_dir, 'results_Ag', 'Ag4_pbe_def2svp'),
    'Au': os.path.join(fukui_dir, 'results_metal', 'Au4_pbe_def2svp'),
    'Cu': os.path.join(fukui_dir, 'results_metal', 'Cu4_pbe_def2svp'),
}

SURFACE_DIRS = {
    'Ag': os.path.join(fukui_dir, 'results_metal', 'Ag111_2x2x2_adatom_GPAW_PBE'),
    'Au': os.path.join(fukui_dir, 'results_metal', 'Au111_2x2x2_adatom_GPAW_PBE'),
    'Cu': os.path.join(fukui_dir, 'results_metal', 'Cu111_2x2x2_adatom_GPAW_PBE'),
}


def load_cluster_fukui(metal):
    """Load cluster Fukui grids (PySCF naming: fukui_f_plus.npy)."""
    resdir = CLUSTER_DIRS[metal]
    f_plus = np.load(os.path.join(resdir, 'fukui_f_plus.npy'))
    f_minus = np.load(os.path.join(resdir, 'fukui_f_minus.npy'))
    f_zero = np.load(os.path.join(resdir, 'fukui_f_zero.npy'))
    return f_plus, f_minus, f_zero


def load_surface_fukui(metal):
    """Load surface+adatom Fukui grids (GPAW naming: f_plus.npy)."""
    resdir = SURFACE_DIRS[metal]
    f_plus = np.load(os.path.join(resdir, 'f_plus.npy'))
    f_minus = np.load(os.path.join(resdir, 'f_minus.npy'))
    f_zero = np.load(os.path.join(resdir, 'f_zero.npy'))
    return f_plus, f_minus, f_zero


def compute_stats(grid):
    """Compute statistics for a Fukui grid."""
    return {
        'max': np.max(grid),
        'min': np.min(grid),
        'mean': np.mean(grid),
        'std': np.std(grid),
        'abs_max': np.max(np.abs(grid)),
    }


def main():
    print("=" * 90)
    print("Fukui Function Comparison: Clusters (M4) vs Surface+Adatom (M111+adatom)")
    print("=" * 90)
    
    # Load data
    cluster_data = {}
    surface_data = {}
    
    for metal in METALS:
        if os.path.isdir(CLUSTER_DIRS[metal]):
            cluster_data[metal] = {
                'f_plus': compute_stats(load_cluster_fukui(metal)[0]),
                'f_minus': compute_stats(load_cluster_fukui(metal)[1]),
                'f_zero': compute_stats(load_cluster_fukui(metal)[2]),
            }
        else:
            print(f"WARNING: Cluster data not found for {metal}: {CLUSTER_DIRS[metal]}")
        
        if os.path.isdir(SURFACE_DIRS[metal]):
            surface_data[metal] = {
                'f_plus': compute_stats(load_surface_fukui(metal)[0]),
                'f_minus': compute_stats(load_surface_fukui(metal)[1]),
                'f_zero': compute_stats(load_surface_fukui(metal)[2]),
            }
        else:
            print(f"WARNING: Surface data not found for {metal}: {SURFACE_DIRS[metal]}")
    
    # Comparison table: |f|_max
    print("\n" + "=" * 90)
    print("Maximum absolute Fukui values (|f|_max)")
    print("=" * 90)
    print(f"{'Metal':<8} {'Cluster f+':<15} {'Surface f+':<15} {'Ratio S/C':<12}")
    print("-" * 90)
    for metal in METALS:
        if metal in cluster_data and metal in surface_data:
            c_fp = cluster_data[metal]['f_plus']['abs_max']
            s_fp = surface_data[metal]['f_plus']['abs_max']
            ratio = s_fp / c_fp if c_fp > 0 else np.nan
            print(f"{metal:<8} {c_fp:.4e}  {s_fp:.4e}  {ratio:.2f}")
    
    print("\n" + "-" * 90)
    print(f"{'Metal':<8} {'Cluster f-':<15} {'Surface f-':<15} {'Ratio S/C':<12}")
    print("-" * 90)
    for metal in METALS:
        if metal in cluster_data and metal in surface_data:
            c_fm = cluster_data[metal]['f_minus']['abs_max']
            s_fm = surface_data[metal]['f_minus']['abs_max']
            ratio = s_fm / c_fm if c_fm > 0 else np.nan
            print(f"{metal:<8} {c_fm:.4e}  {s_fm:.4e}  {ratio:.2f}")
    
    print("\n" + "-" * 90)
    print(f"{'Metal':<8} {'Cluster f0':<15} {'Surface f0':<15} {'Ratio S/C':<12}")
    print("-" * 90)
    for metal in METALS:
        if metal in cluster_data and metal in surface_data:
            c_fz = cluster_data[metal]['f_zero']['abs_max']
            s_fz = surface_data[metal]['f_zero']['abs_max']
            ratio = s_fz / c_fz if c_fz > 0 else np.nan
            print(f"{metal:<8} {c_fz:.4e}  {s_fz:.4e}  {ratio:.2f}")
    
    # Summary: which environment has stronger Fukui response?
    print("\n" + "=" * 90)
    print("Summary: Surface+Adatom vs Cluster reactivity (by |f|_max ratio)")
    print("=" * 90)
    print("Ratio > 1: Surface+Adatom stronger")
    print("Ratio < 1: Cluster stronger")
    print()
    
    for ftype in ['f_plus', 'f_minus', 'f_zero']:
        print(f"\n{ftype}:")
        for metal in METALS:
            if metal in cluster_data and metal in surface_data:
                c_val = cluster_data[metal][ftype]['abs_max']
                s_val = surface_data[metal][ftype]['abs_max']
                ratio = s_val / c_val if c_val > 0 else np.nan
                stronger = "Surface" if ratio > 1 else "Cluster"
                print(f"  {metal}: {ratio:.2f}x ({stronger})")
    
    print("\n" + "=" * 90)


if __name__ == '__main__':
    main()
