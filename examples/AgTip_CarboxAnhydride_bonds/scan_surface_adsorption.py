#!/usr/bin/env python3
"""
scan_surface_adsorption.py — rigid adsorption-energy scan for molecule on M(111)+adatom.

For each method's relaxed geometry, shift the molecule rigidly along the
adatom → host_atom (N or O) bond direction and evaluate E(r).
Reference energy subtracted at r_inf = 20.0 Å.

Usage:
    python scan_surface_adsorption.py --metal Au --molecule CH2O_ep
"""

import os, sys, argparse, time, re
import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO  = os.path.dirname(os.path.dirname(_HERE))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from py import atomicUtils as au
from py.AtomicSystem import AtomicSystem
from py.interfaces.xtb import XTBBBackend
from py.interfaces.dftbplus import DFTBPlusBackend
from py.tasks.scan import make_scan_grid, make_rigid_shift_frames, rigid_scan


def load_gen_with_cell(gen_path):
    """Load DFTB+ geo_end.gen into AtomicSystem."""
    with open(gen_path) as f:
        lines = f.readlines()
    parts = lines[0].strip().split()
    natoms = int(parts[0])
    unique_es = lines[1].strip().split()
    apos = []
    es = []
    for i, line in enumerate(lines[2:2+natoms]):
        parts = line.strip().split()
        elem_idx = int(parts[1]) - 1
        es.append(unique_es[elem_idx])
        apos.append([float(parts[2]), float(parts[3]), float(parts[4])])
    
    # Cell from line after atoms
    lvec = None
    cell_line = lines[2+natoms].strip() if len(lines) > 2+natoms else ''
    if cell_line and cell_line[0].isdigit():
        cell_parts = cell_line.split()
        if len(cell_parts) >= 9:
            lvec = np.array([float(x) for x in cell_parts[:9]]).reshape(3, 3)
    
    mol = AtomicSystem()
    mol.apos = np.array(apos)
    mol.enames = es
    mol.natoms = len(es)
    mol.lvec = lvec
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


def plot_scans(all_results, metal, molecule, outfile):
    """Plot E_bind(r) curves for all methods."""
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
        ax.set_xlabel(f'{metal}-host distance (Å)', fontsize=12)
        ax.set_ylabel('E_bind (eV)', fontsize=12)
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3)
        ax.set_xlim(left=1.4)

    axes[0].set_title('Full range', fontsize=11)
    all_E = np.concatenate([E[:-1][~np.isnan(E[:-1])] for _, _, E in all_results])
    if len(all_E) > 0:
        E_min = np.nanmin(all_E)
        axes[1].set_ylim(min(E_min * 1.5, -0.3), 0.5)
    axes[1].set_title('Well region (zoomed)', fontsize=11)

    fig.suptitle(f'Rigid adsorption scan — {molecule} / {metal}(111)+adatom', fontsize=13)
    fig.tight_layout()
    fig.savefig(outfile, dpi=150)
    print(f"  Saved plot: {outfile}")


def get_host_elem(molecule_name):
    """Determine host atom element (N or O) from molecule name."""
    if 'O' in molecule_name or 'H2O' in molecule_name or 'CH2O' in molecule_name:
        return 'O'
    return 'N'


def find_adatom_index(geom, metal):
    """Find the adatom index (last metal atom before molecule atoms)."""
    # Molecule atoms are C, H, N, O; surface + adatom are metal
    # Adatom is the last metal atom in the list
    last_metal = None
    for i, e in enumerate(geom.enames):
        if e == metal:
            last_metal = i
    if last_metal is None:
        raise ValueError(f"No {metal} atoms found in geometry")
    return last_metal


