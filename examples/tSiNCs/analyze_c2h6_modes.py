#!/usr/bin/env python3
"""
C2H6 Mode Analysis Script

Performs comprehensive analysis of C2H6 vibrational modes across methods:
1. Cosine distance matching between methods (pySCF, DFTB+, MMFF)
2. Mode characterization (CC stretch, CH stretch, HCH bend, etc.)
3. Comparison plots with mode annotations
4. Summary tables with assignments
"""

import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from ase.io import read
from ase.data import atomic_masses, atomic_numbers

from vib_store import load_method, method_dir, discover_methods
from vib_match import match_modes, overlap_matrix, mass_weight_vectors, normalize_rows


def characterize_c2h6_mode(mode, atoms, freq, threshold=0.6):
    """
    Characterize a C2H6 vibrational mode using frequency + displacement patterns.
    
    C2H6 has 18 vibrational modes (8 atoms * 3 - 6):
      - CH stretches: ~2800-3100 cm⁻¹ (6 modes: sym/asym on each CH3)
      - HCH bends: ~1300-1500 cm⁻¹ (6 modes)
      - CCH bends: ~1100-1400 cm⁻¹ (3 modes)
      - CC stretch: ~950-1050 cm⁻¹ (1 mode)
      - Torsions: ~250-350 cm⁻¹ (2 modes: symmetric and asymmetric)
    
    C2H6 structure:
      atoms 0,1 = C (two carbons bonded to each other)
      atoms 2,3,4 = H attached to C0
      atoms 5,6,7 = H attached to C1
    """
    mode = np.asarray(mode)  # (8, 3) array
    n_atoms = len(mode)
    
    # Compute displacement magnitudes per atom
    disp_mag = np.linalg.norm(mode, axis=1)
    total_disp = np.sum(disp_mag)
    
    if total_disp < 1e-10:
        return {'type': 'undefined', 'description': 'Zero displacement', 'primary_coord': 'none'}
    
    # Normalize to get fractional participation
    frac_disp = disp_mag / total_disp
    
    # C2H6 specific atom indices
    C1, C2 = 0, 1  # Two carbon atoms
    H1s = [2, 3, 4]  # Hydrogens on C1
    H2s = [5, 6, 7]  # Hydrogens on C2
    
    # Check which atoms are involved (>15% of total motion)
    significant = np.where(frac_disp > 0.15)[0]
    c1_frac = frac_disp[C1]
    c2_frac = frac_disp[C2]
    h1_frac = np.sum([frac_disp[h] for h in H1s])
    h2_frac = np.sum([frac_disp[h] for h in H2s])
    
    # Get displacement vectors
    c1_disp = mode[C1]
    c2_disp = mode[C2]
    
    # C-C bond vector
    cc_vec = atoms.positions[C2] - atoms.positions[C1]
    cc_vec /= np.linalg.norm(cc_vec)
    
    # Check if C atoms move along C-C bond (for stretch identification)
    c1_along_cc = abs(np.dot(c1_disp, cc_vec)) / (np.linalg.norm(c1_disp) + 1e-10)
    c2_along_cc = abs(np.dot(c2_disp, -cc_vec)) / (np.linalg.norm(c2_disp) + 1e-10)
    
    # Check if C atoms move in opposite directions (stretch) vs same (translation)
    c_opposite_motion = np.dot(c1_disp, c2_disp) < 0
    
    # Classify based on frequency ranges + displacement patterns
    
    # 1. CH STRETCHES: 2800-3200 cm⁻¹
    #    - H atoms move strongly along C-H bonds
    #    - C atoms have minimal motion
    if 2800 <= freq <= 3200:
        if h1_frac > 0.6 and c1_frac < 0.2:
            return {'type': 'CH_stretch', 'description': 'C-H stretch (C1 side, CH3)', 'primary_coord': 'bond'}
        elif h2_frac > 0.6 and c2_frac < 0.2:
            return {'type': 'CH_stretch', 'description': 'C-H stretch (C2 side, CH3)', 'primary_coord': 'bond'}
        else:
            return {'type': 'CH_stretch', 'description': 'C-H stretch (mixed)', 'primary_coord': 'bond'}
    
    # 2. CC STRETCH: ~950-1050 cm⁻¹
    #    - C atoms move strongly along C-C bond in opposite directions
    if 950 <= freq <= 1100:
        if c1_frac > 0.2 and c2_frac > 0.2 and c_opposite_motion:
            if c1_along_cc > 0.7 and c2_along_cc > 0.7:
                return {'type': 'CC_stretch', 'description': 'C-C bond stretch', 'primary_coord': 'bond'}
        # Could be CCH bend in this range too
        if (c1_frac > 0.15 or c2_frac > 0.15) and (h1_frac > 0.3 or h2_frac > 0.3):
            return {'type': 'CCH_bend', 'description': 'C-C-H angle bend', 'primary_coord': 'angle'}
    
    # 3. BENDING MODES: 1100-1600 cm⁻¹
    #    - Mix of H and C motion
    #    - H atoms move perpendicular to C-H bonds
    if 1100 <= freq <= 1600:
        # Check for HCH bend (H atoms on same C moving in opposite directions)
        if h1_frac > 0.5 and c1_frac < 0.15:
            # Check if H atoms on C1 are moving against each other
            h_disps = [mode[h] for h in H1s]
            h_dots = [np.dot(h_disps[i], h_disps[j]) for i in range(3) for j in range(i+1, 3)]
            if any(d < -0.2 for d in h_dots):
                return {'type': 'HCH_bend', 'description': 'H-C-H angle bend (C1)', 'primary_coord': 'angle'}
        if h2_frac > 0.5 and c2_frac < 0.15:
            h_disps = [mode[h] for h in H2s]
            h_dots = [np.dot(h_disps[i], h_disps[j]) for i in range(3) for j in range(i+1, 3)]
            if any(d < -0.2 for d in h_dots):
                return {'type': 'HCH_bend', 'description': 'H-C-H angle bend (C2)', 'primary_coord': 'angle'}
        
        # CCH bend: C and H on same side move, some motion along C-C axis
        if (c1_frac > 0.1 or c2_frac > 0.1) and (h1_frac > 0.2 or h2_frac > 0.2):
            return {'type': 'CCH_bend', 'description': 'C-C-H angle bend', 'primary_coord': 'angle'}
        
        return {'type': 'bend', 'description': 'Bending mode (mixed)', 'primary_coord': 'angle'}
    
    # 4. TORSIONS: < 400 cm⁻¹
    #    - H atoms on opposite sides move in opposite directions
    #    - C atoms have minimal motion
    if freq < 400:
        if h1_frac > 0.3 and h2_frac > 0.3 and c1_frac < 0.15 and c2_frac < 0.15:
            return {'type': 'torsion', 'description': 'C-C torsion (methyl rotation)', 'primary_coord': 'torsion'}
        if c1_frac < 0.2 and c2_frac < 0.2:
            return {'type': 'torsion', 'description': 'Low-freq motion (torsion/bend)', 'primary_coord': 'torsion'}
    
    # 5. ROCKING/UMBRELLA: 800-1000 cm⁻¹
    if 800 <= freq < 950:
        if (h1_frac > 0.4 or h2_frac > 0.4) and (c1_frac > 0.1 or c2_frac > 0.1):
            return {'type': 'rocking', 'description': 'CH3 rocking/umbrella', 'primary_coord': 'angle'}
    
    # Default: classify by dominant motion
    if h1_frac > 0.7 or h2_frac > 0.7:
        return {'type': 'H_motion', 'description': 'Hydrogen-dominated motion', 'primary_coord': 'mixed'}
    elif c1_frac > 0.3 and c2_frac > 0.3:
        if c_opposite_motion:
            return {'type': 'CC_stretch', 'description': 'C-C stretch (weak)', 'primary_coord': 'bond'}
        else:
            return {'type': 'translation', 'description': 'Translational motion', 'primary_coord': 'translation'}
    else:
        return {'type': 'mixed', 'description': 'Mixed motion', 'primary_coord': 'mixed'}


