#!/usr/bin/env python3
"""
relax_dimer.py — build and relax H-bonded dimers via e-pair orientation + xTB / DFTB+.

Uses geom_engine.build_hbond_dimer() to orient monomers (lone pairs from E atoms),
then py.tasks.relax with XTBBBackend and/or DFTBPlusBackend.

Usage:
    python relax_dimer.py --mol data/xyz/H2O.xyz --backend xtb --outdir tmp/H2O_dimer_xtb
    python relax_dimer.py --mol data/xyz/H2O.xyz --backend dftb --sk-set mio/mio-1-1 --outdir tmp/H2O_dimer_dftb
    python relax_dimer.py --mol data/xyz/HCOOH.xyz --mol2 data/xyz/NH3.xyz --backend xtb --outdir tmp/mixed_dimer
    python relax_dimer.py --mol data/xyz/H2O.xyz --backend both --outdir tmp/H2O_dimer
"""

import os
import sys
import time
import argparse

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from py.geom_engine import build_hbond_dimer
from py.tasks.relax import relax


def _default_sk_path(sk_set):
    from py import config_loader as cfg
    sk_dir = cfg.require_path('sk_dir')
    return os.path.join(sk_dir, sk_set)


def _relax_xtb(dimer, outdir, method, n_threads, fmax, maxsteps):
    from py.interfaces.xtb import XTBBBackend
    os.makedirs(outdir, exist_ok=True)
    backend = XTBBBackend(method=method, n_threads=n_threads)
    t0 = time.time()
    result = relax(dimer, backend=backend, method=method, mode='local', outdir=outdir, fmax=fmax, maxsteps=maxsteps)
    wall = time.time() - t0
    result.geom.qs = result.geom.Rs = None
    out_xyz = os.path.join(outdir, 'relaxed.xyz')
    result.geom.saveXYZ(out_xyz, bQs=False)
    print(f"xTB relax done  walltime={wall:.1f}s  -> {out_xyz}")
    return result


def _relax_dftb(dimer, outdir, sk_path, method, fmax, maxsteps):
    from py.interfaces.dftbplus import DFTBPlusBackend
    from py import config_loader as cfg
    os.makedirs(outdir, exist_ok=True)
    temp_K = cfg.get('qc_defaults.dftb_temperature_K', default=300.0)
    backend = DFTBPlusBackend(sk_path=sk_path, method=method, temperature=float(temp_K))
    t0 = time.time()
    result = relax(dimer, backend=backend, method=method, mode='local', outdir=outdir, fmax=fmax, maxsteps=maxsteps)
    wall = time.time() - t0
    result.geom.qs = result.geom.Rs = None
    out_xyz = os.path.join(outdir, 'relaxed.xyz')
    result.geom.saveXYZ(out_xyz, bQs=False)
    print(f"DFTB+ relax done  walltime={wall:.1f}s  -> {out_xyz}")
    return result


def main():
    parser = argparse.ArgumentParser(description='Build and relax H-bonded dimers (e-pair oriented)')
    parser.add_argument('--mol', required=True, help='Monomer XYZ (acceptor side); homodimer if --mol2 omitted')
    parser.add_argument('--mol2', default=None, help='Second monomer XYZ for heterodimer')
    parser.add_argument('--host', default=None, help='Host element for lone-pair frame (default: first O then N)')
    parser.add_argument('--separation', type=float, default=2.9, help='Initial monomer B shift along axis (Å)')
    parser.add_argument('--axis', type=float, nargs=3, default=(0.0, 0.0, 1.0), metavar=('X', 'Y', 'Z'), help='H-bond axis')
    parser.add_argument('--backend', choices=['xtb', 'dftb', 'both'], default='xtb')
    parser.add_argument('--method-xtb', default='GFN2-xTB', help='xTB method')
    parser.add_argument('--method-dftb', default='D3', help='DFTB+ dispersion suffix (D3, D3H5, or empty)')
    parser.add_argument('--sk-set', default='mio/mio-1-1', help='SK set under sk_dir (e.g. mio/mio-1-1, auorg/auorg-1-1)')
    parser.add_argument('--sk-path', default=None, help='Full SK path (overrides --sk-set)')
    parser.add_argument('--outdir', default='tmp/hbond_dimer', help='Output directory')
    parser.add_argument('--n-threads', type=int, default=None, help='xTB threads (default: from machine_config)')
    parser.add_argument('--fmax', type=float, default=0.01, help='Force convergence threshold (eV/Å)')
    parser.add_argument('--maxsteps', type=int, default=500, help='Max optimizer steps')
    parser.add_argument('--build-only', action='store_true', help='Write start geometry only, skip relax')
    args = parser.parse_args()

    if not os.path.isfile(args.mol):
        raise FileNotFoundError(f"Monomer XYZ not found: {args.mol}")
    if args.mol2 is not None and not os.path.isfile(args.mol2):
        raise FileNotFoundError(f"Second monomer XYZ not found: {args.mol2}")

    dimer = build_hbond_dimer(args.mol, mol2_xyz=args.mol2, host=args.host, separation=args.separation, axis=tuple(args.axis))
    os.makedirs(args.outdir, exist_ok=True)
    start_xyz = os.path.join(args.outdir, 'start.xyz')
    dimer.saveXYZ(start_xyz, bQs=False)
    print(f"Built dimer: natoms={dimer.natoms}  host={args.host or 'auto(O,N)'}  sep={args.separation} Å  -> {start_xyz}")

    if args.build_only:
        return

    n_threads = args.n_threads
    if n_threads is None:
        from py import config_loader as cfg
        n_threads = int(cfg.get('qc_defaults.xtb_threads', default=4))

    if args.backend in ('xtb', 'both'):
        xtb_dir = args.outdir if args.backend == 'xtb' else os.path.join(args.outdir, 'xtb')
        _relax_xtb(dimer, xtb_dir, args.method_xtb, n_threads, args.fmax, args.maxsteps)

    if args.backend in ('dftb', 'both'):
        sk_path = args.sk_path or _default_sk_path(args.sk_set)
        dftb_dir = args.outdir if args.backend == 'dftb' else os.path.join(args.outdir, 'dftb')
        _relax_dftb(dimer, dftb_dir, sk_path, args.method_dftb, args.fmax, args.maxsteps)


if __name__ == '__main__':
    main()
