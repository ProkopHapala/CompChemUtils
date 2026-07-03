#!/usr/bin/env python3
"""Plot molecules with symmetry-inequivalent selected atoms highlighted.

Selects non-equivalent C, O, N atoms considering molecular symmetry,
and plots each molecule in the xy-plane with selected atoms marked.

Usage:
    python plot_selected_atoms.py
    python plot_selected_atoms.py --mol C2H4   # single molecule
"""
import os, sys, argparse
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GEOM_DIR = os.path.join(SCRIPT_DIR, 'geometries')
OUT_DIR = os.path.join(SCRIPT_DIR, 'plots')

ELEM_COLORS = {'H': '#cccccc', 'C': '#2b2b2b', 'N': '#3b6fdb', 'O': '#e03030'}
ELEM_SIZES  = {'H': 150, 'C': 300, 'N': 300, 'O': 300}
SELECT_COLOR = '#ffcc00'  # gold for selected atoms
SELECT_EDGE = '#ff0000'

# Manually curated non-equivalent atoms (0-indexed) considering molecular symmetry
# Format: {mol: {indices: [list], labels: [list], sym: 'point group'}}
SELECTED = {
    'C2H4': {
        'indices': [0],
        'labels': ['C1'],
        'sym': 'D2h',
        'note': '2 equivalent C (C2 axis); 4 equivalent H',
    },
    'CH2O': {
        'indices': [0, 1],
        'labels': ['C1', 'O1'],
        'sym': 'C2v',
        'note': '1 C, 1 O; 2 equivalent H',
    },
    'CH2NH': {
        'indices': [0, 1],
        'labels': ['C1', 'N1'],
        'sym': 'Cs',
        'note': '1 C, 1 N; 2 equiv H on C, 1 unique H on N',
    },
    'H2O': {
        'indices': [0],
        'labels': ['O1'],
        'sym': 'C2v',
        'note': '1 O; 2 equivalent H',
    },
    'pyridine': {
        'indices': [0, 1, 3],
        'labels': ['N', 'Cα', 'Cpara'],
        'sym': 'C2v',
        'note': '1 N; 3 inequiv C (α, β, para); C2 through N–Cpara',
    },
    'pyrrol': {
        'indices': [0, 2],
        'labels': ['Cα', 'N'],
        'sym': 'C2v',
        'note': '1 N; 2 inequiv C (α, β); C2 through N–midpoint',
    },
    'pentacene': {
        'indices': [0, 6, 10],
        'labels': ['C_term', 'C_junct', 'C_center'],
        'sym': 'D2h',
        'note': '6 inequiv C types; selected: terminal, junction, central',
    },
    'PTCDA': {
        'indices': [3, 14, 24],
        'labels': ['C_core', 'C_bay', 'O_anhyd'],
        'sym': 'D2h',
        'note': 'Multiple inequiv C + 2 inequiv O (C=O vs ring); selected: core C, bay C, anhydride O',
    },
}


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


def plot_molecule(ax, syms, ps, selected_idx, labels, title, bond_cut=1.8):
    """Plot a molecule in xy-plane with selected atoms highlighted."""
    sel_set = set(selected_idx)

    # Draw bonds
    for i in range(len(syms)):
        for j in range(i + 1, len(syms)):
            d = np.linalg.norm(ps[i] - ps[j])
            if d < bond_cut:
                ax.plot([ps[i, 0], ps[j, 0]], [ps[i, 1], ps[j, 1]], 'k-', lw=1.5, zorder=1)

    # Draw atoms
    for i, (s, p) in enumerate(zip(syms, ps)):
        c = ELEM_COLORS.get(s, '#2b8c4e')
        sz = ELEM_SIZES.get(s, 200)
        if i in sel_set:
            # Selected: gold fill, red edge, larger
            ax.scatter(p[0], p[1], c=SELECT_COLOR, s=sz * 2.5, edgecolors=SELECT_EDGE,
                       linewidths=2.5, zorder=10)
            # Label with element+index
            label = labels[list(selected_idx).index(i)]
            ax.annotate(label, (p[0], p[1]), color='black', fontsize=9, fontweight='bold',
                        ha='center', va='center', zorder=12,
                        bbox=dict(boxstyle='round,pad=0.15', fc='white', ec=SELECT_EDGE, alpha=0.85))
        else:
            ax.scatter(p[0], p[1], c=c, s=sz, edgecolors='black', linewidths=0.8, zorder=5)
            ax.text(p[0], p[1], f'{s}{i+1}', color='white', fontsize=6, ha='center', va='center', zorder=6)

    # Draw CO approach arrow for each selected atom (from above, +z direction = out of plane)
    for i, idx in enumerate(selected_idx):
        p = ps[idx]
        # Draw a small arrow indicating CO approach direction (perpendicular to plane)
        ax.annotate('', xy=(p[0], p[1] + 0.3), xytext=(p[0], p[1] + 1.5),
                    arrowprops=dict(arrowstyle='->', color=SELECT_EDGE, lw=2),
                    zorder=8)
        ax.text(p[0], p[1] + 1.7, 'CO↓', color=SELECT_EDGE, fontsize=7, ha='center', fontweight='bold')

    ax.set_aspect('equal')
    ax.set_xlabel('x (Å)')
    ax.set_ylabel('y (Å)')
    ax.set_title(title, fontsize=11)
    ax.grid(True, alpha=0.2)


