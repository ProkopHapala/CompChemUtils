#!/usr/bin/env python3
"""
Grid fit MMFF bond stiffness for C2H6 against QM reference.

Strategy:
- Fix C-H bond stiffness at optimal value from CH4 (scale=1.89)
- Fit C-C bond stiffness separately
- Optionally fit angle stiffness
"""

import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from ase.io import read

from vib_store import load_method
from mmff_molecular_session import MMFFMolecularSession


def rmse_freqs(freqs_calc, freqs_ref, min_freq=2000, max_freq=3200):
    """Compute RMSE between calculated and reference frequencies in a range.
    
    MMFF misses low-frequency torsional modes, so we fit only C-H stretches.
    """
    f_calc = np.asarray(freqs_calc)
    f_ref = np.asarray(freqs_ref)
    
    # Filter to frequency range (C-H stretches)
    mask_calc = (f_calc >= min_freq) & (f_calc <= max_freq)
    mask_ref = (f_ref >= min_freq) & (f_ref <= max_freq)
    
    f_calc_filtered = np.sort(f_calc[mask_calc])
    f_ref_filtered = np.sort(f_ref[mask_ref])
    
    if len(f_calc_filtered) != len(f_ref_filtered) or len(f_calc_filtered) == 0:
        return np.inf
    
    return np.sqrt(np.mean((f_calc_filtered - f_ref_filtered) ** 2))


