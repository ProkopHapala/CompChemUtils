#!/usr/bin/env python3
"""
run_cluster_relax.py — relax molecule+cluster systems with xTB and/or DFTB+.

Usage:
    python run_cluster_relax.py --backend xtb --method GFN2-xTB --xyz tmp/cluster_apex/HCN_ep_cluster_attach_orients.xyz --outdir tmp/relax_xtb
    python run_cluster_relax.py --backend dftb --sk-path /path/to/slakos --method D3 --xyz tmp/cluster_apex/HCN_ep_cluster_attach_orients.xyz --outdir tmp/relax_dftb
"""

import os
import sys
import time
import argparse

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from py.AtomicSystem import AtomicSystem
from py.tasks.relax import relax


def main():
    parser = argparse.ArgumentParser(description='Relax molecule+cluster with QC backend')
    parser.add_argument('--backend', choices=['xtb', 'dftb', 'pyscf'], required=True)
    parser.add_argument('--method', default=None, help='Method string (e.g. GFN2-xTB, D3)')
    parser.add_argument('--basis', default=None, help='Basis set (DFTB+ only; None for semiempirical)')
    parser.add_argument('--sk-path', default=None, help='DFTB+ Slater-Koster directory')
    parser.add_argument('--xyz', required=True, help='Input XYZ file (single frame or movie)')
    parser.add_argument('--frame', type=int, default=0, help='Frame index to relax (default 0)')
    parser.add_argument('--outdir', default='tmp/relax', help='Output directory')
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    # Load geometry
    mol = AtomicSystem(fname=args.xyz)
    print(f"Loaded {args.xyz}  natoms={mol.natoms}  enames={set(mol.enames)}")

    if args.backend == 'xtb':
        from py.interfaces.xtb import XTBBBackend
        backend = XTBBBackend(method=args.method or 'GFN2-xTB', n_threads=4)
    elif args.backend == 'dftb':
        from py.interfaces.dftbplus import DFTBPlusBackend
        if args.sk_path is None:
            args.sk_path = os.environ.get('DFTB_SK_PATH')
        if args.sk_path is None:
            raise RuntimeError("DFTB+ requires --sk-path or DFTB_SK_PATH env var")
        backend = DFTBPlusBackend(sk_path=args.sk_path, method=args.method, temperature=300.0)
    elif args.backend == 'pyscf':
        from py.interfaces.pyscf import PySCFBackend
        backend = PySCFBackend(verbose=0, engine='ase')
    else:
        raise ValueError(f"Unknown backend {args.backend}")

    print(f"Backend: {backend.name}  method={args.method}  basis={args.basis}")

    # Freeze Au atoms (cluster substrate)
    from py.geom_engine import freeze_atoms
    au_indices = [i for i, e in enumerate(mol.enames) if e == 'Au']
    constraints = [freeze_atoms(au_indices)] if au_indices else None
    if au_indices:
        print(f"Freeze Au atoms: {au_indices}")

    # pySCF: def2-svp for Au lacks ECP → unphysical forces.
    # Use lanl2dz+ECP for Au, def2-svp for organics.
    basis = args.basis
    ecp = None
    if args.backend == 'pyscf' and au_indices and basis == 'def2-svp':
        basis = {e: 'def2-svp' for e in set(mol.enames) if e != 'Au'}
        basis['Au'] = 'lanl2dz'
        ecp = {'Au': 'lanl2dz'}
        print("Using lanl2dz+ECP for Au, def2-svp for organics")

    t0 = time.time()
    result = relax(mol, backend=backend, method=args.method or 'pbe', basis=basis,
                   ecp=ecp, constraints=constraints, mode='local', outdir=args.outdir)
    walltime = time.time() - t0

    # Reset Au positions after relaxation (pySCF doesn't natively support constraints)
    if au_indices and args.backend == 'pyscf':
        import numpy as np
        result.geom.apos[au_indices] = mol.apos[au_indices]
        print("Reset Au atoms to original positions")

    out_xyz = os.path.join(args.outdir, 'relaxed.xyz')
    result.geom.saveXYZ(out_xyz, bQs=False)

    print(f"Converged: {result.converged}  n_steps: {result.n_steps}  walltime: {walltime:.2f}s")
    print(f"Wrote {out_xyz}")


if __name__ == '__main__':
    main()
