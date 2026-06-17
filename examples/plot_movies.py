#!/usr/bin/env python3
"""
plot_movies.py — visualize XYZ movie files as XY and XZ plots.

Thin wrapper around plotUtils.plotGeometry.

Usage:
    python plot_movies.py --movie FILE.xyz --outdir DIR [--replicate 2 2]
    python plot_movies.py --movie-dir DIR --outdir DIR [--replicate 2 2]
"""

import os
import sys
import argparse

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

import matplotlib.pyplot as plt
from py import plotUtils as pu


def _load_first_frame(xyz_path):
    """Load first frame via ASE (preserves Lattice from extxyz comments)."""
    from ase.io import read
    atoms = read(xyz_path, index=0)
    return (list(atoms.get_chemical_symbols()),
            atoms.get_positions(),
            atoms.get_cell())


def plot_system(es, ps, lvs, title='', fname=None, replicate=(1, 1), bBondLabels=False):
    """Side-by-side XY and XZ views using plotUtils.plotGeometry."""
    fig, axes = plt.subplots(1, 2, figsize=(10, 5))
    pu.plotGeometry(ps, es, lvs=lvs, replicate=(replicate[0], replicate[1], 1),
                    axes=(0, 1), title='XY view', ax=axes[0], bDrawBox=True,
                    bBondLabels=bBondLabels, bAtomNumLabels=True, bBlackLabels=True, bNoEdge=True)
    pu.plotGeometry(ps, es, lvs=lvs, replicate=(replicate[0], replicate[1], 1),
                    axes=(0, 2), title='XZ view', ax=axes[1], bDrawBox=True,
                    bBondLabels=bBondLabels, bAtomNumLabels=True, bBlackLabels=True, bNoEdge=True)
    fig.suptitle(title, fontsize=11)
    fig.tight_layout()
    if fname is not None:
        fig.savefig(fname, dpi=150, bbox_inches='tight')
        plt.close(fig)
        print(f"Wrote {fname}")
    else:
        plt.show()
    return fig


def process_movie(xyz_path, outdir, replicate=(1, 1), bBondLabels=False):
    """Generate plot for a single XYZ movie (first frame only)."""
    os.makedirs(outdir, exist_ok=True)
    tag = os.path.splitext(os.path.basename(xyz_path))[0]
    es, ps, lvs = _load_first_frame(xyz_path)
    fname = os.path.join(outdir, f'{tag}.png')
    plot_system(es, ps, lvs, title=tag, fname=fname, replicate=replicate, bBondLabels=bBondLabels)


def main():
    parser = argparse.ArgumentParser(description='Visualize XYZ movies as XY/XZ plots')
    parser.add_argument('--movie', default=None, help='Single XYZ movie file')
    parser.add_argument('--movie-dir', default=None, help='Directory with *.xyz movies')
    parser.add_argument('--outdir', default='tmp/plots', help='Output directory')
    parser.add_argument('--replicate', type=int, nargs=2, default=[1, 1],
                        help='Replicate cell nx ny in XY plane (default 1 1)')
    parser.add_argument('--bond-labels', action='store_true', help='Show bond length labels')
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    rep = tuple(args.replicate)
    if args.movie:
        process_movie(args.movie, args.outdir, replicate=rep, bBondLabels=args.bond_labels)
    elif args.movie_dir:
        for fname in sorted(os.listdir(args.movie_dir)):
            if not fname.endswith('.xyz'):
                continue
            process_movie(os.path.join(args.movie_dir, fname), args.outdir, replicate=rep,
                          bBondLabels=args.bond_labels)
    else:
        raise ValueError("Need --movie or --movie-dir")


if __name__ == '__main__':
    main()
