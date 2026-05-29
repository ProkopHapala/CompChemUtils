#!/usr/bin/env python3
"""CLI wrapper for Fukui function computation via PySCF.

Usage:
    python run_fukui.py --mol H2O --basis def2-svp --xc b3lyp --plot-2d --plot-1d
    python run_fukui.py --mol HCN --basis DZVP --xc pbe0 --plot-2d --vmax-pct 99.0
    python run_fukui.py --mol CO --basis def2-tzvp --xc b3lyp --plot-1d --resolution 0.10

Loads geometry from /home/prokop/git/CompChemUtils/data/xyz/<mol>.xyz.
Results go to results/<mol>_<basis>_<xc>/.
"""

import argparse
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
import numpy as np

fukui_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, fukui_dir)
from fukui_backend import (
    run_fukui_for_molecule, read_cube, read_xyz, B2A
)

XYZ_DIR = '/home/prokop/git/CompChemUtils/data/xyz'


def draw_atoms(ax, plane_axes, apos_ang, labels):
    ax1, ax2 = plane_axes
    x = apos_ang[:, ax1]
    y = apos_ang[:, ax2]
    for i in range(len(apos_ang)):
        for j in range(i + 1, len(apos_ang)):
            d = np.linalg.norm(apos_ang[i] - apos_ang[j])
            if d < 1.8:
                ax.plot([x[i], x[j]], [y[i], y[j]], 'k-', lw=1.5, alpha=0.7, zorder=5)
    elem_colors = {'H': 'lightgray', 'C': 'gray', 'N': 'blue', 'O': 'red', 'Cl': 'green', 'F': 'cyan'}
    elem_sizes = {'H': 120, 'C': 150, 'N': 150, 'O': 150, 'Cl': 180, 'F': 130}
    for i in range(len(apos_ang)):
        c = elem_colors.get(labels[i], 'purple')
        s = elem_sizes.get(labels[i], 100)
        ax.scatter(x[i], y[i], c=c, s=s, edgecolors='black', linewidths=1.0, zorder=10)
        ax.text(x[i], y[i], labels[i], color='white', fontsize=9, ha='center', va='center',
                fontweight='bold', zorder=11)


def plot_2d_slices(resdir, name, vmax_pct=99.5):
    cube_N = os.path.join(resdir, 'rho_N.cube')
    cube_A = os.path.join(resdir, 'rho_A.cube')
    cube_C = os.path.join(resdir, 'rho_C.cube')
    rho_N, origin, shape, vecs, atoms = read_cube(cube_N)
    rho_A, _, _, _, _ = read_cube(cube_A)
    rho_C, _, _, _, _ = read_cube(cube_C)
    nx, ny, nz = shape
    xvec, yvec, zvec = vecs
    dx, dy, dz = xvec[0], yvec[1], zvec[2]
    xx = origin[0] + np.arange(nx) * dx
    yy = origin[1] + np.arange(ny) * dy
    zz = origin[2] + np.arange(nz) * dz
    ix0, iy0, iz0 = nx // 2, ny // 2, nz // 2
    apos_bohr = np.array([[a[1], a[2], a[3]] for a in atoms])
    apos = apos_bohr * B2A
    sym_map = {1: 'H', 6: 'C', 7: 'N', 8: 'O', 9: 'F', 17: 'Cl'}
    labels = [sym_map.get(int(a[0]), str(a[0])) for a in atoms]

    slice_f_p_xy = rho_A[:, :, iz0] - rho_N[:, :, iz0]
    slice_f_m_xy = rho_N[:, :, iz0] - rho_C[:, :, iz0]
    slice_f_p_xz = rho_A[:, iy0, :] - rho_N[:, iy0, :]
    slice_f_m_xz = rho_N[:, iy0, :] - rho_C[:, iy0, :]
    slice_f_p_yz = rho_A[ix0, :, :] - rho_N[ix0, :, :]
    slice_f_m_yz = rho_N[ix0, :, :] - rho_C[ix0, :, :]

    all_data = np.concatenate([
        slice_f_p_xy.ravel(), slice_f_m_xy.ravel(),
        slice_f_p_xz.ravel(), slice_f_m_xz.ravel(),
        slice_f_p_yz.ravel(), slice_f_m_yz.ravel()
    ])
    vabs = float(np.percentile(np.abs(all_data), vmax_pct))

    extent_xy = [xx[0]*B2A, xx[-1]*B2A, yy[0]*B2A, yy[-1]*B2A]
    extent_xz = [xx[0]*B2A, xx[-1]*B2A, zz[0]*B2A, zz[-1]*B2A]
    extent_yz = [yy[0]*B2A, yy[-1]*B2A, zz[0]*B2A, zz[-1]*B2A]

    fig, axes = plt.subplots(3, 2, figsize=(12, 16))
    fig.suptitle(f'{name}: Fukui functions – 2D central slices', fontsize=14)

    def plot_panel(ax, data, extent, plane_axes, title):
        norm = TwoSlopeNorm(vmin=-vabs, vcenter=0, vmax=vabs)
        im = ax.imshow(data.T, origin='lower', cmap='RdBu_r', norm=norm,
                       extent=extent, aspect='equal', interpolation='nearest')
        ax.set_title(title, fontsize=11)
        ax.set_xlabel(f"{['x','y','z'][plane_axes[0]]} (Å)")
        ax.set_ylabel(f"{['x','y','z'][plane_axes[1]]} (Å)")
        cbar = plt.colorbar(im, ax=ax, shrink=0.7, pad=0.02)
        cbar.set_label(r'$\rho$ diff (a.u.)', fontsize=9)
        draw_atoms(ax, plane_axes, apos, labels)
        return im

    plot_panel(axes[0, 0], slice_f_p_xy, extent_xy, (0, 1), r'$f^+$  (xy plane)')
    plot_panel(axes[0, 1], slice_f_m_xy, extent_xy, (0, 1), r'$f^-$  (xy plane)')
    plot_panel(axes[1, 0], slice_f_p_xz, extent_xz, (0, 2), r'$f^+$  (xz plane)')
    plot_panel(axes[1, 1], slice_f_m_xz, extent_xz, (0, 2), r'$f^-$  (xz plane)')
    plot_panel(axes[2, 0], slice_f_p_yz, extent_yz, (1, 2), r'$f^+$  (yz plane)')
    plot_panel(axes[2, 1], slice_f_m_yz, extent_yz, (1, 2), r'$f^-$  (yz plane)')

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    png_path = os.path.join(resdir, f'{name}_fukui_2D_slices.png')
    fig.savefig(png_path, dpi=200, bbox_inches='tight')
    plt.close(fig)
    print(f"  Saved plot: {png_path}")


