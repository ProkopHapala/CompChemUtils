#!/usr/bin/env python3
"""
CH4 Mode Analysis Script

CH4 has 9 vibrational modes (5 atoms * 3 - 6):
  - 1 symmetric C-H stretch (A1): all 4 H move radially outward/inward together
  - 2 asymmetric C-H stretches (T2): 3 H move opposite to 1 H (triply degenerate)
  - 2 bending modes (T2): H-C-H angle deformation (triply degenerate)

Expected frequency ranges:
  - C-H stretches: ~2800-3200 cm⁻¹
  - Bending modes: ~1300-1600 cm⁻¹
"""

import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from ase.io import read

from vib_store import load_method, discover_methods
from vib_match import overlap_matrix, mass_weight_vectors, normalize_rows


def characterize_ch4_mode(mode, atoms, freq):
    """
    Characterize a CH4 vibrational mode by analyzing displacement patterns.
    
    CH4 structure:
      atom 0 = C (central carbon)
      atoms 1-4 = H (4 hydrogens, tetrahedral geometry)
    """
    mode = np.asarray(mode)  # (5, 3) array
    n_atoms = len(mode)
    
    # Compute displacement magnitudes per atom
    disp_mag = np.linalg.norm(mode, axis=1)
    total_disp = np.sum(disp_mag)
    
    if total_disp < 1e-10:
        return {'type': 'undefined', 'description': 'Zero displacement'}
    
    # Normalize to get fractional participation
    frac_disp = disp_mag / total_disp
    
    # CH4 specific atom indices
    C = 0  # Central carbon
    Hs = [1, 2, 3, 4]  # Four hydrogens
    
    # Check which atoms are involved
    c_frac = frac_disp[C]
    h_fracs = [frac_disp[h] for h in Hs]
    h_total = np.sum(h_fracs)
    
    # Get displacement vectors
    c_disp = mode[C]
    h_disps = [mode[h] for h in Hs]
    
    # C-H bond vectors (from C to each H)
    ch_bonds = [atoms.positions[h] - atoms.positions[C] for h in Hs]
    ch_bonds = [b / np.linalg.norm(b) for b in ch_bonds]
    
    # Check if H atoms move along C-H bonds (stretch) vs perpendicular (bend)
    h_parallel = []
    h_perp = []
    for h_disp, ch_bond in zip(h_disps, ch_bonds):
        proj = np.dot(h_disp, ch_bond)
        h_parallel.append(abs(proj))
        h_perp.append(np.linalg.norm(h_disp - proj * ch_bond))
    
    avg_parallel = np.mean(h_parallel)
    avg_perp = np.mean(h_perp)
    
    # Classify based on frequency + displacement patterns
    
    # C-H STRETCHES: 2800-3200 cm⁻¹
    if 2800 <= freq <= 3200:
        # Check if H atoms move along C-H bonds
        if avg_parallel > 2 * avg_perp:
            # Check if all H move in same direction (symmetric) or opposite (asymmetric)
            h_dot_products = [np.dot(h_disps[i], h_disps[j]) 
                             for i in range(4) for j in range(i+1, 4)]
            avg_dot = np.mean(h_dot_products)
            
            if avg_dot > 0:
                return {'type': 'symmetric_stretch', 'description': 'Symmetric C-H stretch (A1)'}
            else:
                return {'type': 'asymmetric_stretch', 'description': 'Asymmetric C-H stretch (T2)'}
        else:
            return {'type': 'CH_stretch', 'description': 'C-H stretch (mixed)'}
    
    # BENDING MODES: 1200-1600 cm⁻¹
    if 1200 <= freq <= 1600:
        if avg_perp > 2 * avg_parallel:
            return {'type': 'bend', 'description': 'H-C-H bending (T2)'}
        else:
            return {'type': 'bend', 'description': 'Bending mode (mixed)'}
    
    # Default classification
    if h_total > 0.8:
        return {'type': 'H_motion', 'description': 'Hydrogen-dominated motion'}
    elif c_frac > 0.3:
        return {'type': 'C_motion', 'description': 'Carbon motion'}
    else:
        return {'type': 'mixed', 'description': 'Mixed motion'}


