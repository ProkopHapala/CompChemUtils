#!/usr/bin/env python3

import os
import argparse

from py.geom_engine import generate_ag4_attach_movie


def main():
    parser = argparse.ArgumentParser(description='Generate Ag4+molecule orientation movies (fixed 2.0A by default)')
    parser.add_argument('--ag4', default='data/xyz/Ag4.xyz', help='Ag4 xyz file (default: data/xyz/Ag4.xyz)')
    parser.add_argument('--outdir', default='tmp/ag4_movies', help='Output directory')
    parser.add_argument('--dist', type=float, default=2.0, help='Ag-host distance (A)')
    parser.add_argument('--tilts', type=float, nargs='*', default=[20.0, 45.0], help='Tilt angles wrt +z (deg), e.g. 20 45')
    parser.add_argument('--rolls', type=float, nargs='*', default=[0.0, 90.0], help='Roll angles around scan direction (deg), e.g. 0 90')
    parser.add_argument('--keep-epairs', action='store_true', help='Keep E-pair dummy atoms in output')
    parser.add_argument('--plot-dirs', action='store_true', help='Generate a PNG illustrating scan directions')
    parser.add_argument('--mols', nargs='*', default=[
        'data/xyz/H2O.xyz',
        'data/xyz/NH3.xyz',
        'data/xyz/CH2NH.xyz',
        'data/xyz/CH2O.xyz',
        'data/xyz/HCN.xyz',
    ], help='List of molecule xyz files')
    args = parser.parse_args()

    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ag4_xyz = os.path.join(repo, args.ag4)

    outdir = os.path.join(repo, args.outdir)
    os.makedirs(outdir, exist_ok=True)

    plot_png = os.path.join(outdir, 'ag4_scan_directions.png') if args.plot_dirs else None

    for im, mol_rel in enumerate(args.mols):
        mol_xyz = os.path.join(repo, mol_rel)
        tag = os.path.splitext(os.path.basename(mol_rel))[0]
        out_xyz = os.path.join(outdir, f'{tag}_Ag4_attach_orients.xyz')
        plot_here = plot_png if (plot_png is not None and im == 0) else None

        res = generate_ag4_attach_movie(
            mol_xyz=mol_xyz,
            out_xyz=out_xyz,
            ag4_xyz=ag4_xyz,
            dist=args.dist,
            tilt_degs=tuple(args.tilts),
            roll_degs=tuple(args.rolls),
            remove_epairs=(not args.keep_epairs),
            plot_dirs_png=plot_here,
        )

        print(f"Wrote {res['n_frames']} frames to {out_xyz}  host={res['host_element']}[{res['host_index']}] dist={args.dist}")

    if plot_png is not None:
        print(f"Wrote direction plot: {plot_png}")


if __name__ == '__main__':
    main()