def create_mode_characterization_table(methods_data, ref_tag='pyscf_b3lyp_cc-pVDZ'):
    """Create a table characterizing each mode for all methods."""
    ref_data = methods_data[ref_tag]
    atoms = ref_data['atoms']
    
    # Characterize each reference mode
    mode_chars = []
    for i, mode in enumerate(ref_data['modes']):
        freq = ref_data['mode_freqs'][i]
        char = characterize_c2h6_mode(mode, atoms, freq)
        char['freq'] = freq
        char['idx'] = i
        mode_chars.append(char)
    
    return mode_chars


def plot_projection_matrices(methods_data, ref_tag='pyscf_b3lyp_cc-pVDZ', workdir='results', noshow=True):
    """Create N×N projection matrix plots between reference and each other method."""
    
    ref_data = methods_data.get(ref_tag)
    if ref_data is None:
        print(f"Warning: {ref_tag} not available, skipping projection matrices")
        return
    
    masses = ref_data['atoms'].get_masses()
    A = normalize_rows(mass_weight_vectors(ref_data['modes'], masses))
    
    # Get other methods
    other_tags = [tag for tag in methods_data.keys() if tag != ref_tag and methods_data[tag] is not None]
    
    n_others = len(other_tags)
    if n_others == 0:
        print("No other methods available for projection matrices")
        return
    
    # Create subplots
    fig, axes = plt.subplots(1, n_others, figsize=(5 * n_others, 5))
    if n_others == 1:
        axes = [axes]
    
    for ax, tag in zip(axes, other_tags):
        data = methods_data[tag]
        B = normalize_rows(mass_weight_vectors(data['modes'], masses))
        O = np.abs(A @ B.T)  # Projection matrix
        
        # Plot
        im = ax.imshow(O, cmap='viridis', vmin=0, vmax=1, aspect='auto')
        ax.set_xlabel(f'{tag.replace("_", " ")} Mode Index')
        ax.set_ylabel(f'{ref_tag.replace("_", " ")} Mode Index')
        ax.set_title(f'Projection Matrix: {tag.replace("_", " ")}')
        
        # Add colorbar
        plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        
        # Highlight diagonal for reference
        n_ref = O.shape[0]
        ax.plot(range(n_ref), range(n_ref), 'r--', alpha=0.3, linewidth=1)
    
    plt.tight_layout()
    
    # Save
    out_path = Path(workdir) / 'C2H6' / 'plots' / 'projection_matrices.png'
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(str(out_path), dpi=150, bbox_inches='tight')
    print(f"Saved: {out_path}")
    
    if not noshow:
        plt.show()
    
    return fig


