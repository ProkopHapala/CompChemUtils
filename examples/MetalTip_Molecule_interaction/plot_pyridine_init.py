#!/usr/bin/env python3
"""Plot initial molecule-on-surface geometries (single frame) for visual inspection.
Reads CONTCAR from systems/<Metal>/<variant>_<molecule>_111_3x3x3/input/CONTCAR.
Uses plotUtils to show side + top view.
"""
import os, sys, glob
import numpy as np
import matplotlib
matplotlib.use('Agg')

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)
from py.plotUtils import plot_init_final_comparison

BASE = os.path.dirname(os.path.abspath(__file__))
SYSTEMS = os.path.join(BASE, 'systems')
PLOT_OUT = os.path.join(BASE, 'init_plots_pyridine')
os.makedirs(PLOT_OUT, exist_ok=True)

def read_contcar(path):
    with open(path) as f:
        lines = f.readlines()
    scale = float(lines[1].strip())
    cell = np.array([[float(x) for x in lines[2+i].split()] for i in range(3)]) * scale
    n_types = [int(x) for x in lines[6].split()]
    symbols = []
    for sym, n in zip(lines[5].split(), n_types):
        symbols.extend([sym] * n)
    n_atoms = sum(n_types)
    ps = np.array([[float(x) for x in lines[8+i].split()[:3]] for i in range(n_atoms)]) * scale
    return symbols, ps, cell

def main():
    targets = sorted(glob.glob(os.path.join(SYSTEMS, '*', '*pyridine_111_3x3x3', 'input', 'CONTCAR')))
    targets += sorted(glob.glob(os.path.join(SYSTEMS, '*', '*furan_111_3x3x3', 'input', 'CONTCAR')))
    targets += sorted(glob.glob(os.path.join(SYSTEMS, '*', '*thiophene_111_3x3x3', 'input', 'CONTCAR')))
    targets += sorted(glob.glob(os.path.join(SYSTEMS, '*', '*pyrrol_111_3x3x3', 'input', 'CONTCAR')))
    print(f"Found {len(targets)} geometries")
    for contcar in targets:
        parts = contcar.split(os.sep)
        metal = parts[-4]
        dirname = parts[-3]  # e.g. adatom_pyridine_111_3x3x3
        # Strip _111_3x3x3 suffix
        base = dirname.replace('_111_3x3x3', '')
        name = f"{metal}_{base}"
        syms, ps, cell = read_contcar(contcar)
        outpath = os.path.join(PLOT_OUT, f'{name}.png')
        plot_init_final_comparison(syms, ps, ps.copy(), name=name, n_frozen=18, fname=outpath)
        print(f"  {name}.png  ({len(syms)} atoms)")
    print(f"\nDone. Plots in {PLOT_OUT}/")

if __name__ == '__main__':
    main()