def make_backends_for_metal(metal):
    """Return list of (label, relax_dir, backend_factory) for given metal."""
    backends = []
    
    # GFN1-xTB (available for all metals)
    backends.append(('GFN1-xTB', f'tmp/relax_xtb_GFN1/{metal}',
                     DFTBPlusBackend(method='GFN1-xTB', kpts=None)))
    
    # GFN2-xTB (available for Au and Cu)
    if metal in ('Au', 'Cu'):
        backends.append(('GFN2-xTB', f'tmp/relax_xtb_GFN2/{metal}',
                         DFTBPlusBackend(method='GFN2-xTB', kpts=None)))
    
    # auorg (only Au)
    if metal == 'Au':
        sk_path = '/home/prokop/SIMULATIONS/dftbplus/slakos/auorg/auorg-1-1'
        backends.append(('DFTB+/auorg', 'tmp/relax_auorg/Au',
                         DFTBPlusBackend(sk_path=sk_path, kpts=None)))
    
    return backends


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--metal',      required=True, help='Metal: Au, Ag, or Cu')
    parser.add_argument('--molecule',   required=True, help='Molecule name')
    parser.add_argument('--outdir',     default=None, help='Output directory')
    parser.add_argument('--r-start',    type=float, default=1.5)
    parser.add_argument('--r-fine-end', type=float, default=2.5)
    parser.add_argument('--dr-fine',    type=float, default=0.1)
    parser.add_argument('--r-coarse-end', type=float, default=6.0)
    parser.add_argument('--dr-coarse',  type=float, default=0.2)
    parser.add_argument('--r-inf',      type=float, default=20.0)
    args = parser.parse_args()

    outdir = args.outdir or f'tmp/scan_surface_{args.metal}_{args.molecule}'
    os.makedirs(outdir, exist_ok=True)

    # Build shared r-grid
    distances = make_scan_grid(
        r_start=args.r_start, r_fine_end=args.r_fine_end, dr_fine=args.dr_fine,
        r_coarse_end=args.r_coarse_end, dr_coarse=args.dr_coarse, r_inf=args.r_inf
    )
    print(f"Scan grid: {len(distances)} points  [{distances[0]:.2f} … {distances[-2]:.2f} + r_inf={distances[-1]:.1f}]")

    host_elem = get_host_elem(args.molecule)
    print(f"Host atom: {host_elem}")

    all_results = []
    configs = make_backends_for_metal(args.metal)

    for label, relax_dir, backend in configs:
        gen_path = os.path.join(REPO, relax_dir, args.molecule, 'geo_end.gen')
        if not os.path.exists(gen_path):
            print(f"\n[SKIP] {label}: {gen_path} not found")
            continue
        print(f"\n=== {label} ===")
        print(f"  Loading: {gen_path}")
        geom = load_gen_with_cell(gen_path)

        # Find adatom (last metal atom)
        i_fixed = find_adatom_index(geom, args.metal)
        
        # Find host atom (N or O in the molecule)
        # Look for host_elem in atoms after the adatom
        i_mobile = None
        for i in range(i_fixed + 1, len(geom.enames)):
            if geom.enames[i] == host_elem:
                i_mobile = i
                break
        if i_mobile is None:
            # Fallback: search all atoms
            for i, e in enumerate(geom.enames):
                if e == host_elem:
                    i_mobile = i
                    break
        if i_mobile is None:
            print(f"  [SKIP] host atom {host_elem} not found")
            continue

        r0 = np.linalg.norm(np.array(geom.apos[i_mobile]) - np.array(geom.apos[i_fixed]))
        print(f"  Bond: {args.metal}[{i_fixed}]—{host_elem}[{i_mobile}]  r0={r0:.3f} Å")

        # Mobile indices: all atoms after the adatom (molecule atoms)
        mobile_indices = list(range(i_fixed + 1, len(geom.enames)))
        print(f"  Mobile atoms: {len(mobile_indices)} (indices {i_fixed+1} … {len(geom.enames)-1})")

        # Build all frame geometries (rigid shift along bond direction)
        frames = make_rigid_shift_frames(
            geom, i_fixed=i_fixed, i_mobile=i_mobile,
            distances=distances, mobile_indices=mobile_indices
        )

        # Run single-point energies
        t0 = time.time()
        energies = []
        for j, (r, g) in enumerate(frames):
            try:
                E = backend.run_energy(g, method=backend.method)
                print(f"  r={r:.2f}  E={E:.4f} eV", flush=True)
            except Exception as exc:
                print(f"  r={r:.2f}  ERROR: {exc}")
                E = np.nan
            energies.append(E)
        energies = np.array(energies)
        walltime = time.time() - t0

        # Subtract reference at r_inf (last point)
        E_ref = energies[-1]
        if not np.isnan(E_ref):
            E_bind = energies - E_ref
        else:
            E_bind = energies
            print("  WARNING: reference energy NaN, cannot compute E_bind")

        print(f"  Done in {walltime:.1f}s  E_bind_min={np.nanmin(E_bind[:-1]):.4f} eV")

        # Save outputs
        safe_label = label.replace('/', '_').replace('+', 'plus')
        dat_path = os.path.join(outdir, f'scan_{args.molecule}_{args.metal}_{safe_label}.dat')
        xyz_path_out = os.path.join(outdir, f'scan_{args.molecule}_{args.metal}_{safe_label}.xyz')
        save_scan_dat(dat_path, distances, E_bind, label=label)
        save_scan_xyz(xyz_path_out, frames, E_bind)
        print(f"  Saved: {dat_path}")
        print(f"  Saved: {xyz_path_out}")

        all_results.append((label, distances, E_bind))

    # Combined plot
    if all_results:
        plot_path = os.path.join(outdir, f'scan_{args.molecule}_{args.metal}_all_methods.png')
        plot_scans(all_results, args.metal, args.molecule, plot_path)

    # Summary table
    print("\n=== SUMMARY ===")
    print(f"{'Method':20s}  {'E_min(eV)':>10s}  {'r_min(A)':>8s}")
    for label, dists, E_bind in all_results:
        valid = ~np.isnan(E_bind[:-1])
        if valid.any():
            idx = np.nanargmin(E_bind[:-1])
            print(f"{label:20s}  {E_bind[idx]:10.4f}  {dists[idx]:8.3f}")


if __name__ == '__main__':
    main()
