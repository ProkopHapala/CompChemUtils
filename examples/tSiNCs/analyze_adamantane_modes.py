#!/usr/bin/env python3
"""
Adamantane Mode Analysis Script

Performs analysis of adamantane vibrational modes across methods:
- DFTB+ mio-1-1 (reference)
- DFTB+ 3ob-3-1
- MMFF (unscaled)
- MMFF (scaled with bond=1.995, angle=0.30)
"""

import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

from vib_store import load_method, discover_methods
from vib_match import mass_weight_vectors, normalize_rows


def create_comparison_plot(methods_data, ref_tag='dftb_mio-1-1', workdir='results', noshow=True):
    """Create comprehensive comparison plot for adamantane."""
    
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    
    # Method colors
    colors = {
        'dftb_mio-1-1': '#1f77b4',
        'dftb_3ob-3-1': '#ff7f0e', 
        'mmff_angles': '#d62728',
        'mmff_angles_bond1.995_angle0.30': '#9467bd',
        'mmff_angles_ch1.995_cc1.0_angle0.30': '#8c564b'
    }
    
    # Plot 1: Stick spectra comparison (vertically offset by method)
    ax1 = axes[0, 0]
    y_offset = 0
    offset_step = 1.2
    
    for tag in ['dftb_mio-1-1', 'dftb_3ob-3-1', 'mmff_angles', 'mmff_angles_bond1.995_angle0.30', 'mmff_angles_ch1.995_cc1.0_angle0.30']:
        if tag not in methods_data or methods_data[tag] is None:
            continue
        data = methods_data[tag]
        freqs = data['mode_freqs']
        color = colors.get(tag, '#999999')
        label = tag.replace('_', ' ')
        
        y_base = y_offset
        y_top = y_offset + 1.0
        ax1.vlines(freqs, y_base, y_top, colors=color, label=label, alpha=0.8, linewidth=1.5)
        ax1.text(5000, (y_base + y_top) / 2, label, va='center', ha='left', 
                fontsize=9, color=color, fontweight='bold')
        
        y_offset += offset_step
    
    ax1.set_xlabel('Frequency (cm⁻¹)')
    ax1.set_ylabel('Method (offset)')
    ax1.set_title('Adamantane Vibrational Spectra Comparison')
    ax1.set_xlim(0, 5000)
    ax1.set_ylim(-0.2, y_offset + 0.2)
    
    # Plot 2: C-H stretch range detail (2800-3200 cm⁻¹)
    ax2 = axes[0, 1]
    y_offset = 0
    
    for tag in ['dftb_mio-1-1', 'dftb_3ob-3-1', 'mmff_angles', 'mmff_angles_bond1.995_angle0.30', 'mmff_angles_ch1.995_cc1.0_angle0.30']:
        if tag not in methods_data or methods_data[tag] is None:
            continue
        data = methods_data[tag]
        freqs = data['mode_freqs']
        color = colors.get(tag, '#999999')
        label = tag.replace('_', ' ')
        
        # Filter to C-H stretch range
        ch_freqs = freqs[(freqs >= 2800) & (freqs <= 3200)]
        
        y_base = y_offset
        y_top = y_offset + 1.0
        ax2.vlines(ch_freqs, y_base, y_top, colors=color, label=label, alpha=0.8, linewidth=1.5)
        ax2.text(3250, (y_base + y_top) / 2, f'{label} ({len(ch_freqs)})', va='center', ha='left', 
                fontsize=8, color=color)
        
        y_offset += offset_step
    
    ax2.set_xlabel('Frequency (cm⁻¹)')
    ax2.set_ylabel('Method (offset)')
    ax2.set_title('C-H Stretch Range (2800-3200 cm⁻¹)')
    ax2.set_xlim(2800, 3200)
    ax2.set_ylim(-0.2, y_offset + 0.2)
    
    # Plot 3: Frequency correlation (ref vs others)
    ax3 = axes[1, 0]
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
            ax3.scatter(matched_ref, matched_tgt, c=color, label=tag.replace('_', ' '), alpha=0.6, s=30)
        
        ax3.plot([0, 5000], [0, 5000], 'k--', alpha=0.3)
        ax3.set_xlabel(f'{ref_tag.replace("_", " ")} Frequency (cm⁻¹)')
        ax3.set_ylabel('Other Method Frequency (cm⁻¹)')
        ax3.set_title('Frequency Correlation')
        ax3.legend()
    
    # Plot 4: Statistics table
    ax4 = axes[1, 1]
    ax4.axis('off')
    
    # Create statistics table
    table_text = []
    table_text.append(f"{'Method':<35} {'Modes':<8} {'C-H (2800-3200)':<15} {'Mean C-H':<12}")
    table_text.append('-' * 70)
    
    for tag in ['dftb_mio-1-1', 'dftb_3ob-3-1', 'mmff_angles', 'mmff_angles_bond1.995_angle0.30', 'mmff_angles_ch1.995_cc1.0_angle0.30']:
        if tag not in methods_data or methods_data[tag] is None:
            continue
        data = methods_data[tag]
        freqs = data['mode_freqs']
        ch_freqs = freqs[(freqs >= 2800) & (freqs <= 3200)]
        mean_ch = ch_freqs.mean() if len(ch_freqs) > 0 else 0
        
        label = tag.replace('_', ' ')
        table_text.append(f"{label:<35} {len(freqs):<8} {len(ch_freqs):<15} {mean_ch:<12.1f}")
    
    ax4.text(0.1, 0.95, '\n'.join(table_text), transform=ax4.transAxes,
             fontfamily='monospace', fontsize=10, verticalalignment='top')
    ax4.set_title('Mode Statistics')
    
    plt.tight_layout()
    
    # Save
    out_path = Path(workdir) / 'adamantane' / 'plots' / 'mode_analysis.png'
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(str(out_path), dpi=150, bbox_inches='tight')
    print(f"Saved: {out_path}")
    
    if not noshow:
        plt.show()
    
    return fig


def main():
    """Main analysis function for adamantane."""
    workdir = 'results'
    mol_name = 'adamantane'
    
    print(f"\n{'='*60}")
    print(f"Adamantane Mode Analysis")
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
    
    # Create comparison plots
    print(f"\n{'='*60}")
    print("Generating Comparison Plots")
    print(f"{'='*60}")
    create_comparison_plot(methods_data, ref_tag='dftb_mio-1-1', workdir=workdir, noshow=True)
    
    print(f"\n{'='*60}")
    print("Analysis Complete")
    print(f"{'='*60}")
    print(f"\nGenerated files:")
    print(f"  - results/adamantane/plots/mode_analysis.png")


if __name__ == '__main__':
    main()