def plot_1d_cuts(resdir, name):
    cube_N = os.path.join(resdir, 'rho_N.cube')
    cube_A = os.path.join(resdir, 'rho_A.cube')
    cube_C = os.path.join(resdir, 'rho_C.cube')
    rho_N, origin, shape, vecs, atoms = read_cube(cube_N)
    rho_A, _, _, _, _ = read_cube(cube_A)
    rho_C, _, _, _, _ = read_cube(cube_C)

    nx, ny, nz = shape
    xvec, yvec, zvec = vecs
    dx, dy, dz = xvec[0], yvec[1], zvec[2]
    xx = origin[0] + np.arange(nx) * dx
    yy = origin[1] + np.arange(ny) * dy
    zz = origin[2] + np.arange(nz) * dz

    # Find voxel closest to molecular centroid
    apos_bohr = np.array([[a[1], a[2], a[3]] for a in atoms])
    centroid = np.mean(apos_bohr, axis=0)
    ix = np.argmin(np.abs(xx - centroid[0]))
    iy = np.argmin(np.abs(yy - centroid[1]))
    iz = np.argmin(np.abs(zz - centroid[2]))

    f_plus = rho_A - rho_N
    f_minus = rho_N - rho_C

    x_ang = xx * B2A
    y_ang = yy * B2A
    z_ang = zz * B2A

    fig, axes = plt.subplots(3, 2, figsize=(12, 12), sharex=False, sharey=False)
    fig.suptitle(f'{name}: Fukui functions – 1D cuts through molecular center', fontsize=14)

    axes[0, 0].plot(x_ang, f_plus[:, iy, iz], 'r-', lw=1.2, label=r'$f^+$')
    axes[0, 0].plot(x_ang, f_minus[:, iy, iz], 'b-', lw=1.2, label=r'$f^-$')
    axes[0, 0].set_title('x direction')
    axes[0, 0].set_xlabel('x (Å)')
    axes[0, 0].set_ylabel(r'$\rho$ difference (a.u.)')
    axes[0, 0].legend()
    axes[0, 0].axhline(0, color='k', lw=0.5)

    axes[1, 0].plot(y_ang, f_plus[ix, :, iz], 'r-', lw=1.2, label=r'$f^+$')
    axes[1, 0].plot(y_ang, f_minus[ix, :, iz], 'b-', lw=1.2, label=r'$f^-$')
    axes[1, 0].set_title('y direction')
    axes[1, 0].set_xlabel('y (Å)')
    axes[1, 0].set_ylabel(r'$\rho$ difference (a.u.)')
    axes[1, 0].legend()
    axes[1, 0].axhline(0, color='k', lw=0.5)

    axes[2, 0].plot(z_ang, f_plus[ix, iy, :], 'r-', lw=1.2, label=r'$f^+$')
    axes[2, 0].plot(z_ang, f_minus[ix, iy, :], 'b-', lw=1.2, label=r'$f^-$')
    axes[2, 0].set_title('z direction')
    axes[2, 0].set_xlabel('z (Å)')
    axes[2, 0].set_ylabel(r'$\rho$ difference (a.u.)')
    axes[2, 0].legend()
    axes[2, 0].axhline(0, color='k', lw=0.5)

    # Zoomed panels (valence region only)
    def zoom_panel(ax, coord, fp, fm, title):
        # Find range where abs values are below 1% of max for clean zoom
        vmax = max(np.max(np.abs(fp)), np.max(np.abs(fm)))
        mask = (np.abs(fp) < 0.01 * vmax) & (np.abs(fm) < 0.01 * vmax)
        if not np.any(mask):
            mask = np.ones(len(coord), dtype=bool)
        i0, i1 = np.where(mask)[0][0], np.where(mask)[0][-1]
        # Expand a bit
        i0 = max(0, i0 - 5)
        i1 = min(len(coord)-1, i1 + 5)
        ax.plot(coord[i0:i1], fp[i0:i1], 'r-', lw=1.2, label=r'$f^+$')
        ax.plot(coord[i0:i1], fm[i0:i1], 'b-', lw=1.2, label=r'$f^-$')
        ax.set_title(title + ' (zoomed)')
        ax.set_xlabel(title.split()[0] + ' (Å)')
        ax.set_ylabel(r'$\rho$ difference (a.u.)')
        ax.legend()
        ax.axhline(0, color='k', lw=0.5)

    zoom_panel(axes[0, 1], x_ang, f_plus[:, iy, iz], f_minus[:, iy, iz], 'x direction')
    zoom_panel(axes[1, 1], y_ang, f_plus[ix, :, iz], f_minus[ix, :, iz], 'y direction')
    zoom_panel(axes[2, 1], z_ang, f_plus[ix, iy, :], f_minus[ix, iy, :], 'z direction')

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    png_path = os.path.join(resdir, f'{name}_fukui_1D_cuts.png')
    fig.savefig(png_path, dpi=200, bbox_inches='tight')
    plt.close(fig)
    print(f"  Saved plot: {png_path}")


