#!/usr/bin/env python3

import os
import argparse

from py.export_gpaw_jobs import write_gpaw_runner


def main():
    parser = argparse.ArgumentParser(description='Export GPAW runner scripts from Ag111 edgepair per-frame structures')
    parser.add_argument('frame_dir', help='Directory containing per-tilt frames (e.g. tmp/ag111_edgepair_movies/maleic_anhydride_frames)')
    parser.add_argument('--outdir', default='tmp/gpaw_edge_runners', help='Output directory')
    parser.add_argument('--xc', default='PBE', help='XC functional')
    parser.add_argument('--pw', type=int, default=400, help='Plane-wave cutoff (eV)')
    parser.add_argument('--kpts', type=int, nargs=3, default=[4, 4, 1], help='k-point grid')
    parser.add_argument('--fix-indices', type=int, nargs='*', default=None, help='ASE FixAtoms indices (e.g. all surface atoms)')
    parser.add_argument('--mem', default='2GB', help='Memory hint (not used by GPAW, kept for consistency)')
    args = parser.parse_args()

    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    frame_dir = args.frame_dir
    if not os.path.isabs(frame_dir):
        frame_dir = os.path.join(repo, frame_dir)

    outdir = os.path.join(repo, args.outdir)
    os.makedirs(outdir, exist_ok=True)

    if args.fix_indices is None:
        fix = None
    else:
        fix = list(args.fix_indices)

    written = 0
    for fname in sorted(os.listdir(frame_dir)):
        if not fname.endswith('.xyz'):
            continue
        struct = os.path.join(frame_dir, fname)
        tag = fname.replace('.xyz', '')
        runner = os.path.join(outdir, f"run_{tag}.py")
        write_gpaw_runner(
            fname=runner,
            structure_file=struct,
            txt=f"gpaw_{tag}.txt",
            xc=args.xc,
            pw=args.pw,
            kpts=tuple(args.kpts),
            fix_indices=fix,
        )
        print(f"Wrote {runner}")
        written += 1

    print(f"Wrote {written} GPAW runner scripts to {outdir}")


if __name__ == '__main__':
    main()
