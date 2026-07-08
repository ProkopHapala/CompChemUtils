#!/usr/bin/env python3
"""
scan_dimer.py — rigid O···O (or host-host) distance scan from a relaxed dimer geometry.

Translates the donor monomer rigidly along the acceptor→donor axis; energies vs separation.
Grid: 0.1 Å near r_eq, geometric coarsening (0.2, 0.4, … per 1 Å band), 1 Å steps from 6 Å,
5 Å steps from 15 Å to r_max (default 20 Å).

Usage:
    python scan_dimer.py --geom tmp/H2O_dimer_xtb/relaxed.xyz --backend xtb --outdir tmp/H2O_dimer_scan_xtb
    python scan_dimer.py --geom tmp/H2O_dimer_dftb/relaxed.xyz --backend dftb --method-dftb none --outdir tmp/H2O_dimer_scan_dftb
"""

import os
import sys
import time
import argparse
import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from py.AtomicSystem import AtomicSystem
from py.tasks.scan import make_scan_grid_geometric, make_rigid_shift_frames, rigid_scan


def _default_sk_path(sk_set):
    from py import config_loader as cfg
    return os.path.join(cfg.require_path('sk_dir'), sk_set)


def _dimer_indices(geom, n_acceptor=None):
    """Return (i_O_acc, i_O_don, acc_indices, don_indices) for homodimer or half-split."""
    O_idx = [i for i, e in enumerate(geom.enames) if e in ('O', 'N')]
    if len(O_idx) < 2:
        raise ValueError(f"Need >=2 O/N host atoms for dimer scan; found {O_idx}")
    i_acc, i_don = O_idx[0], O_idx[1]
    if n_acceptor is None:
        n_acceptor = i_don
    acc = list(range(n_acceptor))
    don = list(range(n_acceptor, len(geom.enames)))
    return i_acc, i_don, acc, don


def _save_scan_xyz(fname, frames, energies):
    with open(fname, 'w') as f:
        for (r, geom), E in zip(frames, energies):
            f.write(f"{len(geom.enames)}\n")
            f.write(f"r={r:.4f} E={E:.8f} eV\n")
            for e, p in zip(geom.enames, geom.apos):
                f.write(f"{e}  {p[0]:.10f}  {p[1]:.10f}  {p[2]:.10f}\n")


def _save_scan_dat(fname, distances, energies, E_bind, label=''):
    with open(fname, 'w') as f:
        f.write(f"# Rigid dimer scan  method={label}\n")
        f.write("# r(A)   E_tot(eV)   E_bind(eV)\n")
        for r, E, Eb in zip(distances, energies, E_bind):
            f.write(f"{r:.4f}  {E:.8f}  {Eb:.8f}\n")


def _plot_scan(outfile, distances, E_bind, label, r_eq):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    x = np.asarray(distances); y = np.asarray(E_bind)
    Emin = float(np.nanmin(y))
    vmin = Emin * 1.2
    vmax = -vmin * 2.0
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.plot(x, y, '.-', color='blue', lw=0.5, ms=3, label=label)
    ax.axhline(0, color='gray', lw=0.5, ls='--', alpha=0.5)
    if np.any(np.isfinite(y)):
        i = int(np.nanargmin(y))
        ax.axvline(x[i], color='blue', ls='--', lw=0.5, alpha=0.4)
    ax.set_xlim(left=max(0, float(x.min()) - 0.2))
    ax.set_ylim(vmin, vmax)
    ax.set_xlabel('O···O distance (Å)')
    ax.set_ylabel('E_bind (eV)')
    ax.set_title(f'Rigid H-bond scan — {label}')
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(outfile, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"  Saved plot: {outfile}  y=[{vmin:.4f}, {vmax:.4f}] eV")


