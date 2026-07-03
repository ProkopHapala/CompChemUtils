#!/usr/bin/env python3
"""Compare Ag4 cluster Fukui functions between def2-SVP and LANL2DZ basis sets.

Reads Mulliken condensed Fukui indices and 3D density cubes from two
PySCF PBE calculations (results_Ag/Ag4_pbe_def2svp and Ag4_pbe_lanl2dz),
prints side-by-side comparison tables (f+, f-, f0), and computes
integrated grid statistics to assess basis set sensitivity.

Usage:
    python compare_ag4_basis.py
"""

import os
import sys
import numpy as np

fukui_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, fukui_dir)
from fukui_backend import read_cube

RESULTS_DIR = os.path.join(fukui_dir, 'results_Ag')


def read_mulliken(path):
    """Read mulliken_fukui.txt and return (labels, f_plus, f_minus, f0)."""
    labels, fp, fm, f0 = [], [], [], []
    with open(path) as f:
        next(f)  # skip header
        for line in f:
            parts = line.split()
            if len(parts) >= 4:
                labels.append(parts[0])
                fp.append(float(parts[1]))
                fm.append(float(parts[2]))
                f0.append(float(parts[3]))
    return labels, np.array(fp), np.array(fm), np.array(f0)


def compare():
    print("=" * 70)
    print("Ag4 Fukui Comparison: PBE/def2-svp  vs  PBE/lanl2dz")
    print("=" * 70)

    # --- Mulliken condensed indices ---
    labels_s, fp_s, fm_s, f0_s = read_mulliken(
        os.path.join(RESULTS_DIR, 'Ag4_pbe_def2svp', 'mulliken_fukui.txt'))
    labels_l, fp_l, fm_l, f0_l = read_mulliken(
        os.path.join(RESULTS_DIR, 'Ag4_pbe_lanl2dz', 'mulliken_fukui.txt'))

    print("\n--- Condensed Mulliken Fukui Indices ---")
    print(f"{'Atom':>4}  {'f+_SVP':>10}  {'f+_DZ':>10}  {'diff':>10} | "
          f"{'f-_SVP':>10}  {'f-_DZ':>10}  {'diff':>10} | "
          f"{'f0_SVP':>10}  {'f0_DZ':>10}  {'diff':>10}")
    print("-" * 110)
    for i in range(len(labels_s)):
        print(f"{labels_s[i]:>4}  {fp_s[i]:10.6f}  {fp_l[i]:10.6f}  {fp_s[i]-fp_l[i]:10.6f} | "
              f"{fm_s[i]:10.6f}  {fm_l[i]:10.6f}  {fm_s[i]-fm_l[i]:10.6f} | "
              f"{f0_s[i]:10.6f}  {f0_l[i]:10.6f}  {f0_s[i]-f0_l[i]:10.6f}")

    print(f"\n{'Stats':>4}  {'std_SVP':>10}  {'std_DZ':>10}  {'':>10} | "
          f"{'std_SVP':>10}  {'std_DZ':>10}  {'':>10} | "
          f"{'std_SVP':>10}  {'std_DZ':>10}")
    print("-" * 110)
    print(f"{'':>4}  {np.std(fp_s):10.6f}  {np.std(fp_l):10.6f}  {'':>10} | "
          f"{np.std(fm_s):10.6f}  {np.std(fm_l):10.6f}  {'':>10} | "
          f"{np.std(f0_s):10.6f}  {np.std(f0_l):10.6f}")

    # --- Cube grid statistics ---
    print("\n--- 3D Grid Statistics ---")
    for tag in ['def2svp', 'lanl2dz']:
        resdir = os.path.join(RESULTS_DIR, f'Ag4_pbe_{tag}')
        rho_N, origin, shape, vecs, atoms = read_cube(os.path.join(resdir, 'rho_N.cube'))
        rho_A, _, _, _, _ = read_cube(os.path.join(resdir, 'rho_A.cube'))
        rho_C, _, _, _, _ = read_cube(os.path.join(resdir, 'rho_C.cube'))
        f_plus = rho_A - rho_N
        f_minus = rho_N - rho_C
        f_zero = 0.5 * (f_plus + f_minus)
        dV = abs(vecs[0][0] * vecs[1][1] * vecs[2][2])

        print(f"\n{tag}:")
        print(f"  Grid shape: {shape}")
        print(f"  Integrated N:  {np.sum(rho_N)*dV:.4f} e")
        print(f"  Integrated A:  {np.sum(rho_A)*dV:.4f} e")
        print(f"  Integrated C:  {np.sum(rho_C)*dV:.4f} e")
        print(f"  f+ range: [{f_plus.min():.3e}, {f_plus.max():.3e}]")
        print(f"  f- range: [{f_minus.min():.3e}, {f_minus.max():.3e}]")
        print(f"  f0 range: [{f_zero.min():.3e}, {f_zero.max():.3e}]")

    print("\n" + "=" * 70)


if __name__ == '__main__':
    compare()