def main():
    parser = argparse.ArgumentParser(description='Compute Fukui functions with PySCF.')
    parser.add_argument('--mol', required=True, help='Molecule name (looks for data/xyz/<mol>.xyz)')
    parser.add_argument('--basis', default='def2-svp', help='Basis set (default: def2-svp)')
    parser.add_argument('--xc', default='b3lyp', help='XC functional (default: b3lyp)')
    parser.add_argument('--resolution', type=float, default=0.15, help='Cube grid resolution in Angstrom (default: 0.15)')
    parser.add_argument('--margin', type=float, default=4.0, help='Cube box margin in Angstrom (default: 4.0)')
    parser.add_argument('--plot-2d', action='store_true', help='Generate 2D central slice plots')
    parser.add_argument('--plot-1d', action='store_true', help='Generate 1D cut plots through molecular center')
    parser.add_argument('--vmax-pct', type=float, default=99.5, help='Percentile for colormap vmax in 2D plots (default: 99.5)')
    args = parser.parse_args()

    xyz_path = os.path.join(XYZ_DIR, f'{args.mol}.xyz')
    if not os.path.isfile(xyz_path):
        print(f"ERROR: XYZ file not found: {xyz_path}")
        sys.exit(1)

    geom = read_xyz(xyz_path)
    print(f"Loaded geometry from {xyz_path}")
    print(f"Method: {args.xc} / {args.basis}")

    outdir = os.path.join(fukui_dir, 'results')
    tag = f"{args.mol}_{args.basis}_{args.xc}"

    resdir = run_fukui_for_molecule(
        tag, geom, outdir,
        basis=args.basis, xc_func=args.xc,
        resolution=args.resolution, margin=args.margin
    )

    if args.plot_2d:
        plot_2d_slices(resdir, args.mol, vmax_pct=args.vmax_pct)
    if args.plot_1d:
        plot_1d_cuts(resdir, args.mol)

    print(f"\n{'='*50}")
    print(f"  Results: {resdir}")
    print(f"{'='*50}")


if __name__ == '__main__':
    main()
