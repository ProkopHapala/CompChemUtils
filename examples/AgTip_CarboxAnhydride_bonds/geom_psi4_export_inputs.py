#!/usr/bin/env python3

import os
import argparse

from py.export_psi4_jobs import export_movie_to_psi4


def main():
    parser = argparse.ArgumentParser(description='Export Psi4 inputs from XYZ movie frames')
    parser.add_argument('xyz_movie', help='XYZ movie file')
    parser.add_argument('--outdir', default='tmp/psi4_inputs', help='Output directory')
    parser.add_argument('--method', default='b3lyp', help='Psi4 method (b3lyp, pbe, ...)')
    parser.add_argument('--basis', default='cc-pvdz', help='Main-group basis')
    parser.add_argument('--basis-ag', default='def2-SVP', help='Ag basis')
    parser.add_argument('--ecp-ag', default='def2-SVP', help='Ag ECP')
    parser.add_argument('--no-freeze-ag', action='store_true', help='Do not freeze Ag atoms')
    parser.add_argument('--opt', action='store_true', help='Optimize geometry instead of single-point energy')
    parser.add_argument('--mem', default='2GB', help='Psi4 memory')
    args = parser.parse_args()

    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    xyz_movie = args.xyz_movie
    if not os.path.isabs(xyz_movie):
        xyz_movie = os.path.join(repo, xyz_movie)

    outdir = args.outdir
    if not os.path.isabs(outdir):
        outdir = os.path.join(repo, outdir)

    res = export_movie_to_psi4(
        xyz_movie=xyz_movie,
        outdir=outdir,
        method=args.method,
        basis_main=args.basis,
        basis_ag=args.basis_ag,
        ecp_ag=args.ecp_ag,
        freeze_ag=(not args.no_freeze_ag),
        opt=args.opt,
        mem=args.mem,
    )

    print(f"Exported {res['n_frames']} Psi4 inputs into {outdir}")


if __name__ == '__main__':
    main()
