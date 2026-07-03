#!/usr/bin/env python3
"""Plot Fukui function 2D slices for GPAW M(111)+adatom surface.

Usage:
    venvML && python plot_gpaw_fukui_slices.py --metal Ag
    venvML && python plot_gpaw_fukui_slices.py --metal Au
    venvML && python plot_gpaw_fukui_slices.py --metal Cu
"""

import os
import sys
import argparse
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

fukui_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, fukui_dir)
from fukui_backend import read_cube

BOHR2ANG = 0.529177210903


def plot_fukui_slices(resdir, outpath=None, plane='yz', atom_scale=500,
                       cmap='seismic', dpi=200):
    """Plot f+, f-, f0 on a central slice."""
    # Load grids from cube (use N cube for metadata)
    rho_N, origin, shape, vecs, atoms = read_cube(os.path.join(resdir, 'rho_N.cube'))
    rho_A, _, _, _, _ = read_cube(os.path.join(resdir, 'rho_A.cube'))
    rho_C, _, _, _, _ = read_cube(os.path.join(resdir, 'rho_C.cube'))

    f_plus = rho_A - rho_N
    f_minus = rho_N - rho_C
    f_zero = 0.5 * (f_plus + f_minus)

    nx, ny, nz = shape
    xvec, yvec, zvec = vecs
    dx, dy, dz = xvec[0], yvec[1], zvec[2]

    xx = (origin[0] + np.arange(nx) * dx) * BOHR2ANG
    yy = (origin[1] + np.arange(ny) * dy) * BOHR2ANG
    zz = (origin[2] + np.arange(nz) * dz) * BOHR2ANG

    apos_bohr = np.array([[a[1], a[2], a[3]] for a in atoms])
    apos = apos_bohr * BOHR2ANG

    # Identify adatom: highest z position
    adatom_idx = int(np.argmax(apos[:, 2]))
    adatom_pos = apos[adatom_idx]
    print(f"Adatom index: {adatom_idx}, position: {adatom_pos}")

    if plane == 'yz':
        target = adatom_pos[0]  # x of adatom
        idx = np.argmin(np.abs(xx - target))
        slice_data = [f_plus[idx, :, :], f_minus[idx, :, :], f_zero[idx, :, :]]
        x_axis, y_axis = yy, zz
        xlabel, ylabel = 'y (Å)', 'z (Å)'
        extent = [yy[0], yy[-1], zz[0], zz[-1]]
    elif plane == 'xz':
        target = adatom_pos[1]  # y of adatom
        idx = np.argmin(np.abs(yy - target))
        slice_data = [f_plus[:, idx, :], f_minus[:, idx, :], f_zero[:, idx, :]]
        x_axis, y_axis = xx, zz
        xlabel, ylabel = 'x (Å)', 'z (Å)'
        extent = [xx[0], xx[-1], zz[0], zz[-1]]
    elif plane == 'xy':
        target = adatom_pos[2]  # z of adatom
        idx = np.argmin(np.abs(zz - target))
        slice_data = [f_plus[:, :, idx], f_minus[:, :, idx], f_zero[:, :, idx]]
        x_axis, y_axis = xx, yy
        xlabel, ylabel = 'x (Å)', 'y (Å)'
        extent = [xx[0], xx[-1], yy[0], yy[-1]]
    else:
        raise ValueError(f"Unknown plane: {plane}")

    titles = [r'$f^+$ (electrophilic)', r'$f^-$ (nucleophilic)', r'$f^0$ (radical)']
    vmax = max(np.max(np.abs(d)) for d in slice_data)
    vmax = max(vmax, 1e-8)

    print(f"Slice at {plane} index {idx} ({target:.3f} Å target)")
    print(f"Color limits: vmin={-vmax:.3e}, vmax={vmax:.3e}")

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
    for ax, data, title in zip(axes, slice_data, titles):
        im = ax.imshow(data.T, origin='lower', extent=extent, cmap=cmap,
                       vmin=-vmax, vmax=vmax, aspect='equal')
        ax.set_title(title, fontsize=12)
        ax.set_xlabel(xlabel, fontsize=11)
        ax.set_ylabel(ylabel, fontsize=11)

        # No atom markers - they hide the imshow data

        plt.colorbar(im, ax=ax, fraction=0.046, pad=0.02)

    fig.tight_layout()
    if outpath:
        fig.savefig(outpath, dpi=dpi, bbox_inches='tight')
        print(f"Saved: {outpath}")
    else:
        plt.show()
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description='Plot Fukui function slices for M(111)+adatom')
    parser.add_argument('--metal', type=str, default='Ag', choices=['Ag', 'Au', 'Cu'],
                        help='Metal element (default: Ag)')
    args = parser.parse_args()

    metal = args.metal
    resdir = os.path.join(fukui_dir, 'results_metal', f'{metal}111_2x2x2_adatom_GPAW_PBE')
    if not os.path.isdir(resdir):
        print(f"ERROR: Results directory not found: {resdir}")
        sys.exit(1)

    for plane in ['yz', 'xz', 'xy']:
        outpath = os.path.join(resdir, f'{metal}111_adatom_fukui_{plane}_slice.png')
        plot_fukui_slices(resdir, outpath=outpath, plane=plane)


if __name__ == '__main__':
    main()
