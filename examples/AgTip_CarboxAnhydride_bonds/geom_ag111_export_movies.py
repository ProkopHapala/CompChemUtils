#!/usr/bin/env python3

import os
import argparse

from py.export_gpaw_jobs import export_surface_movie_from_molecule_frames


def main():
    parser = argparse.ArgumentParser(description='Generate Ag(111)+adatom + molecule orientation movies (PBC)')
    parser.add_argument('--outdir', default='tmp/ag111_movies', help='Output directory')
    parser.add_argument('--dist', type=float, default=2.0, help='Adatom-host distance (A)')
    parser.add_argument('--size', type=int, nargs=3, default=[2, 2, 2], help='Surface size nx ny nz')
    parser.add_argument('--a', type=float, default=4.086, help='Ag lattice constant (A)')
    parser.add_argument('--vacuum', type=float, default=10.0, help='Vacuum (A)')
    parser.add_argument('--adatom-height', type=float, default=2.0, help='Adatom height above top layer (A)')
    parser.add_argument('--tilts', type=float, nargs='*', default=[20.0, 45.0], help='Tilt angles wrt +z (deg)')
    parser.add_argument('--rolls', type=float, nargs='*', default=[0.0, 90.0], help='Roll angles around scan direction (deg)')
    parser.add_argument('--keep-epairs', action='store_true', help='Keep E dummy atoms')
    parser.add_argument('--export-structs', action='store_true', help='Write extxyz/cif/POSCAR for each frame')
    parser.add_argument('--plot-dirs', action='store_true', help='Write direction plot PNG')
    parser.add_argument('--mols', nargs='*', default=[
        'data/xyz/H2O.xyz',
        'data/xyz/NH3.xyz',
        'data/xyz/CH2NH.xyz',
        'data/xyz/CH2O.xyz',
        'data/xyz/HCN.xyz',
    ])
    args = parser.parse_args()

    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    outdir = os.path.join(repo, args.outdir)
    os.makedirs(outdir, exist_ok=True)

    plot_png = os.path.join(outdir, 'ag111_scan_directions.png') if args.plot_dirs else None

    for im, mol_rel in enumerate(args.mols):
        mol_xyz = os.path.join(repo, mol_rel)
        tag = os.path.splitext(os.path.basename(mol_rel))[0]
        out_xyz = os.path.join(outdir, f'{tag}_Ag111_attach_orients.xyz')

        frame_dir = os.path.join(outdir, f'{tag}_frames') if args.export_structs else None
        plot_here = plot_png if (plot_png is not None and im == 0) else None

        res = export_surface_movie_from_molecule_frames(
            mol_xyz=mol_xyz,
            out_xyz=out_xyz,
            surface_size=tuple(args.size),
            a=args.a,
            vacuum=args.vacuum,
            adatom_height=args.adatom_height,
            dist=args.dist,
            tilt_degs=tuple(args.tilts),
            roll_degs=tuple(args.rolls),
            remove_epairs=(not args.keep_epairs),
            outdir_struct=frame_dir,
            plot_dirs_png=plot_here,
        )

        print(f"Wrote {res['n_frames']} frames to {out_xyz}  adatom_index={res['surface_adatom_index']} base3={res['base3']}")
        if frame_dir is not None:
            print(f"Wrote per-frame structures to {frame_dir}")

    if plot_png is not None:
        print(f"Wrote direction plot: {plot_png}")


if __name__ == '__main__':
    main()
