#!/usr/bin/env python3
"""Plot 2D slices of density cubes and Fukui difference cubes.

Panels: rho_N, rho_A, rho_C, f+, f-
Atom overlays in Angstrom.  Grid origin/vectors assumed orthogonal.
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
from fukui_backend import read_cube

B2A = 0.529177210903


def draw_atoms_2d(ax, apos_ang, ax1, ax2):
    """Draw tiny dot markers for atoms onto arbitrary 2D axes.

    ax1, ax2 : int
        Column indices into apos_ang for the horizontal / vertical axes.
    """
    x = apos_ang[:, ax1]
    y = apos_ang[:, ax2]
    ax.plot(x, y, 'k.', markersize=1, zorder=10)


def plot_2d_slice(ax, data_3d, origin, vecs, atoms, title, plane='xz',
                  cmap='viridis', vmin=None, vmax=None, norm=None, zlim=None, density_cmap='viridis', fukui_cmap='seismic'):
    """Plot a 2D slice through a 3D cube.

    Parameters
    ----------
    plane : {'xy', 'xz', 'yz'}
        Which plane to slice (central index fixed for the omitted axis).
    zlim : tuple (zmin, zmax) or None
        If given and plane is 'xz' or 'yz', crop data to this z-range (in Angstrom).
    """
    nx, ny, nz = data_3d.shape
    xvec, yvec, zvec = vecs
    dx, dy, dz = xvec[0], yvec[1], zvec[2]

    if plane == 'xy':
        iz = nz // 2
        slice_data = data_3d[:, :, iz]          # (nx, ny)
        slice_data = slice_data.T                # (ny, nx)
        xx = (origin[0] + np.arange(nx) * dx) * B2A
        yy = (origin[1] + np.arange(ny) * dy) * B2A
        xlabel, ylabel = 'x (Å)', 'y (Å)'
        ax1, ax2 = 0, 1
    elif plane == 'xz':
        iy = ny // 2
        slice_data = data_3d[:, iy, :]           # (nx, nz)
        xx = (origin[0] + np.arange(nx) * dx) * B2A
        zz = (origin[2] + np.arange(nz) * dz) * B2A
        if zlim is not None:
            zmin, zmax = zlim
            iz0 = np.argmin(np.abs(zz - zmin))
            iz1 = np.argmin(np.abs(zz - zmax))
            if iz0 > iz1:
                iz0, iz1 = iz1, iz0
            slice_data = slice_data[:, iz0:iz1+1]  # (nx, nz_crop)
            zz = zz[iz0:iz1+1]
        slice_data = slice_data.T                # (nz_crop, nx)
        xlabel, ylabel = 'x (Å)', 'z (Å)'
        ax1, ax2 = 0, 2
    elif plane == 'yz':
        ix = nx // 2
        slice_data = data_3d[ix, :, :]           # (ny, nz)
        yy = (origin[1] + np.arange(ny) * dy) * B2A
        zz = (origin[2] + np.arange(nz) * dz) * B2A
        if zlim is not None:
            zmin, zmax = zlim
            iz0 = np.argmin(np.abs(zz - zmin))
            iz1 = np.argmin(np.abs(zz - zmax))
            if iz0 > iz1:
                iz0, iz1 = iz1, iz0
            slice_data = slice_data[:, iz0:iz1+1]  # (ny, nz_crop)
            zz = zz[iz0:iz1+1]
        slice_data = slice_data.T                # (nz_crop, ny)
        xlabel, ylabel = 'y (Å)', 'z (Å)'
        ax1, ax2 = 1, 2
    else:
        raise ValueError(f"Unknown plane: {plane}")

    apos_bohr = np.array([[a[1], a[2], a[3]] for a in atoms])
    apos_ang = apos_bohr * B2A

    # Use pcolormesh for better axis limit control with aspect='equal'
    actual_cmap = density_cmap if norm is None else fukui_cmap
    if plane == 'xy':
        X, Y = np.meshgrid(xx, yy)
        im = ax.pcolormesh(X, Y, slice_data, cmap=actual_cmap, vmin=vmin, vmax=vmax, norm=norm, shading='auto')
    elif plane == 'xz':
        X, Z = np.meshgrid(xx, zz)
        im = ax.pcolormesh(X, Z, slice_data, cmap=actual_cmap, vmin=vmin, vmax=vmax, norm=norm, shading='auto')
    elif plane == 'yz':
        Y, Z = np.meshgrid(yy, zz)
        im = ax.pcolormesh(Y, Z, slice_data, cmap=actual_cmap, vmin=vmin, vmax=vmax, norm=norm, shading='auto')

    ax.set_title(title, fontsize=11)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    draw_atoms_2d(ax, apos_ang, ax1, ax2)
    plt.colorbar(im, ax=ax, shrink=0.7, pad=0.02)
    ax.set_aspect('equal')
    return im


def plot_all(cube_N, cube_A, cube_C, outpath, plane='xz',
             vmax_rho=None, vmax_f=None, vmax_pct=99.5, zlim=None, density_cmap='viridis', fukui_cmap='seismic'):
    rho_N, origin, shape, vecs, atoms = read_cube(cube_N)
    rho_A, _, _, _, _ = read_cube(cube_A)
    rho_C, _, _, _, _ = read_cube(cube_C)

    f_plus = rho_A - rho_N
    f_minus = rho_N - rho_C

    # Density vmax: use explicit if given, else percentile
    if vmax_rho is None:
        vmax_rho = float(np.percentile(rho_N, vmax_pct))

    # Fukui vmax: use explicit if given, else percentile of pooled abs values
    if vmax_f is None:
        all_abs = np.concatenate([np.abs(f_plus).ravel(), np.abs(f_minus).ravel()])
        vmax_f = float(np.percentile(all_abs, vmax_pct))

    fig, axes = plt.subplots(2, 3, figsize=(14, 9))
    fig.suptitle(f'{plane.upper()} central slices', fontsize=13)

    plot_2d_slice(axes[0, 0], rho_N, origin, vecs, atoms,
                  r'$\rho_N$  (neutral)', plane=plane, vmin=0, vmax=vmax_rho, zlim=zlim, density_cmap=density_cmap)
    plot_2d_slice(axes[0, 1], rho_A, origin, vecs, atoms,
                  r'$\rho_A$  (anion N+1)', plane=plane, vmin=0, vmax=vmax_rho, zlim=zlim, density_cmap=density_cmap)
    plot_2d_slice(axes[0, 2], rho_C, origin, vecs, atoms,
                  r'$\rho_C$  (cation N-1)', plane=plane, vmin=0, vmax=vmax_rho, zlim=zlim, density_cmap=density_cmap)

    norm = TwoSlopeNorm(vmin=-vmax_f, vcenter=0, vmax=vmax_f)
    plot_2d_slice(axes[1, 0], f_plus, origin, vecs, atoms,
                  r'$f^+ = \rho_A - \rho_N$', plane=plane, norm=norm, zlim=zlim, fukui_cmap=fukui_cmap)
    plot_2d_slice(axes[1, 1], f_minus, origin, vecs, atoms,
                  r'$f^- = \rho_N - \rho_C$', plane=plane, norm=norm, zlim=zlim, fukui_cmap=fukui_cmap)
    plot_2d_slice(axes[1, 2], 0.5*(f_plus + f_minus), origin, vecs, atoms,
                  r'$f^0 = 0.5(f^+ + f^-)$', plane=plane, norm=norm, zlim=zlim, fukui_cmap=fukui_cmap)

    for ax in axes.ravel():
        if not ax.has_data():
            ax.axis('off')

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(outpath, dpi=200, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved: {outpath}")


def main():
    parser = argparse.ArgumentParser(description='Plot 2D slices of densities and Fukui functions.')
    parser.add_argument('--cube-N', required=True, help='Neutral density cube')
    parser.add_argument('--cube-A', required=True, help='Anion density cube (N+1)')
    parser.add_argument('--cube-C', required=True, help='Cation density cube (N-1)')
    parser.add_argument('--out', required=True, help='Output PNG path')
    parser.add_argument('--slice', choices=['xy', 'xz', 'yz'], default='xz',
                        help='Slice plane (default: xz)')
    parser.add_argument('--zmin', type=float, default=2.0, help='z-axis lower limit (default: 2.0)')
    parser.add_argument('--zmax', type=float, default=5.0, help='z-axis upper limit (default: 5.0)')
    parser.add_argument('--vmax-rho', type=float, default=None, help='Density vmax (default: 99.5 pctile)')
    parser.add_argument('--vmax-fukui', type=float, default=None, help='Fukui abs vmax (default: 99.5 pctile)')
    parser.add_argument('--vmax-pct', type=float, default=99.5, help='Percentile fallback when vmax not set')
    parser.add_argument('--cmap-density', default='viridis', help='Colormap for density panels (default: viridis)')
    parser.add_argument('--cmap-fukui', default='seismic', help='Colormap for Fukui panels (default: seismic)')
    args = parser.parse_args()

    zlim = (args.zmin, args.zmax)
    plot_all(args.cube_N, args.cube_A, args.cube_C, args.out,
             plane=args.slice, vmax_rho=args.vmax_rho, vmax_f=args.vmax_fukui,
             vmax_pct=args.vmax_pct, zlim=zlim, density_cmap=args.cmap_density, fukui_cmap=args.cmap_fukui)


if __name__ == '__main__':
    main()
