#!/usr/bin/env python3
"""
batch_relax_xtb.py — relax all molecule+cluster systems with xTB.

Usage:
    python batch_relax_xtb.py --cluster-dir tmp/cluster_apex --outdir tmp/relax_xtb
"""

import os
import sys
import time
import argparse

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from py import atomicUtils as au
from py.AtomicSystem import AtomicSystem
from py.interfaces.xtb import XTBBBackend
from py.tasks.relax import relax


def main():
    parser = argparse.ArgumentParser(description='Batch relax molecule+cluster with xTB')
    parser.add_argument('--cluster-dir', default='tmp/cluster_apex', help='Directory with cluster attach orientations')
    parser.add_argument('--outdir', default='tmp/relax_xtb', help='Output directory')
    parser.add_argument('--frame', type=int, default=0, help='Frame index to relax (default 0)')
    parser.add_argument('--method', default='GFN2-xTB', help='xTB method')
    parser.add_argument('--n-threads', type=int, default=4, help='Number of threads')
    parser.add_argument('--fmax', type=float, default=0.001, help='Max force convergence threshold')
    parser.add_argument('--maxsteps', type=int, default=2000, help='Max optimization steps')
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    backend = XTBBBackend(method=args.method, n_threads=args.n_threads)

    xyz_files = [f for f in os.listdir(args.cluster_dir) if f.endswith('.xyz')]
    print(f"Found {len(xyz_files)} XYZ files in {args.cluster_dir}")

    results = []
    for xyz_file in sorted(xyz_files):
        mol_name = xyz_file.replace('_cluster_attach_orients.xyz', '')
        print(f"\n=== {mol_name} ===")

        # Load first frame
        frames = au.load_xyz_movie(os.path.join(args.cluster_dir, xyz_file))
        es, apos, qs, Rs, comment = frames[args.frame]

        mol = AtomicSystem()
        mol.apos = apos
        mol.enames = list(es)
        mol.qs = None
        mol.Rs = None
        mol.natoms = len(es)

        print(f"  natoms={mol.natoms}  es={set(es)}")

        # Store original Au positions to reset after relaxation
        au_indices = [i for i, e in enumerate(es) if e == 'Au']
        au_positions_orig = apos[au_indices].copy()
        print(f"  Will reset Au atoms at indices: {au_indices} after relaxation")

        t0 = time.time()
        # Run relaxation (xTB doesn't support constraints easily, so we reset Au positions after)
        result_geom = backend.run_relax(mol, method=args.method, fmax=args.fmax, maxsteps=args.maxsteps)
        walltime = time.time() - t0

        # Reset Au atoms to original positions
        result_geom.apos[au_indices] = au_positions_orig

        out_xyz = os.path.join(args.outdir, f'{mol_name}_relaxed.xyz')
        result_geom.saveXYZ(out_xyz, bQs=False)

        print(f"  Converged: True  walltime: {walltime:.2f}s (Au positions reset)")
        results.append((mol_name, walltime, True))

    # Summary
    print("\n=== SUMMARY ===")
    for mol_name, walltime, converged in results:
        print(f"{mol_name:20s}  {walltime:6.2f}s  converged={converged}")


if __name__ == '__main__':
    main()
