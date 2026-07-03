#!/usr/bin/env python3
"""
scan_adsorption.py — rigid adsorption-energy scan for molecule+Au4 clusters.

For each method's relaxed geometry, shift the molecule rigidly along the
Au_apex → O bond direction and evaluate E(r).  All methods share the same
r-grid.  Outputs: per-method .dat + .xyz, and a combined PNG plot.

Usage:
    python scan_adsorption.py [--molecule CH2O_ep] [--outdir tmp/scan_CH2O]
"""

import os, sys, argparse, time
import numpy as np

# sys.path for py.* imports (py package lives at CompChemUtils/py, accessible via site-packages or local install)
_HERE = os.path.dirname(os.path.abspath(__file__))
REPO  = os.path.dirname(os.path.dirname(_HERE))  # CompChemUtils/
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from py import atomicUtils as au
from py.AtomicSystem import AtomicSystem
from py.interfaces.xtb import XTBBBackend
from py.interfaces.dftbplus import DFTBPlusBackend
from py.tasks.scan import make_scan_grid, make_rigid_shift_frames, rigid_scan


# ---- method configs: (label, relax_dir, backend_factory)
SK_PATH = '/home/prokop/SIMULATIONS/dftbplus/slakos/auorg/auorg-1-1'

def make_backends():
    return [
        ('GFN1-xTB',   'tmp/relax_xtb_au_gfn1_tight',  XTBBBackend(method='GFN1-xTB')),
        ('GFN2-xTB',   'tmp/relax_xtb_au_gfn2_tight',  XTBBBackend(method='GFN2-xTB')),
        ('g-xTB',      'tmp/relax_xtb_au_gxtb_tight',  XTBBBackend(method='g-xTB')),
        ('DFTB+/auorg','tmp/relax_dftb_auorg_tight',    DFTBPlusBackend(sk_path=SK_PATH, method=None)),
    ]


def load_geom(xyz_path):
    """Load first frame of XYZ into AtomicSystem."""
    frames = au.load_xyz_movie(xyz_path)
    es, apos, qs, Rs, comment = frames[0]
    mol = AtomicSystem()
    mol.apos   = apos
    mol.enames = list(es)
    mol.natoms = len(es)
    mol.qs     = None
    mol.Rs     = None
    return mol


def save_scan_xyz(fname, frames, energies):
    """Write XYZ movie with energy in comment line."""
    with open(fname, 'w') as f:
        for (r, geom), E in zip(frames, energies):
            es   = geom.enames
            apos = geom.apos
            f.write(f"{len(es)}\n")
            f.write(f"r={r:.4f} E={E:.6f} eV\n")
            for e, pos in zip(es, apos):
                f.write(f"{e}  {pos[0]:.10f}  {pos[1]:.10f}  {pos[2]:.10f}\n")


def save_scan_dat(fname, distances, energies, label=''):
    """Write two-column r/E text file."""
    with open(fname, 'w') as f:
        f.write(f"# Rigid adsorption scan  method={label}\n")
        f.write("# r(A)   E_bind(eV)\n")
        for r, E in zip(distances, energies):
            f.write(f"{r:.4f}  {E:.8f}\n")