def create_ch4_analysis(methods_data, workdir='results'):
    """Create comprehensive CH4 analysis."""
    
    mol_name = 'CH4'
    ref_tag = 'pyscf_b3lyp_cc-pVDZ'
    
    print(f"\n{'='*60}")
    print(f"CH4 Mode Analysis")
    print(f"{'='*60}\n")
    
    # Load reference data
    ref_data = methods_data.get(ref_tag)
    if ref_data is None:
        print(f"Warning: {ref_tag} not available")
        return
    
    atoms = ref_data['atoms']
    masses = atoms.get_masses()
    
    # Characterize reference modes
    mode_chars = []
    for i, mode in enumerate(ref_data['modes']):
        freq = ref_data['mode_freqs'][i]
        char = characterize_ch4_mode(mode, atoms, freq)
        char['freq'] = freq
        char['idx'] = i
        mode_chars.append(char)
    
    # Print characterization
    print(f"{'Mode':<6} {'Freq':<10} {'Type':<20} {'Description'}")
    print('-' * 70)
    for char in sorted(mode_chars, key=lambda x: x['freq']):
        print(f"{char['idx']+1:<6} {char['freq']:<10.1f} {char['type']:<20} {char['description']}")
    
    # Count by type
    type_counts = {}
    for char in mode_chars:
        t = char['type']
        type_counts[t] = type_counts.get(t, 0) + 1
    
    print(f"\n{'Type':<20} {'Count'}")
    print('-' * 30)
    for t, c in sorted(type_counts.items()):
        print(f"{t:<20} {c}")
    
    # Create frequency comparison table
    print(f"\n{'='*100}")
    print("Frequency Comparison Table")
    print(f"{'='*100}")
    
    header = ['Mode', 'Type', 'Description']
    method_tags = sorted(methods_data.keys())
    for tag in method_tags:
        header.append(f'{tag.replace("_", " ")}')
    
    lines = [','.join(header)]
    
    # Get reference modes for matching
    A = normalize_rows(mass_weight_vectors(ref_data['modes'], masses))
    
    for i, char in enumerate(mode_chars):
        row = [str(i+1), char['type'], char['description']]
        
        for tag in method_tags:
            data = methods_data[tag]
            if data is None:
                row.append('NA')
                continue
            # Skip methods with wrong number of modes
            if len(data['mode_freqs']) != 9:
                row.append('NA')
                continue
            
            if tag == ref_tag:
                row.append(f"{ref_data['mode_freqs'][i]:.2f}")
            else:
                # Find best match using projection matrix
                B = normalize_rows(mass_weight_vectors(data['modes'], masses))
                O = np.abs(A @ B.T)
                j = np.argmax(O[i])
                row.append(f"{data['mode_freqs'][j]:.2f}")
        
        lines.append(','.join(row))
    
    # Save and print table
    out_path = Path(workdir) / 'CH4' / 'frequency_comparison.csv'
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w') as f:
        f.write('\n'.join(lines))
    print(f"Saved: {out_path}")
    print('\n'.join(lines[:2]))
    for line in lines[2:]:
        print(line)
    
    # Create projection matrices
    print(f"\n{'='*60}")
    print("Generating Projection Matrices")
    print(f"{'='*60}")
    
    other_tags = [tag for tag in method_tags if tag != ref_tag and methods_data[tag] is not None]
    # Skip methods with wrong number of modes
    other_tags = [tag for tag in other_tags if len(methods_data[tag]['mode_freqs']) == 9]
    n_others = len(other_tags)
    
    if n_others > 0:
        fig, axes = plt.subplots(1, n_others, figsize=(5 * n_others, 5))
        if n_others == 1:
            axes = [axes]
        
        for ax, tag in zip(axes, other_tags):
            data = methods_data[tag]
            B = normalize_rows(mass_weight_vectors(data['modes'], masses))
            O = np.abs(A @ B.T)
            
            im = ax.imshow(O, cmap='viridis', vmin=0, vmax=1, aspect='auto')
            ax.set_xlabel(f'{tag.replace("_", " ")} Mode Index')
            ax.set_ylabel(f'{ref_tag.replace("_", " ")} Mode Index')
            ax.set_title(f'Projection Matrix: {tag.replace("_", " ")}')
            plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
            
            n_ref = O.shape[0]
            ax.plot(range(n_ref), range(n_ref), 'r--', alpha=0.3, linewidth=1)
        
        plt.tight_layout()
        plot_path = Path(workdir) / 'CH4' / 'plots' / 'projection_matrices.png'
        plot_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(str(plot_path), dpi=150, bbox_inches='tight')
        print(f"Saved: {plot_path}")
    
    # Create spectra plot
    print(f"\n{'='*60}")
    print("Generating Spectra Plot")
    print(f"{'='*60}")
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    colors = {
        'pyscf_b3lyp_cc-pVDZ': '#1f77b4',
        'dftb_mio-1-1': '#ff7f0e',
        'dftb_3ob-3-1': '#2ca02c',
        'mmff_angles': '#d62728',
        'mmff_angles_bond1.89_angle0.70': '#9467bd'
    }

    y_offset = 0
    offset_step = 1.2

    for tag in ['pyscf_b3lyp_cc-pVDZ', 'dftb_mio-1-1', 'dftb_3ob-3-1', 'mmff_angles', 'mmff_angles_bond1.89_angle0.70']:
        if tag not in methods_data or methods_data[tag] is None:
            continue
        # Skip methods with wrong number of modes
        if len(methods_data[tag]['mode_freqs']) != 9:
            print(f"Skipping {tag} (wrong number of modes: {len(methods_data[tag]['mode_freqs'])})")
            continue
        data = methods_data[tag]
        freqs = data['mode_freqs']
        color = colors.get(tag, '#999999')
        label = tag.replace('_', ' ')
        
        y_base = y_offset
        y_top = y_offset + 1.0
        ax.vlines(freqs, y_base, y_top, colors=color, label=label, alpha=0.8, linewidth=1.5)
        ax.text(3200, (y_base + y_top) / 2, label, va='center', ha='left', 
                fontsize=9, color=color, fontweight='bold')
        
        y_offset += offset_step
    
    ax.set_xlabel('Frequency (cm⁻¹)')
    ax.set_ylabel('Method (offset)')
    ax.set_title('CH4 Vibrational Spectra Comparison')
    ax.set_xlim(0, 3500)
    ax.set_ylim(-0.2, y_offset + 0.2)
    
    plt.tight_layout()
    spectra_path = Path(workdir) / 'CH4' / 'plots' / 'spectra_comparison.png'
    spectra_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(str(spectra_path), dpi=150, bbox_inches='tight')
    print(f"Saved: {spectra_path}")
    
    print(f"\n{'='*60}")
    print("Analysis Complete")
    print(f"{'='*60}")


def main():
    workdir = 'results'
    mol_name = 'CH4'
    
    # Discover available methods
    available_methods = discover_methods(mol_name, workdir)
    print(f"Available methods: {available_methods}")
    
    # Load all method data
    methods_data = {}
    for tag in available_methods:
        try:
            data = load_method(mol_name, tag, workdir=workdir, threshold=10.0)
            methods_data[tag] = data
            print(f"  Loaded {tag}: {len(data['mode_freqs'])} modes")
        except Exception as e:
            print(f"  Failed to load {tag}: {e}")
            methods_data[tag] = None
    
    # Run analysis
    create_ch4_analysis(methods_data, workdir=workdir)


if __name__ == '__main__':
    main()
