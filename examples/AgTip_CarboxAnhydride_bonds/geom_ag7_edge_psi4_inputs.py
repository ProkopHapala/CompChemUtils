#!/usr/bin/env python3

import os
import argparse

from py.export_psi4_jobs import export_movie_to_psi4


def main():
    parser = argparse.ArgumentParser(description='Export Psi4 inputs from Ag7 edge-molecule XYZ movies')
    parser.add_argument('movie_dir', help='Directory containing *_edge_tilts.xyz movies')
    parser.add_argument('--outdir', default='tmp/psi4_edge_inputs', help='Output directory')
    parser.add_argument('--method', default='b3lyp', help='QM method')
    parser.add_argument('--basis-main', default='cc-pvdz', help='Basis for main-group atoms')
    parser.add_argument('--basis-ag', default='def2-SVP', help='Basis for Ag')
    parser.add_argument('--ecp-ag', default='def2-SVP', help='ECP for Ag')
    parser.add_argument('--freeze-ag', action='store_true', default=True, help='Freeze Ag atoms')
    parser.add_argument('--opt', action='store_true', default=False, help='Optimize instead of single-point')
    parser.add_argument('--mem', default='2GB', help='Memory')
    args = parser.parse_args()

    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    movie_dir = args.movie_dir
    if not os.path.isabs(movie_dir):
        movie_dir = os.path.join(repo, movie_dir)

    outdir = os.path.join(repo, args.outdir)
    os.makedirs(outdir, exist_ok=True)

    for fname in sorted(os.listdir(movie_dir)):
        if not fname.endswith('_edge_tilts.xyz'):
            continue
        xyz_path = os.path.join(movie_dir, fname)
        tag = fname.replace('_edge_tilts.xyz', '')
        subdir = os.path.join(outdir, tag)
        os.makedirs(subdir, exist_ok=True)

        res = export_movie_to_psi4(
            xyz_movie=xyz_path,
            outdir=subdir,
            method=args.method,
            basis_main=args.basis_main,
            basis_ag=args.basis_ag,
            ecp_ag=args.ecp_ag,
            freeze_ag=args.freeze_ag,
            opt=args.opt,
            mem=args.mem,
        )
        print(f"Wrote {res['n_frames']} Psi4 inputs to {subdir}")


if __name__ == '__main__':
    main()