def create_comparison_plot(methods_data, mode_chars, workdir='results', noshow=True):
    """Create comprehensive comparison plot with mode annotations."""
    
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    
    # Method colors
    colors = {
        'pyscf_b3lyp_cc-pVDZ': '#1f77b4',
        'dftb_mio-1-1': '#ff7f0e', 
        'dftb_3ob-3-1': '#2ca02c',
        'mmff_angles': '#d62728',
        'mmff_angles_bond1.995_angle0.30': '#9467bd'
    }
    
    # Plot 1: Stick spectra comparison (vertically offset by method)
    ax1 = axes[0, 0]
    y_offset = 0
    offset_step = 1.2  # Vertical spacing between methods
    
    for tag in ['pyscf_b3lyp_cc-pVDZ', 'dftb_mio-1-1', 'dftb_3ob-3-1', 'mmff_angles', 'mmff_angles_bond1.995_angle0.30']:
        if tag not in methods_data or methods_data[tag] is None:
            continue
        data = methods_data[tag]
        freqs = data['mode_freqs']
        color = colors.get(tag, '#999999')
        label = tag.replace('_', ' ')
        
        # Plot with vertical offset
        y_base = y_offset
        y_top = y_offset + 1.0
        ax1.vlines(freqs, y_base, y_top, colors=color, label=label, alpha=0.8, linewidth=1.5)
        
        # Add method label on the right
        ax1.text(3500, (y_base + y_top) / 2, label, va='center', ha='left', 
                fontsize=9, color=color, fontweight='bold')
        
        y_offset += offset_step
    
    ax1.set_xlabel('Frequency (cm⁻¹)')
    ax1.set_ylabel('Method (offset)')
    ax1.set_title('C2H6 Vibrational Spectra Comparison')
    ax1.set_xlim(0, 3500)
    ax1.set_ylim(-0.2, y_offset + 0.2)
    
    # Plot 2: Mode type distribution
    ax2 = axes[0, 1]
    type_counts = {}
    for char in mode_chars:
        t = char['type']
        type_counts[t] = type_counts.get(t, 0) + 1
    
    types = list(type_counts.keys())
    counts = list(type_counts.values())
    ax2.bar(types, counts, color='steelblue', alpha=0.7)
    ax2.set_xlabel('Mode Type')
    ax2.set_ylabel('Count')
    ax2.set_title('C2H6 Mode Characterization (Reference)')
    ax2.tick_params(axis='x', rotation=45)
    
    # Plot 3: Frequency correlation (ref vs others)
    ax3 = axes[1, 0]
    ref_tag = 'pyscf_b3lyp_cc-pVDZ'
    ref_data = methods_data.get(ref_tag)
    
    if ref_data is not None:
        ref_freqs = ref_data['mode_freqs']
        
        for tag, data in methods_data.items():
            if tag == ref_tag or data is None:
                continue
            
            # Match modes using overlap matrix
            masses = ref_data['atoms'].get_masses()
            A = normalize_rows(mass_weight_vectors(ref_data['modes'], masses))
            B = normalize_rows(mass_weight_vectors(data['modes'], masses))
            O = np.abs(A @ B.T)
            
            # Find best matches
            matches = []
            for i in range(len(ref_freqs)):
                j = np.argmax(O[i])
                matches.append((ref_freqs[i], data['mode_freqs'][j], O[i, j]))
            
            matched_ref = [m[0] for m in matches]
            matched_tgt = [m[1] for m in matches]
            color = colors.get(tag, '#999999')
            ax3.scatter(matched_ref, matched_tgt, c=color, label=tag.replace('_', ' '), alpha=0.6, s=50)
        
        # Reference line
        ax3.plot([0, 3500], [0, 3500], 'k--', alpha=0.3)
        ax3.set_xlabel(f'{ref_tag.replace("_", " ")} Frequency (cm⁻¹)')
        ax3.set_ylabel('Other Method Frequency (cm⁻¹)')
        ax3.set_title('Frequency Correlation')
        ax3.legend()
    
    # Plot 4: Mode assignment table (text)
    ax4 = axes[1, 1]
    ax4.axis('off')
    
    # Create text table
    table_text = []
    table_text.append(f"{'Mode':<6} {'Freq':<8} {'Type':<15} {'Description':<30}")
    table_text.append('-' * 60)
    
    for char in sorted(mode_chars, key=lambda x: x['freq']):
        table_text.append(f"{char['idx']+1:<6} {char['freq']:<8.1f} {char['type']:<15} {char['description']:<30}")
    
    ax4.text(0.1, 0.95, '\n'.join(table_text), transform=ax4.transAxes,
             fontfamily='monospace', fontsize=9, verticalalignment='top')
    ax4.set_title('Mode Assignments (Reference: PySCF)')
    
    plt.tight_layout()
    
    # Save
    out_path = Path(workdir) / 'C2H6' / 'plots' / 'mode_analysis.png'
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(str(out_path), dpi=150, bbox_inches='tight')
    print(f"Saved: {out_path}")
    
    if not noshow:
        plt.show()
    
    return fig


