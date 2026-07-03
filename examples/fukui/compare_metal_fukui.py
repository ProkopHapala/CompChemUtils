#!/usr/bin/env python3
"""Compare Fukui function magnitudes across Ag, Au, Cu(111)+adatom surfaces.

Usage:
    venvML && python compare_metal_fukui.py
"""

import os
import sys
import numpy as np

fukui_dir = os.path.dirname(os.path.abspath(__file__))
METALS = ['Ag', 'Au', 'Cu']


def load_fukui_data(metal):
    """Load Fukui grids and compute statistics."""
    resdir = os.path.join(fukui_dir, 'results_metal', f'{metal}111_2x2x2_adatom_GPAW_PBE')
    
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
    print("=" * 80)
    print("Fukui Function Comparison: Ag, Au, Cu(111) + adatom")
    print("=" * 80)
    
    # Collect data
    data = {}
    for metal in METALS:
        f_plus, f_minus, f_zero = load_fukui_data(metal)
        data[metal] = {
            'f_plus': compute_stats(f_plus),
            'f_minus': compute_stats(f_minus),
            'f_zero': compute_stats(f_zero),
        }
    
    # Print comparison table
    print("\n" + "=" * 80)
    print("Maximum absolute Fukui values (|f|_max)")
    print("=" * 80)
    print(f"{'Metal':<8} {'f+':<12} {'f-':<12} {'f0':<12}")
    print("-" * 80)
    for metal in METALS:
        fp = data[metal]['f_plus']['abs_max']
        fm = data[metal]['f_minus']['abs_max']
        fz = data[metal]['f_zero']['abs_max']
        print(f"{metal:<8} {fp:.4e}  {fm:.4e}  {fz:.4e}")
    
    print("\n" + "=" * 80)
    print("Mean Fukui values (average over grid)")
    print("=" * 80)
    print(f"{'Metal':<8} {'f+':<12} {'f-':<12} {'f0':<12}")
    print("-" * 80)
    for metal in METALS:
        fp = data[metal]['f_plus']['mean']
        fm = data[metal]['f_minus']['mean']
        fz = data[metal]['f_zero']['mean']
        print(f"{metal:<8} {fp:.4e}  {fm:.4e}  {fz:.4e}")
    
    print("\n" + "=" * 80)
    print("Standard deviation (spatial variation)")
    print("=" * 80)
    print(f"{'Metal':<8} {'f+':<12} {'f-':<12} {'f0':<12}")
    print("-" * 80)
    for metal in METALS:
        fp = data[metal]['f_plus']['std']
        fm = data[metal]['f_minus']['std']
        fz = data[metal]['f_zero']['std']
        print(f"{metal:<8} {fp:.4e}  {fm:.4e}  {fz:.4e}")
    
    print("\n" + "=" * 80)
    print("Summary: Relative reactivity strength (by |f|_max)")
    print("=" * 80)
    for ftype in ['f_plus', 'f_minus', 'f_zero']:
        print(f"\n{ftype}:")
        sorted_metals = sorted(METALS, key=lambda m: data[m][ftype]['abs_max'], reverse=True)
        for i, metal in enumerate(sorted_metals):
            val = data[metal][ftype]['abs_max']
            print(f"  {i+1}. {metal}: {val:.4e}")
    
    print("\n" + "=" * 80)


if __name__ == '__main__':
    main()
