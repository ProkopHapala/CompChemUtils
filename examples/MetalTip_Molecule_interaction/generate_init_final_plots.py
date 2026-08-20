#!/usr/bin/env python3
"""Generate init+final multi-frame XYZ files and comparison plots for all molecule-on-surface jobs.
Reads initial geometry from systems/<Metal>/<variant>_<molecule>_111_3x3x3/input/CONTCAR
and final geometry from jobs_mol_on_surf/results_*/relaxed.xyz.
Writes 2-frame XYZ to init_final_xyz/ and plots to init_final_plots/ using plotUtils.plot_init_final_comparison().
"""
import os, sys, glob, re
import numpy as np
import matplotlib
matplotlib.use('Agg')

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)
from py.plotUtils import plot_init_final_comparison

BASE = os.path.dirname(os.path.abspath(__file__))
SYSTEMS = os.path.join(BASE, 'systems')
JOBS = os.path.join(BASE, 'jobs_mol_on_surf')
XYZ_OUT = os.path.join(BASE, 'init_final_xyz')
PLOT_OUT = os.path.join(BASE, 'init_final_plots')
os.makedirs(XYZ_OUT, exist_ok=True)
os.makedirs(PLOT_OUT, exist_ok=True)

def read_contcar(path):
    with open(path) as f:
        lines = f.readlines()
    scale = float(lines[1].strip())
    cell = np.array([[float(x) for x in lines[2+i].split()] for i in range(3)]) * scale
    n_types = [int(x) for x in lines[6].split()]
    symbols = []
    for i, (sym, n) in enumerate(zip(lines[5].split(), n_types)):
        symbols.extend([sym] * n)
    n_atoms = sum(n_types)
    ps = np.array([[float(x) for x in lines[8+i].split()[:3]] for i in range(n_atoms)]) * scale
    return symbols, ps, cell

def read_xyz(path):
    with open(path) as f:
        lines = f.readlines()
    n = int(lines[0].strip())
    syms = []; ps = []
    for i in range(n):
        parts = lines[2+i].split()
        syms.append(parts[0]); ps.append([float(parts[1]), float(parts[2]), float(parts[3])])
    return syms, np.array(ps)

def write_two_frame_xyz(path, syms, ps_init, ps_final):
    with open(path, 'w') as f:
        for ps in [ps_init, ps_final]:
            f.write(f"{len(syms)}\n\n")
            for s, p in zip(syms, ps):
                f.write(f"{s:2s}  {p[0]:.6f}  {p[1]:.6f}  {p[2]:.6f}\n")

def main():
    results_dirs = sorted(glob.glob(os.path.join(JOBS, 'results_*_111_3x3x3')))
    n_done = 0; n_skip = 0
    for rd in results_dirs:
        name = os.path.basename(rd).replace('results_', '').replace('_111_3x3x3', '')
        relaxed = os.path.join(rd, 'relaxed.xyz')
        if not os.path.exists(relaxed):
            print(f"  SKIP {name}: no relaxed.xyz"); n_skip += 1; continue
        # Parse name: Metal_variant_molecule  e.g. Cu_bare_H2O, Cu_adatom_HCN
        parts = name.split('_')
        metal = parts[0]; variant = parts[1]; molecule = parts[2]
        # Find initial CONTCAR
        contcar = os.path.join(SYSTEMS, metal, f'{variant}_{molecule}_111_3x3x3', 'input', 'CONTCAR')
        if not os.path.exists(contcar):
            print(f"  SKIP {name}: no initial CONTCAR at {contcar}"); n_skip += 1; continue
        syms_init, ps_init, cell = read_contcar(contcar)
        syms_final, ps_final = read_xyz(relaxed)
        if syms_init != syms_final:
            print(f"  WARN {name}: symbol mismatch init={syms_init} vs final={syms_final}")
        # Write 2-frame XYZ
        xyz_path = os.path.join(XYZ_OUT, f'{name}.xyz')
        write_two_frame_xyz(xyz_path, syms_init, ps_init, ps_final)
        # Plot
        plot_path = os.path.join(PLOT_OUT, f'{name}.png')
        plot_init_final_comparison(syms_init, ps_init, ps_final, name=name, n_frozen=18, fname=plot_path)
        print(f"  {name}.png  (init→final, {len(syms_init)} atoms)")
        n_done += 1
    print(f"\nDone: {n_done} plotted, {n_skip} skipped")
    print(f"  XYZ:  {XYZ_OUT}/")
    print(f"  Plots: {PLOT_OUT}/")

if __name__ == '__main__':
    main()
