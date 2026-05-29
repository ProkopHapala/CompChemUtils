#!/usr/bin/env python3
"""Run Fukui batch for all small molecules with DZVP basis, with 1D + 2D plots."""

import os, sys
fukui_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, fukui_dir)
from fukui_backend import run_fukui_for_molecule, read_xyz
from run_fukui import plot_2d_slices, plot_1d_cuts

XYZ_DIR = '/home/prokop/git/CompChemUtils/data/xyz'

MOLS = ['H2O', 'HCN', 'HCl', 'CH2O', 'CO', 'NH3', 'HCOOH']

outdir = os.path.join(fukui_dir, 'results_DZVP')
os.makedirs(outdir, exist_ok=True)

for name in MOLS:
    xyz = os.path.join(XYZ_DIR, f'{name}.xyz')
    geom = read_xyz(xyz)
    tag = f'{name}_DZVP_b3lyp'
    resdir = run_fukui_for_molecule(tag, geom, outdir, basis='DZVP', xc_func='b3lyp',
                                    resolution=0.15, margin=4.0)
    plot_2d_slices(resdir, name, vmax_pct=99.5)
    plot_1d_cuts(resdir, name)
    print()
