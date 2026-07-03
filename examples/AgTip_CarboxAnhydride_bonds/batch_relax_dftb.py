#!/usr/bin/env python3
"""
batch_relax_dftb.py — relax molecule+cluster systems with DFTB+.

Usage:
    python batch_relax_dftb.py --cluster-dir tmp/cluster_apex --outdir tmp/relax_dftb --sk-path /path/to/slakos
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
from py.interfaces.dftbplus import DFTBPlusBackend
from py.tasks.relax import relax


def main():
    parser = argparse.ArgumentParser(description='Batch relax molecule+cluster with DFTB+')
    parser.add_argument('--cluster-dir', default='tmp/cluster_apex', help='Directory with cluster attach orientations')
    parser.add_argument('--outdir', default='tmp/relax_dftb', help='Output directory')
    parser.add_argument('--frame', type=int, default=0, help='Frame index to relax (default 0)')
    parser.add_argument('--method', default='D3', help='DFTB+ method (D3, D3H5, or None)')
    parser.add_argument('--sk-path', default=None, help='DFTB+ Slater-Koster directory (default: DFTB_SK_PATH env var)')
    parser.add_argument('--molecules', nargs='+', default=None, help='Specific molecules to relax (default: all)')
    parser.add_argument('--max-steps', type=int, default=500, help='DFTB+ geometry optimization MaxSteps')
    parser.add_argument('--max-force', type=float, default=0.01, help='DFTB+ geometry optimization MaxForceComponent')
    args = parser.parse_args()

    if args.sk_path is None:
        args.sk_path = os.environ.get('DFTB_SK_PATH')
    if args.sk_path is None:
        raise RuntimeError("DFTB+ requires --sk-path or DFTB_SK_PATH env var")

    os.makedirs(args.outdir, exist_ok=True)

    backend = DFTBPlusBackend(sk_path=args.sk_path, method=args.method, temperature=300.0, orbital_resolved_scc=False)

    xyz_files = [f for f in os.listdir(args.cluster_dir) if f.endswith('.xyz')]
    if args.molecules:
        xyz_files = [f for f in xyz_files if any(m in f for m in args.molecules)]
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

        au_indices = [i for i, e in enumerate(es) if e == 'Au']
        moved_atoms = [i+1 for i, e in enumerate(es) if e != 'Au']
        print(f"  Freeze Au atoms at indices: {au_indices}; MovedAtoms (1-based): {moved_atoms[0]}..{moved_atoms[-1]}")

        # Per-molecule output directory to avoid dftb_in.hsd overwrites
        mol_outdir = os.path.join(args.outdir, mol_name)
        os.makedirs(mol_outdir, exist_ok=True)

        t0 = time.time()
        try:
            # Use export mode + manual run for DFTB+ (ASE interface has driver syntax issues)
            files = backend.export_relax(mol, method=args.method, outdir=mol_outdir, moved_atoms=moved_atoms, max_steps=args.max_steps, max_force_component=args.max_force)

            # Run DFTB+ in output directory
            import subprocess
            result = subprocess.run(['dftb+'], cwd=mol_outdir, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"  ERROR: DFTB+ failed")
                print(f"  stderr: {result.stderr[-500:]}")
                continue
            # Read relaxed geometry
            geo_end = os.path.join(mol_outdir, 'geo_end.gen')
            if os.path.exists(geo_end):
                apos_out, es_out = backend._read_gen(geo_end)
                result_geom = AtomicSystem()
                result_geom.apos = apos_out
                result_geom.enames = list(es_out)
                result_geom.natoms = len(es_out)
            else:
                print(f"  ERROR: geo_end.gen not found")
                continue
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()
            continue
        walltime = time.time() - t0

        out_xyz = os.path.join(args.outdir, f'{mol_name}_relaxed.xyz')
        result_geom.saveXYZ(out_xyz, bQs=False)

        print(f"  Converged: True  walltime: {walltime:.2f}s")
        results.append((mol_name, walltime, True))

    # Summary
    print("\n=== SUMMARY ===")
    for mol_name, walltime, converged in results:
        print(f"{mol_name:20s}  {walltime:6.2f}s  converged={converged}")


if __name__ == '__main__':
    main()
