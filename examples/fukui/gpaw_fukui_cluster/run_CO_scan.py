#!/usr/bin/env python3
"""GPAW rigid-scan interaction energy: CO molecule over selected atoms.

For each selected atom in a molecule, places CO at a series of distances
perpendicular to the molecular plane (z-direction) and computes:
  E_int(r) = E_total(r) - E_mol - E_CO

Uses GPAW restart from previous frame to speed up SCF convergence.
PBE + plane-wave mode. Gamma-point only (isolated molecules in vacuum).

Usage:
    # Quick local test with C2H4
    python run_CO_scan.py --mol C2H4 --ecut 200 --vacuum 8.0

    # Production
    python run_CO_scan.py --mol pyridine --ecut 500 --vacuum 12.0

    # Batch all molecules
    python run_CO_scan.py --batch --ecut 500 --vacuum 12.0

Results: results/CO_scan_<mol>_PBE_<ecut>eV/
"""

import os, sys, argparse
import numpy as np

B2A = 0.529177210903

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GEOM_DIR = os.path.join(SCRIPT_DIR, 'geometries')
OUT_DIR = os.path.join(SCRIPT_DIR, 'results')

# Non-equivalent atoms selected by symmetry (0-indexed)
# See plot_selected_atoms.py for visual confirmation
SELECTED = {
    'C2H4':      {'indices': [0],       'labels': ['C1']},
    'CH2O':      {'indices': [0, 1],    'labels': ['C1', 'O1']},
    'CH2NH':     {'indices': [0, 1],    'labels': ['C1', 'N1']},
    'H2O':       {'indices': [0],       'labels': ['O1']},
    'pyridine':  {'indices': [0, 1, 3], 'labels': ['N', 'Cα', 'Cpara']},
    'pyrrol':    {'indices': [0, 2],    'labels': ['Cα', 'N']},
    'pentacene': {'indices': [0, 6, 10],'labels': ['C_term', 'C_junct', 'C_center']},
    'PTCDA':     {'indices': [3, 14, 24], 'labels': ['C_core', 'C_bay', 'O_anhyd']},
}

# CO bond length (Å) — experimental gas-phase
R_CO = 1.128


def read_xyz(fname):
    with open(fname) as f:
        lines = f.readlines()
    natm = int(lines[0].strip())
    syms, ps = [], []
    for i in range(2, 2 + natm):
        parts = lines[i].split()
        syms.append(parts[0])
        ps.append([float(parts[1]), float(parts[2]), float(parts[3])])
    return syms, np.array(ps)


def make_scan_grid(r_start=2.0, r_fine_end=3.0, dr_fine=0.1,
                   r_coarse_end=6.0, dr_coarse=0.25, r_inf=15.0):
    """Non-uniform distance grid: fine near contact, coarse further out, + r_inf."""
    r_fine   = np.arange(r_start, r_fine_end + 1e-9, dr_fine)
    r_coarse = np.arange(r_fine_end + dr_coarse, r_coarse_end + 1e-9, dr_coarse)
    return np.concatenate([r_fine, r_coarse, [r_inf]])


def box_positions(ps, extra_atoms_ps, vacuum):
    """Center all atoms (molecule + CO) in a cell with vacuum padding.
    Returns (all_ps_shifted, cell) where all_ps_shifted includes both sets."""
    all_ps = np.vstack([ps, extra_atoms_ps])
    rmin = all_ps.min(axis=0)
    rmax = all_ps.max(axis=0)
    extent = rmax - rmin
    cell = extent + 2 * vacuum
    shift = 0.5 * cell - 0.5 * (rmin + rmax)
    return all_ps + shift, cell


def make_co_atoms(atom_pos, r, direction='z'):
    """Place CO molecule at distance r above atom_pos along direction.
    CO oriented with C closer to the surface (C-down).
    Returns positions of [C, O] in the full system."""
    if direction == 'z':
        d = np.array([0.0, 0.0, 1.0])
    else:
        d = np.array(direction, dtype=float)
        d /= np.linalg.norm(d)
    c_pos = atom_pos + d * r
    o_pos = c_pos + d * R_CO
    return c_pos, o_pos