def main():
    parser = argparse.ArgumentParser(description='Plot molecules with selected atoms')
    parser.add_argument('--mol', type=str, default=None, help='Single molecule name')
    args = parser.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)

    mols = [args.mol] if args.mol else list(SELECTED.keys())

    # Individual plots
    for mol in mols:
        if mol not in SELECTED:
            print(f"WARNING: {mol} not in SELECTED, skipping")
            continue
        xyz_path = os.path.join(GEOM_DIR, f'{mol}.xyz')
        if not os.path.isfile(xyz_path):
            print(f"WARNING: {xyz_path} not found, skipping")
            continue

        syms, ps = read_xyz(xyz_path)
        sel = SELECTED[mol]

        fig, ax = plt.subplots(figsize=(8, 7))
        plot_molecule(ax, syms, ps, sel['indices'], sel['labels'],
                      f"{mol} ({sel['sym']}) — selected atoms (gold)")

        # Add note
        fig.text(0.02, 0.02, sel['note'], fontsize=8, style='italic', color='#555555')

        outfile = os.path.join(OUT_DIR, f'selected_{mol}.png')
        fig.tight_layout(rect=[0, 0.04, 1, 1])
        fig.savefig(outfile, dpi=150, bbox_inches='tight')
        plt.close(fig)
        print(f"  {mol:12s} -> {outfile}  selected: {sel['labels']}")

    # Combined overview plot
    n = len(mols)
    ncols = 3
    nrows = (n + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(6 * ncols, 5 * nrows))
    axes_flat = axes.flatten() if hasattr(axes, 'flatten') else [axes]

    for idx, mol in enumerate(mols):
        if mol not in SELECTED:
            continue
        xyz_path = os.path.join(GEOM_DIR, f'{mol}.xyz')
        if not os.path.isfile(xyz_path):
            continue
        syms, ps = read_xyz(xyz_path)
        sel = SELECTED[mol]
        plot_molecule(axes_flat[idx], syms, ps, sel['indices'], sel['labels'],
                      f"{mol} ({sel['sym']})")

    # Hide unused axes
    for idx in range(len(mols), len(axes_flat)):
        axes_flat[idx].set_visible(False)

    fig.suptitle('Non-equivalent atoms selected for CO rigid scan', fontsize=14, fontweight='bold')
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    overview = os.path.join(OUT_DIR, 'selected_overview.png')
    fig.savefig(overview, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"\n  Overview -> {overview}")

    # Print summary table
    print(f"\n{'='*70}")
    print(f"{'Molecule':12s} {'Sym':6s} {'Selected atoms':30s} {'Indices'}")
    print(f"{'='*70}")
    for mol in mols:
        if mol not in SELECTED:
            continue
        sel = SELECTED[mol]
        labels_str = ', '.join(sel['labels'])
        indices_str = str(sel['indices'])
        print(f"{mol:12s} {sel['sym']:6s} {labels_str:30s} {indices_str}")
    print(f"{'='*70}")


if __name__ == '__main__':
    main()
