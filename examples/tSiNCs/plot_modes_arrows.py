#!/usr/bin/env python3
"""
Plot vibrational modes with displacement arrows.

Creates 3D visualizations of molecular vibrations showing
atom positions and displacement vectors as arrows.
"""

import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from pathlib import Path
from ase.io import read


def plot_mode_with_arrows(atoms, mode, freq, mode_idx, scale=0.5, save_path=None):
    """Plot a single vibrational mode with displacement arrows."""
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection='3d')
    
    # Atom positions
    pos = atoms.get_positions()
    symbols = atoms.get_chemical_symbols()
    
    # Plot atoms
    colors = {'C': 'black', 'H': 'white'}
    sizes = {'C': 200, 'H': 100}
    
    for i, (p, s) in enumerate(zip(pos, symbols)):
        ax.scatter(p[0], p[1], p[2], c=colors.get(s, 'gray'), 
                   s=sizes.get(s, 100), edgecolors='black', alpha=0.8)
        ax.text(p[0], p[1], p[2], s, fontsize=12, fontweight='bold')
    
    # Plot displacement arrows
    # Normalize mode for visualization
    mode_norm = mode / (np.linalg.norm(mode, axis=1, keepdims=True) + 1e-10)
    displacement = mode_norm * scale
    
    for i, (p, d) in enumerate(zip(pos, displacement)):
        ax.quiver(p[0], p[1], p[2], d[0], d[1], d[2], 
                  color='red', linewidth=2, arrow_length_ratio=0.3, alpha=0.7)
    
    # Set equal aspect ratio
    max_range = np.array([pos[:,0].max()-pos[:,0].min(), 
                          pos[:,1].max()-pos[:,1].min(), 
                          pos[:,2].max()-pos[:,2].min()]).max() / 2.0
    mid_x = (pos[:,0].max()+pos[:,0].min()) * 0.5
    mid_y = (pos[:,1].max()+pos[:,1].min()) * 0.5
    mid_z = (pos[:,2].max()+pos[:,2].min()) * 0.5
    
    ax.set_xlim(mid_x - max_range, mid_x + max_range)
    ax.set_ylim(mid_y - max_range, mid_y + max_range)
    ax.set_zlim(mid_z - max_range, mid_z + max_range)
    
    ax.set_xlabel('X (Å)')
    ax.set_ylabel('Y (Å)')
    ax.set_zlabel('Z (Å)')
    ax.set_title(f'Mode {mode_idx+1}: {freq:.1f} cm⁻¹', fontsize=14, fontweight='bold')
    
    plt.tight_layout()
    
    if save_path:
        save_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(str(save_path), dpi=150, bbox_inches='tight')
        print(f'Saved: {save_path}')
    else:
        plt.show()
    
    plt.close(fig)


def plot_all_modes(atoms, modes, freqs, workdir='results', mol_name='CH4', method_tag='mmff_angles_bond1.89_angle0.70'):
    """Plot all vibrational modes with arrows."""
    outdir = Path(workdir) / mol_name / 'plots' / f'{method_tag}_modes'
    outdir.mkdir(parents=True, exist_ok=True)
    
    for i, (mode, freq) in enumerate(zip(modes, freqs)):
        save_path = outdir / f'mode_{i+1:02d}_{freq:.0f}cm.png'
        plot_mode_with_arrows(atoms, mode, freq, i, scale=0.4, save_path=save_path)
    
    print(f'All modes saved to: {outdir}')


def export_modes_xyz(atoms, modes, freqs, workdir='results', mol_name='CH4', method_tag='mmff_angles_bond1.89_angle0.70'):
    """Export modes as XYZ files with displacement vectors in comments."""
    outdir = Path(workdir) / mol_name / method_tag
    outdir.mkdir(parents=True, exist_ok=True)
    
    pos = atoms.get_positions()
    symbols = atoms.get_chemical_symbols()
    n_atoms = len(atoms)
    
    for i, (mode, freq) in enumerate(zip(modes, freqs)):
        xyz_path = outdir / f'mode_{i+1:02d}_{freq:.0f}cm.xyz'
        
        with open(xyz_path, 'w') as f:
            f.write(f'{n_atoms}\n')
            f.write(f'Mode {i+1}: {freq:.1f} cm⁻¹\n')
            for j, (p, s, d) in enumerate(zip(pos, symbols, mode)):
                # Write position and displacement vector in comment
                f.write(f'{s}  {p[0]:.8f}  {p[1]:.8f}  {p[2]:.8f}  # dx={d[0]:.4f} dy={d[1]:.4f} dz={d[2]:.4f}\n')
    
    print(f'XYZ files saved to: {outdir}')


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Plot vibrational modes with arrows')
    parser.add_argument('--mol', default='CH4', help='Molecule name')
    parser.add_argument('--method', default='mmff_angles_bond1.89_angle0.70', help='Method tag')
    parser.add_argument('--workdir', default='results', help='Working directory')
    parser.add_argument('--no-plot', action='store_true', help='Skip plotting, only export XYZ')
    parser.add_argument('--no-xyz', action='store_true', help='Skip XYZ export, only plot')
    
    args = parser.parse_args()
    
    # Load data
    atoms = read(f'{args.workdir}/{args.mol}/mmff_angles/relaxed.xyz')
    modes = np.load(f'{args.workdir}/{args.mol}/{args.method}/modes.npy', allow_pickle=True)
    freqs = np.load(f'{args.workdir}/{args.mol}/{args.method}/freq.npy')
    
    print(f'Loaded {len(modes)} modes for {args.mol}/{args.method}')
    
    # Plot modes
    if not args.no_plot:
        plot_all_modes(atoms, modes, freqs, workdir=args.workdir, mol_name=args.mol, method_tag=args.method)
    
    # Export XYZ
    if not args.no_xyz:
        export_modes_xyz(atoms, modes, freqs, workdir=args.workdir, mol_name=args.mol, method_tag=args.method)