def create_full_comparison_table(methods_data, workdir='results'):
    """Create a comprehensive CSV table with all methods and mode assignments."""
    
    # Use pySCF as reference for mode characterization
    ref_tag = 'pyscf_b3lyp_cc-pVDZ'
    ref_data = methods_data.get(ref_tag)
    if ref_data is None:
        print("Warning: pySCF reference not found, skipping detailed table")
        return
    
    # Characterize reference modes
    mode_chars = create_mode_characterization_table(methods_data, ref_tag)
    
    # Create output
    lines = []
    header = ['mode_idx', 'mode_type', 'description', 'primary_coord']
    
    # Add columns for each method
    method_tags = sorted(methods_data.keys())
    for tag in method_tags:
        header.append(f'{tag}_freq')
        header.append(f'{tag}_cosine')
    
    lines.append(','.join(header))
    
    # For each reference mode, find matches in all other methods
    masses = ref_data['atoms'].get_masses()
    A = normalize_rows(mass_weight_vectors(ref_data['modes'], masses))
    
    for i, char in enumerate(mode_chars):
        row = [str(i+1), char['type'], char['description'], char['primary_coord']]
        
        for tag in method_tags:
            data = methods_data[tag]
            if data is None:
                row.append('NA')
                row.append('NA')
                continue
            
            # Find best match
            B = normalize_rows(mass_weight_vectors(data['modes'], masses))
            O = np.abs(A @ B.T)
            j = np.argmax(O[i])
            
            row.append(f"{data['mode_freqs'][j]:.2f}")
            row.append(f"{O[i, j]:.4f}")
        
        lines.append(','.join(row))
    
    # Save to CSV
    out_path = Path(workdir) / 'C2H6' / 'mode_comparison_full.csv'
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w') as f:
        f.write('\n'.join(lines))
    
    print(f"Saved: {out_path}")
    return out_path