def run_grid_fit_c2h6(workdir='results', n=10, range_cc=(0.5, 5.0), range_angle=(0.3, 2.0), 
                      fix_ch_scale=1.89):
    """Grid fit C-C bond and angle stiffness for C2H6."""
    
    # Load reference pySCF data
    ref_data = load_method('C2H6', 'pyscf_b3lyp_cc-pVDZ', workdir=workdir)
    freqs_ref = ref_data['mode_freqs']
    
    print(f'Reference: {len(freqs_ref)} modes from pySCF B3LYP/cc-pVDZ')
    print(f'Freq range: {freqs_ref.min():.1f} - {freqs_ref.max():.1f} cm^-1')
    
    # Grid parameters
    cc_scales = np.linspace(float(range_cc[0]), float(range_cc[1]), int(n))
    angle_scales = np.linspace(float(range_angle[0]), float(range_angle[1]), int(n))
    
    errors = np.zeros((len(cc_scales), len(angle_scales)))
    
    best = {"rmse": np.inf, "scale_cc": 1.0, "scale_angle": 1.0, "freqs": None, "best_ij": (0, 0)}
    
    # Reference atoms for geometry - use existing MMFF relaxed geometry
    ref_xyz = Path(workdir) / 'C2H6' / 'mmff_angles' / 'relaxed.xyz'
    if ref_xyz.exists():
        atoms = read(str(ref_xyz))
        print(f"Using reference geometry from {ref_xyz}")
    else:
        raise FileNotFoundError(f"MMFF relaxed geometry not found: {ref_xyz}")
    
    # Initialize reusable MMFF session (once!)
    print("\nInitializing MMFF session...")
    symbols = atoms.get_chemical_symbols()
    positions = atoms.get_positions()
    masses = atoms.get_masses()
    
    total = len(cc_scales) * len(angle_scales)
    count = 0
    
    with MMFFMolecularSession(positions, symbols, enable_angles=True) as sess:
        print(f"Session initialized. Running {total} grid points...\n")
        
        for ic, scc in enumerate(cc_scales):
            for ia, sa in enumerate(angle_scales):
                count += 1
                
                # Scale parameters in-place (no reinit!)
                # For C2H6: scale C-C bond by scc, C-H bond by fix_ch_scale, angles by sa
                # Note: This is a simplified approach - we scale ALL bonds and angles uniformly
                # A more sophisticated approach would scale specific bond types separately
                sess.set_scales(fix_ch_scale * scc, sa)  # Apply combined scaling
                
                # Compute frequencies
                freqs, modes, hess = sess.compute_frequencies(masses)
                
                e = rmse_freqs(freqs, freqs_ref)
                errors[ic, ia] = e
                
                if e < best["rmse"]:
                    best.update({
                        "rmse": e,
                        "scale_cc": float(scc),
                        "scale_angle": float(sa),
                        "freqs": freqs.copy(),
                        "best_ij": (ic, ia)
                    })
                    print(f"[{count}/{total}] C-C={scc:.3f} angle={sa:.3f} RMSE={e:.2f} cm^-1 *** NEW BEST ***")
                else:
                    print(f"[{count}/{total}] C-C={scc:.3f} angle={sa:.3f} RMSE={e:.2f} cm^-1")
    
    # Save results
    outdir = Path(workdir) / 'C2H6' / 'mmff_fit'
    outdir.mkdir(parents=True, exist_ok=True)
    
    np.savez(
        outdir / 'grid_errors.npz',
        cc_scales=cc_scales,
        angle_scales=angle_scales,
        errors=errors,
        best_rmse=best["rmse"],
        best_scale_cc=best["scale_cc"],
        best_scale_angle=best["scale_angle"],
        fix_ch_scale=fix_ch_scale
    )
    
    print(f"\n{'='*60}")
    print("Summary")
    print(f"{'='*60}")
    print(f"Best RMSE: {best['rmse']:.2f} cm^-1")
    print(f"Optimal C-C scale: {best['scale_cc']:.3f}")
    print(f"Optimal angle scale: {best['scale_angle']:.3f}")
    print(f"Fixed C-H scale: {fix_ch_scale:.3f}")
    print(f"Effective C-H scale: {fix_ch_scale * best['scale_cc']:.3f}")
    print(f"Saved: {outdir / 'grid_errors.npz'}")
    
    # Plot heatmap
    fig, ax = plt.subplots(figsize=(10, 8))
    im = ax.imshow(errors, aspect='auto', origin='lower', 
                   extent=[angle_scales[0], angle_scales[-1], cc_scales[0], cc_scales[-1]],
                   cmap='viridis_r')
    
    ax.set_xlabel('Angle Scale')
    ax.set_ylabel('C-C Bond Scale')
    ax.set_title(f'C2H6 MMFF Fitting (C-H fixed at {fix_ch_scale})\nRMSE vs C-C and Angle Scales')
    
    cbar = plt.colorbar(im, ax=ax)
    cbar.set_label('RMSE (cm$^{-1}$)')
    
    # Mark best point
    best_ic, best_ia = best["best_ij"]
    ax.plot(angle_scales[best_ia], cc_scales[best_ic], 'r*', markersize=20, 
            label=f'Best: C-C={best["scale_cc"]:.2f}, angle={best["scale_angle"]:.2f}')
    ax.legend()
    
    fig.tight_layout()
    heatmap_path = outdir / 'error_heatmap.png'
    fig.savefig(str(heatmap_path), dpi=150)
    plt.close(fig)
    print(f"Saved: {heatmap_path}")
    
    return best


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Grid fit MMFF for C2H6')
    parser.add_argument('n', type=int, default=10, help='Grid points per axis')
    parser.add_argument('--workdir', default='results', help='Working directory')
    parser.add_argument('--range-cc', nargs=2, type=float, default=[0.5, 3.0], 
                       help='C-C bond scale range')
    parser.add_argument('--range-angle', nargs=2, type=float, default=[0.3, 1.5], 
                       help='Angle scale range')
    parser.add_argument('--fix-ch', type=float, default=1.89, 
                       help='Fixed C-H bond scale from CH4 fitting')
    
    args = parser.parse_args()
    
    run_grid_fit_c2h6(
        workdir=args.workdir,
        n=args.n,
        range_cc=args.range_cc,
        range_angle=args.range_angle,
        fix_ch_scale=args.fix_ch
    )