def main():
    parser = argparse.ArgumentParser(description='Rigid dimer distance scan from relaxed geometry')
    parser.add_argument('--geom', required=True, help='Relaxed dimer XYZ')
    parser.add_argument('--backend', choices=['xtb', 'dftb'], default='xtb')
    parser.add_argument('--method-xtb', default='GFN2-xTB')
    parser.add_argument('--method-dftb', default='D3', help='D3, D3H5, none/empty for plain SCC-DFTB')
    parser.add_argument('--sk-set', default='mio/mio-1-1')
    parser.add_argument('--sk-path', default=None)
    parser.add_argument('--outdir', default='tmp/hbond_dimer_scan')
    parser.add_argument('--n-acceptor', type=int, default=None, help='Atoms in acceptor monomer (default: first donor O index)')
    parser.add_argument('--r-max', type=float, default=20.0)
    parser.add_argument('--dr-fine', type=float, default=0.1)
    parser.add_argument('--fine-half-width', type=float, default=1.0, help='±(this) Å around r_eq at dr_fine')
    parser.add_argument('--r-min', type=float, default=None)
    parser.add_argument('--n-threads', type=int, default=None)
    parser.add_argument('--export-only', action='store_true', help='Write scan.xyz grid only, no energies')
    args = parser.parse_args()

    if not os.path.isfile(args.geom):
        raise FileNotFoundError(args.geom)

    geom = AtomicSystem(fname=args.geom)
    geom.qs = geom.Rs = None
    i_acc, i_don, acc_idx, don_idx = _dimer_indices(geom, n_acceptor=args.n_acceptor)
    r_eq = float(np.linalg.norm(geom.apos[i_don] - geom.apos[i_acc]))
    print(f"Loaded {args.geom}  natoms={geom.natoms}  r_eq(O···O)={r_eq:.4f} Å")
    print(f"  acceptor O={i_acc} atoms={acc_idx}  donor O={i_don} atoms={don_idx}")

    distances = make_scan_grid_geometric(
        r_eq, r_min=args.r_min, r_max=args.r_max, dr_fine=args.dr_fine,
        fine_half_width=args.fine_half_width,
    )
    print(f"Scan grid: {len(distances)} points  [{distances[0]:.2f} … {distances[-1]:.1f} Å]")
    print(f"  steps: {np.diff(distances)[:8]} … {np.diff(distances)[-3:]}")

    frames = make_rigid_shift_frames(
        geom, i_fixed=i_acc, i_mobile=i_don, distances=distances,
        mobile_indices=don_idx,
    )

    os.makedirs(args.outdir, exist_ok=True)
    _save_scan_xyz(os.path.join(args.outdir, 'scan.xyz'), frames, [np.nan] * len(frames))
    np.savetxt(os.path.join(args.outdir, 'distances.dat'), distances, header='r_OO_A')

    if args.export_only:
        print(f"Wrote grid only -> {args.outdir}/scan.xyz")
        return

    if args.backend == 'xtb':
        from py.interfaces.xtb import XTBBBackend
        n_threads = args.n_threads
        if n_threads is None:
            from py import config_loader as cfg
            n_threads = int(cfg.get('qc_defaults.xtb_threads', default=4))
        backend = XTBBBackend(method=args.method_xtb, n_threads=n_threads)
        method = args.method_xtb
    else:
        from py.interfaces.dftbplus import DFTBPlusBackend
        from py import config_loader as cfg
        sk = args.sk_path or _default_sk_path(args.sk_set)
        m = (args.method_dftb or '').strip()
        if m.lower() in ('none', 'no', ''):
            m = ''
        backend = DFTBPlusBackend(sk_path=sk, method=m or None, temperature=float(cfg.get('qc_defaults.dftb_temperature_K', default=300.0)))
        method = m

    t0 = time.time()
    result = rigid_scan(frames, backend=backend, method=method, mode='local', outdir=args.outdir)
    wall = time.time() - t0
    print(f"Scan done  {len(result.coords)} points  walltime={wall:.1f}s")

    E_ref = float(result.energies[-1])
    E_bind = result.energies - E_ref
    label = f"{args.backend}:{method or 'SCC-DFTB'}"
    _save_scan_xyz(os.path.join(args.outdir, 'scan_out.xyz'), frames, result.energies)
    _save_scan_dat(os.path.join(args.outdir, 'scan.dat'), result.coords, result.energies, E_bind, label=label)
    _plot_scan(os.path.join(args.outdir, 'scan.png'), result.coords, E_bind, label, r_eq)
    i_min = int(np.nanargmin(E_bind))
    print(f"  E_bind min: {E_bind[i_min]:.4f} eV at r={result.coords[i_min]:.4f} Å  (r_eq={r_eq:.4f})")


if __name__ == '__main__':
    main()