def plot_scans(all_results, outfile):
    """Plot E_bind(r) curves for all methods — two panels: full range and zoomed well."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    linestyles = ['-', '--', '-.', ':']
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    for ax_idx, ax in enumerate(axes):
        for i, (label, distances, energies) in enumerate(all_results):
            d = distances[:-1]  # skip r_inf
            E = energies[:-1]
            valid = ~np.isnan(E)
            ax.plot(d[valid], E[valid], linestyles[i % 4], color=colors[i % 4],
                    label=label, linewidth=1.8)

        ax.axhline(0, color='gray', linewidth=0.7, linestyle='--')
        ax.set_xlabel('Au-O distance (Å)', fontsize=12)
        ax.set_ylabel('E_bind (eV)', fontsize=12)
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3)
        ax.set_xlim(left=1.4)

    # Right panel: zoom into the well (clip y-axis near zero)
    axes[0].set_title('Full range', fontsize=11)
    # Auto-detect a sensible y-limit for the well panel
    all_E = np.concatenate([E[:-1][~np.isnan(E[:-1])] for _, _, E in all_results])
    E_min = np.nanmin(all_E)
    axes[1].set_ylim(min(E_min * 1.5, -0.3), 0.5)
    axes[1].set_title('Well region (zoomed)', fontsize=11)

    mol_name = os.path.basename(os.path.dirname(outfile)).replace('scan_', '').replace('_fixed3', '').replace('_fixed2', '')
    fig.suptitle(f'Rigid adsorption scan — {mol_name} / Au₄', fontsize=13)
    fig.tight_layout()
    fig.savefig(outfile, dpi=150)
    print(f"  Saved plot: {outfile}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--molecule',   default='CH2O_ep', help='Molecule name (must match relaxed XYZ filenames)')
    parser.add_argument('--outdir',     default=None,       help='Output directory (default: tmp/scan_<molecule>)')
    parser.add_argument('--i-fixed',    type=int, default=0,  help='Index of fixed (anchor) atom, default 0 (apex Au)')
    parser.add_argument('--i-mobile',   type=int, default=None, help='Index of mobile atom defining bond (overrides --mobile-elem)')
    parser.add_argument('--fixed-elem', default='Au', help='Element name of the fixed cluster (default Au)')
    parser.add_argument('--mobile-elem', default=None, help='Element of the bond atom on the molecule (e.g. O, N). Auto: first non-fixed-elem atom.')
    parser.add_argument('--r-start',    type=float, default=1.5)
    parser.add_argument('--r-fine-end', type=float, default=2.5)
    parser.add_argument('--dr-fine',    type=float, default=0.1)
    parser.add_argument('--r-coarse-end', type=float, default=6.0)
    parser.add_argument('--dr-coarse',  type=float, default=0.2)
    parser.add_argument('--r-inf',      type=float, default=20.0)
    args = parser.parse_args()

    outdir = args.outdir or f'tmp/scan_{args.molecule}'
    os.makedirs(outdir, exist_ok=True)

    # Build shared r-grid
    distances = make_scan_grid(
        r_start=args.r_start, r_fine_end=args.r_fine_end, dr_fine=args.dr_fine,
        r_coarse_end=args.r_coarse_end, dr_coarse=args.dr_coarse, r_inf=args.r_inf
    )
    print(f"Scan grid: {len(distances)} points  [{distances[0]:.2f} … {distances[-2]:.2f} + r_inf={distances[-1]:.1f}]")

    all_results = []   # (label, distances, E_bind) for plotting
    configs = make_backends()

    for label, relax_dir, backend in configs:
        xyz_path = os.path.join(REPO, relax_dir, f'{args.molecule}_relaxed.xyz')
        if not os.path.exists(xyz_path):
            print(f"\n[SKIP] {label}: {xyz_path} not found")
            continue
        print(f"\n=== {label} ===")
        print(f"  Loading: {xyz_path}")
        geom = load_geom(xyz_path)

        # Detect i_mobile
        if args.i_mobile is not None:
            i_mobile = args.i_mobile
        elif args.mobile_elem is not None:
            i_mobile = next((i for i, e in enumerate(geom.enames) if e == args.mobile_elem), None)
            if i_mobile is None:
                print(f"  [SKIP] element {args.mobile_elem} not found in {xyz_path}")
                continue
        else:
            i_mobile = next(i for i, e in enumerate(geom.enames) if e != args.fixed_elem)

        r0 = np.linalg.norm(np.array(geom.apos[i_mobile]) - np.array(geom.apos[args.i_fixed]))
        mobile_elem = geom.enames[i_mobile]
        print(f"  Bond: Au[{args.i_fixed}]—{mobile_elem}[{i_mobile}]  r0={r0:.3f} Å")

        # Build all frame geometries (rigid shift along bond direction)
        frames = make_rigid_shift_frames(
            geom, i_fixed=args.i_fixed, i_mobile=i_mobile,
            distances=distances,
            mobile_indices=[i for i, e in enumerate(geom.enames) if e != args.fixed_elem]
        )

        # Run single-point energies
        t0 = time.time()
        energies = []
        for j, (r, g) in enumerate(frames):
            try:
                E = backend.run_energy(g)
                print(f"  r={r:.2f}  E={E:.4f} eV", flush=True)
            except Exception as exc:
                print(f"  r={r:.2f}  ERROR: {exc}")
                E = np.nan
            energies.append(E)
        energies = np.array(energies)
        walltime = time.time() - t0

        # Subtract reference: use energy at relaxed distance (r0) as reference
        # Find index closest to r0
        i_ref = np.argmin(np.abs(distances - r0))
        E_ref = energies[i_ref]
        if not np.isnan(E_ref):
            E_bind = energies - E_ref
        else:
            E_bind = energies
            print("  WARNING: reference energy NaN, cannot compute E_bind")

        print(f"  Done in {walltime:.1f}s  E_bind_min={np.nanmin(E_bind[:-1]):.4f} eV")

        # Save outputs
        safe_label = label.replace('/', '_').replace('+', 'plus')
        dat_path = os.path.join(outdir, f'scan_{args.molecule}_{safe_label}.dat')
        xyz_path_out = os.path.join(outdir, f'scan_{args.molecule}_{safe_label}.xyz')
        save_scan_dat(dat_path, distances, E_bind, label=label)
        save_scan_xyz(xyz_path_out, frames, E_bind)
        print(f"  Saved: {dat_path}")
        print(f"  Saved: {xyz_path_out}")

        all_results.append((label, distances, E_bind))

    # Combined plot
    if all_results:
        plot_path = os.path.join(outdir, f'scan_{args.molecule}_all_methods.png')
        plot_scans(all_results, plot_path)

    # Summary table
    print("\n=== SUMMARY ===")
    print(f"{'Method':20s}  {'E_min(eV)':>10s}  {'r_min(A)':>8s}  {'Wall(s)':>8s}")
    for label, dists, E_bind in all_results:
        valid = ~np.isnan(E_bind[:-1])
        if valid.any():
            idx = np.nanargmin(E_bind[:-1])
            print(f"{label:20s}  {E_bind[idx]:10.4f}  {dists[idx]:8.3f}")


if __name__ == '__main__':
    main()
