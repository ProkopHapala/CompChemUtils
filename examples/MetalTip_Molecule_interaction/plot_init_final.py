#!/usr/bin/env python3
"""Thin wrapper: plot initial (red) vs final (blue) geometry for all init_final_xyz/*.xyz.
Uses plot_init_final_comparison() from py/plotUtils.py.
Usage: python3 plot_init_final.py [file1.xyz ...]  (default: all in init_final_xyz/)
"""
import sys, os, glob
import numpy as np
import matplotlib
matplotlib.use('Agg')

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)
from py.plotUtils import plot_init_final_comparison

def read_xyz_frames(path):
    """Read multi-frame XYZ, return list of (symbols, positions)."""
    with open(path) as f:
        lines = f.readlines()
    frames = []
    i = 0
    while i < len(lines):
        n = int(lines[i].strip())
        syms = []; ps = []
        for j in range(n):
            parts = lines[i + 2 + j].split()
            syms.append(parts[0]); ps.append([float(parts[1]), float(parts[2]), float(parts[3])])
        frames.append((syms, np.array(ps)))
        i += 2 + n
    return frames

def main():
    base = os.path.dirname(os.path.abspath(__file__))
    xyz_dir = os.path.join(base, 'init_final_xyz')
    out_dir = os.path.join(base, 'init_final_plots')
    os.makedirs(out_dir, exist_ok=True)
    files = sys.argv[1:] if len(sys.argv) > 1 else sorted(glob.glob(os.path.join(xyz_dir, '*.xyz')))
    print(f"Plotting {len(files)} files → {out_dir}/")
    for f in files:
        frames = read_xyz_frames(f)
        if len(frames) < 2:
            print(f"  SKIP {f}: need 2 frames"); continue
        syms, ps_init = frames[0]; _, ps_final = frames[1]
        name = os.path.basename(f).replace('.xyz', '')
        outpath = os.path.join(out_dir, name + '.png')
        plot_init_final_comparison(syms, ps_init, ps_final, name=name, n_frozen=18, fname=outpath)
        print(f"  {name}.png")
    print(f"Done. {len(files)} plots in {out_dir}/")

if __name__ == '__main__':
    main()