def run_scan_for_atom(mol_name, mol_syms, mol_ps, atom_idx, atom_label,
                      ecut, vacuum, xc, outdir, r_grid):
    """Run rigid scan of CO over one selected atom. Uses GPAW restart."""
    from ase import Atoms
    from gpaw import GPAW, PW, FermiDirac, restart as gpaw_restart

    os.makedirs(outdir, exist_ok=True)
    tag = f"{mol_name}_atom{atom_idx}_{atom_label}"

    # --- 1. Single-point energy of isolated molecule ---
    all_boxed, mol_cell = box_positions(mol_ps, mol_ps[:1], vacuum)  # mol_ps[:1] just for extent
    mol_boxed = all_boxed[:len(mol_ps)]
    mol_atoms = Atoms(symbols=mol_syms, positions=mol_boxed, cell=mol_cell, pbc=True)

    mol_calc = GPAW(mode=PW(ecut), xc=xc, charge=0, spinpol=False,
                    occupations=FermiDirac(0.05), kpts=(1, 1, 1), symmetry='off',
                    convergence=dict(energy=1e-5, density=1e-5, bands='occupied'),
                    txt=os.path.join(outdir, f'{tag}_mol.txt'))
    mol_atoms.calc = mol_calc
    E_mol = mol_atoms.get_potential_energy()
    print(f"  [{tag}] E_mol = {E_mol:.6f} eV")

    # --- 2. Single-point energy of isolated CO ---
    # Place CO in same-sized cell, centered
    co_center = 0.5 * mol_cell
    co_atoms_iso = Atoms(symbols=['C', 'O'],
                         positions=[co_center - np.array([0, 0, R_CO / 2]),
                                    co_center + np.array([0, 0, R_CO / 2])],
                         cell=mol_cell, pbc=True)
    co_calc = GPAW(mode=PW(ecut), xc=xc, charge=0, spinpol=False,
                   occupations=FermiDirac(0.05), kpts=(1, 1, 1), symmetry='off',
                   convergence=dict(energy=1e-5, density=1e-5, bands='occupied'),
                   txt=os.path.join(outdir, f'{tag}_CO.txt'))
    co_atoms_iso.calc = co_calc
    E_CO = co_atoms_iso.get_potential_energy()
    print(f"  [{tag}] E_CO  = {E_CO:.6f} eV")

    # --- 3. Scan: CO at distance r above selected atom ---
    energies = []
    restart_file = os.path.join(outdir, f'{tag}_restart.gpw')

    for ir, r in enumerate(r_grid):
        # Build combined system: molecule + CO
        all_syms = list(mol_syms) + ['C', 'O']
        c_pos, o_pos = make_co_atoms(mol_ps[atom_idx], r, direction='z')
        all_boxed, all_cell = box_positions(mol_ps, np.array([c_pos, o_pos]), vacuum)

        # Split boxed positions back into molecule and CO parts
        n_mol = len(mol_syms)
        combined = Atoms(symbols=all_syms, positions=all_boxed,
                         cell=all_cell, pbc=True)

        # Use restart from previous frame if available (speeds up SCF)
        if ir > 0 and os.path.isfile(restart_file):
            prev_atoms, calc = gpaw_restart(restart_file,
                                            txt=os.path.join(outdir, f'{tag}_r{r:.2f}.txt'))
            # Update positions for this frame (same cell, same atoms, new positions)
            prev_atoms.positions = all_boxed
            prev_atoms.calc = calc
            combined = prev_atoms
        else:
            calc = GPAW(mode=PW(ecut), xc=xc, charge=0, spinpol=False,
                        occupations=FermiDirac(0.05), kpts=(1, 1, 1), symmetry='off',
                        convergence=dict(energy=1e-5, density=1e-5, bands='occupied'),
                        txt=os.path.join(outdir, f'{tag}_r{r:.2f}.txt'))
            combined.calc = calc
        E = combined.get_potential_energy()
        E_int = E - E_mol - E_CO
        energies.append(E_int)
        print(f"  [{tag}] r={r:6.2f}  E_tot={E:12.6f}  E_int={E_int:12.6f} eV")

        # Save restart for next frame
        calc.write(restart_file, mode='all')

    energies = np.array(energies)

    # --- 4. Save results ---
    dat_file = os.path.join(outdir, f'{tag}_scan.dat')
    with open(dat_file, 'w') as f:
        f.write(f"# CO rigid scan over {mol_name} atom {atom_idx} ({atom_label})\n")
        f.write(f"# Method: GPAW {xc} PW({int(ecut)}eV) vacuum={vacuum}A\n")
        f.write(f"# E_mol = {E_mol:.6f} eV, E_CO = {E_CO:.6f} eV\n")
        f.write("# r(A)    E_int(eV)\n")
        for r, E in zip(r_grid, energies):
            f.write(f"{r:.4f}  {E:.8f}\n")
    print(f"  [{tag}] Saved: {dat_file}")

    return r_grid, energies, E_mol, E_CO