def create_frequency_comparison_table(methods_data, mode_chars, ref_tag='pyscf_b3lyp_cc-pVDZ', workdir='results'):
    """Create clean frequency comparison table for corresponding modes."""
    
    ref_data = methods_data.get(ref_tag)
    if ref_data is None:
        print(f"Warning: {ref_tag} not available, skipping frequency table")
        return
    
    # Get reference frequencies and modes
    ref_freqs = ref_data['mode_freqs']
    masses = ref_data['atoms'].get_masses()
    A = normalize_rows(mass_weight_vectors(ref_data['modes'], masses))
    
    # Build table
    lines = []
    header = ['Mode', 'Type', 'Description']
    
    # Add columns for each method
    method_tags = sorted(methods_data.keys())
    for tag in method_tags:
        header.append(f'{tag.replace("_", " ")}')
    
    lines.append(','.join(header))
    
    # For each reference mode, find best match in each method
    for i, char in enumerate(mode_chars):
        row = [str(i+1), char['type'], char['description']]
        
        for tag in method_tags:
            data = methods_data[tag]
            if data is None:
                row.append('NA')
                continue
            
            if tag == ref_tag:
                row.append(f"{ref_freqs[i]:.2f}")
            else:
                # Find best match using projection matrix
                B = normalize_rows(mass_weight_vectors(data['modes'], masses))
                O = np.abs(A @ B.T)
                j = np.argmax(O[i])
                row.append(f"{data['mode_freqs'][j]:.2f}")
        
        lines.append(','.join(row))
    
    # Save to CSV
    out_path = Path(workdir) / 'C2H6' / 'frequency_comparison.csv'
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w') as f:
        f.write('\n'.join(lines))
    
    print(f"Saved: {out_path}")
    
    # Also print to console
    print(f"\n{'='*100}")
    print("Frequency Comparison Table (Corresponding Modes)")
    print(f"{'='*100}")
    print('\n'.join(lines[:2]))  # header
    for line in lines[2:]:
        print(line)
    
    return out_path


def main():
    """Main analysis function for C2H6."""
    workdir = 'results'
    mol_name = 'C2H6'
    
    print(f"\n{'='*60}")
    print(f"C2H6 Mode Analysis")
    print(f"{'='*60}\n")
    
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
    
    # Check if we have pySCF reference
    ref_tag = 'pyscf_b3lyp_cc-pVDZ'
    if ref_tag not in methods_data or methods_data[ref_tag] is None:
        print(f"\nWarning: {ref_tag} not available, using first available method for reference")
        ref_tag = [t for t, d in methods_data.items() if d is not None][0]
    
    # Create mode characterization
    print(f"\n{'='*60}")
    print("Mode Characterization")
    print(f"{'='*60}")
    mode_chars = create_mode_characterization_table(methods_data, ref_tag)
    
    # Print summary
    print(f"\n{'Mode':<6} {'Freq':<10} {'Type':<15} {'Description'}")
    print('-' * 70)
    for char in sorted(mode_chars, key=lambda x: x['freq']):
        print(f"{char['idx']+1:<6} {char['freq']:<10.1f} {char['type']:<15} {char['description']}")
    
    # Count by type
    type_counts = {}
    for char in mode_chars:
        t = char['type']
        type_counts[t] = type_counts.get(t, 0) + 1
    
    print(f"\n{'Type':<15} {'Count'}")
    print('-' * 25)
    for t, c in sorted(type_counts.items()):
        print(f"{t:<15} {c}")
    
    # Create projection matrices
    print(f"\n{'='*60}")
    print("Generating Projection Matrices (Mode Assignment Verification)")
    print(f"{'='*60}")
    plot_projection_matrices(methods_data, ref_tag=ref_tag, workdir=workdir, noshow=True)
    
    # Create comparison plots
    print(f"\n{'='*60}")
    print("Generating Comparison Plots")
    print(f"{'='*60}")
    create_comparison_plot(methods_data, mode_chars, workdir=workdir, noshow=True)
    
    # Create frequency comparison table
    print(f"\n{'='*60}")
    print("Creating Frequency Comparison Table")
    print(f"{'='*60}")
    create_frequency_comparison_table(methods_data, mode_chars, ref_tag=ref_tag, workdir=workdir)
    
    print(f"\n{'='*60}")
    print("Analysis Complete")
    print(f"{'='*60}")
    print(f"\nGenerated files:")
    print(f"  - results/C2H6/plots/projection_matrices.png")
    print(f"  - results/C2H6/plots/mode_analysis.png")
    print(f"  - results/C2H6/frequency_comparison.csv")


if __name__ == '__main__':
    main()
