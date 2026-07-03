#!/usr/bin/env python3
"""Plot Fukui function 2D slices for metal clusters.

Takes a YZ-plane slice through x=0 (apex atom), showing the symmetric
cut of the tetrahedron: 2 atoms in-plane, 2 symmetrically out-of-plane.

Usage:
    python plot_fukui_slices_metal.py --mol Ag4 --basis def2svp
    python plot_fukui_slices_metal.py --mol Au4 --basis lanl2dz --out png
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
RESULTS_DIR = os.path.join(fukui_dir, 'results_metal')


def plot_fukui_slices(resdir, outpath=None, slice_plane='yz', atom_scale=500,
                       cmap='seismic', dpi=200):
    """Plot f+, f-, f0 on a central slice through the cluster.

    Parameters
    ----------
    resdir : str
        Directory containing fukui_f_*.cube files.
    outpath : str, optional
        Output PNG path. If None, displayed interactively.
    slice_plane : str
        Plane to slice: 'yz' (x=0), 'xz' (y=0), or 'xy' (z=0).
    """
    # Load grids
    f_plus, origin, shape, vecs, atoms = read_cube(os.path.join(resdir, 'fukui_f_plus.cube'))
    f_minus, _, _, _, _ = read_cube(os.path.join(resdir, 'fukui_f_minus.cube'))
    f_zero, _, _, _, _ = read_cube(os.path.join(resdir, 'fukui_f_zero.cube'))

    nx, ny, nz = shape
    xvec, yvec, zvec = vecs
    dx, dy, dz = xvec[0], yvec[1], zvec[2]

    # Convert to Angstrom for axes
    xx = (origin[0] + np.arange(nx) * dx) * BOHR2ANG
    yy = (origin[1] + np.arange(ny) * dy) * BOHR2ANG
    zz = (origin[2] + np.arange(nz) * dz) * BOHR2ANG

    # Atom positions in Angstrom
    apos_bohr = np.array([[a[1], a[2], a[3]] for a in atoms])
    apos = apos_bohr * BOHR2ANG

    # Choose slice axis and find central index
    if slice_plane == 'yz':
        # Slice at x closest to 0 (apex atom)
        target = 0.0
        idx = np.argmin(np.abs(xx - target))
        slice_data = [f_plus[idx, :, :], f_minus[idx, :, :], f_zero[idx, :, :]]
        x_axis, y_axis = yy, zz
        xlabel, ylabel = 'y (Å)', 'z (Å)'
        extent = [yy[0], yy[-1], zz[0], zz[-1]]
        inplane_idx = np.where(np.abs(apos[:, 0] - target) < 0.1)[0]
    elif slice_plane == 'xz':
        target = 0.0
        idx = np.argmin(np.abs(yy - target))
        slice_data = [f_plus[:, idx, :], f_minus[:, idx, :], f_zero[:, idx, :]]
        x_axis, y_axis = xx, zz
        xlabel, ylabel = 'x (Å)', 'z (Å)'
        extent = [xx[0], xx[-1], zz[0], zz[-1]]
        inplane_idx = np.where(np.abs(apos[:, 1] - target) < 0.1)[0]
    elif slice_plane == 'xy':
        target = 0.0
        idx = np.argmin(np.abs(zz - target))
        slice_data = [f_plus[:, :, idx], f_minus[:, :, idx], f_zero[:, :, idx]]
        x_axis, y_axis = xx, yy
        xlabel, ylabel = 'x (Å)', 'y (Å)'
        extent = [xx[0], xx[-1], yy[0], yy[-1]]
        inplane_idx = np.where(np.abs(apos[:, 2] - target) < 0.1)[0]
    else:
        raise ValueError(f"Unknown slice_plane: {slice_plane}")

    titles = [r'$f^+$ (electrophilic)', r'$f^-$ (nucleophilic)', r'$f^0$ (radical)']

    # Symmetric color limits: find max absolute value across all three panels
    vmax = max(np.max(np.abs(d)) for d in slice_data)
    # Add small floor to avoid zero
    vmax = max(vmax, 1e-8)
    print(f"Slice at {slice_plane} index {idx} ({target:.3f} Å target)")
    print(f"Color limits: vmin={-vmax:.3e}, vmax={vmax:.3e}")
    print(f"In-plane atoms: {inplane_idx}")

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
    for ax, data, title in zip(axes, slice_data, titles):
        im = ax.imshow(data.T, origin='lower', extent=extent, cmap=cmap,
                       vmin=-vmax, vmax=vmax, aspect='equal')
        ax.set_title(title, fontsize=12)
        ax.set_xlabel(xlabel, fontsize=11)
        ax.set_ylabel(ylabel, fontsize=11)

        # Overlay atoms: large filled circles for in-plane, open circles for out-of-plane
        for i, (x, y, z) in enumerate(apos):
            if slice_plane == 'yz':
                px, py = y, z
                pz = x
            elif slice_plane == 'xz':
                px, py = x, z
                pz = y
            else:
                px, py = x, y
                pz = z

            # Only show atoms near the slice plane
            if abs(pz - target) < 0.15:
                ax.scatter(px, py, c='black', s=atom_scale, zorder=5, edgecolors='white', linewidths=1.5)
            elif abs(pz - target) < 0.8:
                ax.scatter(px, py, facecolors='none', edgecolors='black', s=atom_scale*0.6, zorder=5, linewidths=1.5)

        plt.colorbar(im, ax=ax, fraction=0.046, pad=0.02)

    fig.tight_layout()
    if outpath:
        fig.savefig(outpath, dpi=dpi, bbox_inches='tight')
        print(f"Saved: {outpath}")
    else:
        plt.show()
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description='Plot Fukui 2D slices for metal clusters')
    parser.add_argument('--mol', type=str, required=True, help='Cluster name (e.g. Ag4, Au4)')
    parser.add_argument('--basis', type=str, default='def2svp',
                        help='Basis tag in directory name (default: def2svp)')
    parser.add_argument('--xc', type=str, default='pbe',
                        help='XC functional tag (default: pbe)')
    parser.add_argument('--plane', type=str, default='yz', choices=['yz', 'xz', 'xy'],
                        help='Slice plane (default: yz, i.e. x=0)')
    parser.add_argument('--out', type=str, default=None,
                        help='Output PNG path. If omitted, auto-generated.')
    parser.add_argument('--cmap', type=str, default='seismic',
                        help='Colormap (default: seismic)')
    parser.add_argument('--results-dir', type=str, default=RESULTS_DIR,
                        help='Results parent directory')
    args = parser.parse_args()

    tag = f"{args.mol}_{args.xc}_{args.basis}"
    resdir = os.path.join(args.results_dir, tag)
    if not os.path.isdir(resdir):
        print(f"ERROR: Results directory not found: {resdir}")
        sys.exit(1)

    outpath = args.out
    if outpath is None:
        outpath = os.path.join(resdir, f'{tag}_fukui_{args.plane}_slice.png')

    plot_fukui_slices(resdir, outpath=outpath, slice_plane=args.plane, cmap=args.cmap)


if __name__ == '__main__':
    main()