def plot_scan(mol_name, atom_label, r_grid, energies, outdir):
    """Plot E_int vs r for one scan."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 5))
    r_plot = r_grid[:-1] if r_grid[-1] > 10 else r_grid  # skip r_inf in plot
    E_plot = energies[:-1] if r_grid[-1] > 10 else energies

    ax.plot(r_plot, E_plot, 'o-', color='#1f77b4', lw=2, ms=6)
    ax.axhline(0, color='gray', ls='--', lw=0.7)
    ax.set_xlabel('r (CO–atom distance, Å)', fontsize=12)
    ax.set_ylabel('E_int (eV)', fontsize=12)
    ax.set_title(f'CO over {mol_name} / {atom_label}', fontsize=12)
    ax.grid(True, alpha=0.3)

    if np.any(np.isfinite(E_plot)):
        i_min = np.nanargmin(E_plot)
        ax.annotate(f'min: r={r_plot[i_min]:.2f}, E={E_plot[i_min]:.3f} eV',
                    xy=(r_plot[i_min], E_plot[i_min]),
                    xytext=(r_plot[i_min] + 0.5, E_plot[i_min] + 0.1),
                    arrowprops=dict(arrowstyle='->', color='red'),
                    fontsize=9, color='red')

    fig.tight_layout()
    outfile = os.path.join(outdir, f'{mol_name}_atom_{atom_label}_scan.png')
    fig.savefig(outfile, dpi=150)
    plt.close(fig)
    print(f"  Plot: {outfile}")


def run_molecule(mol_name, ecut, vacuum, xc, r_grid=None):
    """Run CO scan over all selected atoms for one molecule."""
    xyz_path = os.path.join(GEOM_DIR, f'{mol_name}.xyz')
    if not os.path.isfile(xyz_path):
        print(f"ERROR: {xyz_path} not found")
        sys.exit(1)

    syms, ps = read_xyz(xyz_path)
    sel = SELECTED.get(mol_name)
    if sel is None:
        print(f"ERROR: no selected atoms for {mol_name}")
        sys.exit(1)

    if r_grid is None:
        r_grid = make_scan_grid()

    outdir = os.path.join(OUT_DIR, f'CO_scan_{mol_name}_{xc}_{int(ecut)}eV')
    os.makedirs(outdir, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"  CO rigid scan: {mol_name}")
    print(f"  Method: GPAW {xc} PW({int(ecut)}eV) vacuum={vacuum}A")
    print(f"  Selected atoms: {sel['labels']}  indices={sel['indices']}")
    print(f"  Grid: {len(r_grid)} points, r=[{r_grid[0]:.2f}..{r_grid[-1]:.2f}] A")
    print(f"{'='*60}")

    all_results = {}
    for idx, label in zip(sel['indices'], sel['labels']):
        print(f"\n  --- Scanning over atom {idx} ({label}) ---")
        r_arr, E_arr, E_mol, E_CO = run_scan_for_atom(
            mol_name, syms, ps, idx, label, ecut, vacuum, xc, outdir, r_grid)
        plot_scan(mol_name, label, r_arr, E_arr, outdir)
        all_results[label] = (r_arr, E_arr)

    # Combined plot for all atoms in this molecule
    if len(all_results) > 1:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(9, 6))
        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']
        for i, (label, (r_arr, E_arr)) in enumerate(all_results.items()):
            r_plot = r_arr[:-1] if r_arr[-1] > 10 else r_arr
            E_plot = E_arr[:-1] if r_arr[-1] > 10 else E_arr
            ax.plot(r_plot, E_plot, 'o-', color=colors[i % 4], lw=2, ms=5, label=label)
        ax.axhline(0, color='gray', ls='--', lw=0.7)
        ax.set_xlabel('r (Å)', fontsize=12)
        ax.set_ylabel('E_int (eV)', fontsize=12)
        ax.set_title(f'CO scan over {mol_name} — all selected atoms', fontsize=12)
        ax.legend(fontsize=10)
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        combined_file = os.path.join(outdir, f'{mol_name}_all_atoms_scan.png')
        fig.savefig(combined_file, dpi=150)
        plt.close(fig)
        print(f"\n  Combined plot: {combined_file}")

    # Summary
    summary_file = os.path.join(outdir, 'summary.txt')
    with open(summary_file, 'w') as f:
        f.write(f"CO rigid scan over {mol_name}\n")
        f.write(f"Method: GPAW {xc} PW({int(ecut)}eV) vacuum={vacuum}A\n")
        f.write(f"CO bond length: {R_CO} A\n")
        f.write(f"Grid: {len(r_grid)} points\n\n")
        for label, (r_arr, E_arr) in all_results.items():
            i_min = np.nanargmin(E_arr[:-1]) if r_arr[-1] > 10 else np.nanargmin(E_arr)
            r_min = r_arr[i_min]
            E_min = E_arr[i_min]
            f.write(f"  {label:12s}: E_min = {E_min:.4f} eV at r = {r_min:.2f} A\n")
    print(f"\n  Summary: {summary_file}")
    return outdir


def main():
    parser = argparse.ArgumentParser(description='GPAW CO rigid scan over selected atoms')
    parser.add_argument('--mol', type=str, default=None, help='Molecule name')
    parser.add_argument('--batch', action='store_true', help='Run all molecules')
    parser.add_argument('--ecut', type=float, default=500.0, help='PW cutoff (eV)')
    parser.add_argument('--vacuum', type=float, default=12.0, help='Vacuum (Å)')
    parser.add_argument('--xc', type=str, default='PBE')
    parser.add_argument('--r-start', type=float, default=2.0)
    parser.add_argument('--r-fine-end', type=float, default=3.0)
    parser.add_argument('--dr-fine', type=float, default=0.1)
    parser.add_argument('--r-coarse-end', type=float, default=6.0)
    parser.add_argument('--dr-coarse', type=float, default=0.25)
    parser.add_argument('--r-inf', type=float, default=15.0)
    args = parser.parse_args()

    if args.batch:
        mols = list(SELECTED.keys())
    elif args.mol:
        mols = [args.mol]
    else:
        parser.error('Specify --mol <name> or --batch')

    r_grid = make_scan_grid(args.r_start, args.r_fine_end, args.dr_fine,
                            args.r_coarse_end, args.dr_coarse, args.r_inf)

    print(f"Scan grid: {r_grid}")

    for mol in mols:
        run_molecule(mol, args.ecut, args.vacuum, args.xc, r_grid)

    print(f"\n{'='*60}")
    print(f"  All done. Results in: {OUT_DIR}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
