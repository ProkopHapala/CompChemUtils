#!/usr/bin/env python3
"""
Grid fit MMFF bond/angle stiffness for CH4 against QM reference.

Similar to phonon fitting but for isolated molecules (no k-space).
"""

import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from ase.build import molecule
from ase.io import read

from vib_store import load_method
from mmff_molecular_session import MMFFMolecularSession


def rmse_freqs(freqs_calc, freqs_ref):
    """Compute RMSE between calculated and reference frequencies."""
    # Sort both to match modes (they should already be sorted, but just in case)
    f_calc = np.sort(np.asarray(freqs_calc))
    f_ref = np.sort(np.asarray(freqs_ref))
    
    if len(f_calc) != len(f_ref):
        return np.inf
    
    return np.sqrt(np.mean((f_calc - f_ref)**2))


def run_grid_fit_ch4(workdir='results', n=10, range_bond=(0.5, 3.0), range_angle=(0.3, 1.5)):
    """
    Grid search over bond_scale and angle_scale to match pySCF frequencies.
    
    Args:
        workdir: results directory
        n: grid size (n x n points)
        range_bond: (min, max) bond stiffness scaling factors
        range_angle: (min, max) angle stiffness scaling factors
    """
    
    mol_name = 'CH4'
    
    # Load reference pySCF frequencies
    print("Loading pySCF reference...")
    ref_data = load_method(mol_name, 'pyscf_b3lyp_cc-pVDZ', workdir=workdir)
    freqs_ref = ref_data['mode_freqs']
    print(f"Reference: {len(freqs_ref)} modes, range {freqs_ref.min():.1f} - {freqs_ref.max():.1f} cm^-1")
    
    # Create grid
    bond_scales = np.linspace(float(range_bond[0]), float(range_bond[1]), int(n))
    angle_scales = np.linspace(float(range_angle[0]), float(range_angle[1]), int(n))
    
    print(f"\nGrid search: {n}x{n} = {n*n} points")
    print(f"  Bond scales: {bond_scales[0]:.3f} to {bond_scales[-1]:.3f}")
    print(f"  Angle scales: {angle_scales[0]:.3f} to {angle_scales[-1]:.3f}")
    
    errors = np.zeros((len(bond_scales), len(angle_scales)))
    
    best = {
        "rmse": np.inf,
        "scale_bond": None,
        "scale_angle": None,
        "freqs": None,
        "best_ij": None
    }
    
    # Reference atoms for geometry - use existing MMFF relaxed geometry
    ref_xyz = Path(workdir) / 'CH4' / 'mmff_angles' / 'relaxed.xyz'
    if ref_xyz.exists():
        atoms = read(str(ref_xyz))
        print(f"Using reference geometry from {ref_xyz}")
    else:
        atoms = molecule('CH4')
        print("Using ASE molecule('CH4') as reference geometry")
    
    # Initialize reusable MMFF session (once!)
    print("\nInitializing MMFF session...")
    symbols = atoms.get_chemical_symbols()
    positions = atoms.get_positions()
    masses = atoms.get_masses()
    
    total = len(bond_scales) * len(angle_scales)
    count = 0
    
    with MMFFMolecularSession(positions, symbols, enable_angles=True) as sess:
        print(f"Session initialized. Running {total} grid points...\n")
        
        for ib, sb in enumerate(bond_scales):
            for ia, sa in enumerate(angle_scales):
                count += 1
                
                # Scale parameters in-place (no reinit!)
                sess.set_scales(sb, sa)
                
                # Compute frequencies
                freqs, modes, hess = sess.compute_frequencies(masses)
                
                e = rmse_freqs(freqs, freqs_ref)
                errors[ib, ia] = e
                
                if e < best["rmse"]:
                    best.update({
                        "rmse": e,
                        "scale_bond": float(sb),
                        "scale_angle": float(sa),
                        "freqs": freqs.copy(),
                        "best_ij": (ib, ia)
                    })
                    print(f"[{count}/{total}] bond={sb:.3f} angle={sa:.3f} RMSE={e:.2f} cm^-1 *** NEW BEST ***")
                else:
                    print(f"[{count}/{total}] bond={sb:.3f} angle={sa:.3f} RMSE={e:.2f} cm^-1")
    
    # Save results
    outdir = Path(workdir) / 'CH4' / 'mmff_fit'
    outdir.mkdir(parents=True, exist_ok=True)
    
    np.savez(
        outdir / 'grid_errors.npz',
        bond_scales=bond_scales,
        angle_scales=angle_scales,
        errors=errors,
        best_scale_bond=best['scale_bond'],
        best_scale_angle=best['scale_angle'],
        best_rmse=best['rmse'],
        freqs_ref=freqs_ref,
        freqs_best=best['freqs']
    )
    
    # Print summary
    print(f"\n{'='*60}")
    print("Grid Fit Results")
    print(f"{'='*60}")
    print(f"Best RMSE: {best['rmse']:.2f} cm^-1")
    print(f"Optimal bond scale: {best['scale_bond']:.4f}")
    print(f"Optimal angle scale: {best['scale_angle']:.4f}")
    print(f"\nFrequencies comparison (cm^-1):")
    print(f"{'Mode':<6} {'Ref':<10} {'MMFF':<10} {'Diff':<10}")
    print('-' * 40)
    for i, (f_ref, f_calc) in enumerate(zip(freqs_ref, np.sort(best['freqs']))):
        print(f"{i+1:<6} {f_ref:<10.1f} {f_calc:<10.1f} {f_calc-f_ref:<+10.1f}")
    
    # Generate heatmap
    print(f"\nGenerating heatmap...")
    fig, ax = plt.subplots(figsize=(8, 6))
    
    # Mask inf values
    errors_plot = errors.copy()
    errors_plot[np.isinf(errors_plot)] = errors_plot[~np.isinf(errors_plot)].max() * 2
    
    im = ax.imshow(errors_plot, origin='lower', aspect='auto', cmap='viridis_r',
                   extent=[angle_scales[0], angle_scales[-1], bond_scales[0], bond_scales[-1]])
    
    ax.set_xlabel('Angle scale')
    ax.set_ylabel('Bond scale')
    ax.set_title(f'CH4 MMFF Fitting - RMSE (cm⁻¹)\nBest: bond={best["scale_bond"]:.3f}, angle={best["scale_angle"]:.3f}, RMSE={best["rmse"]:.1f}')
    
    cb = fig.colorbar(im, ax=ax)
    cb.set_label('RMSE (cm⁻¹)')
    
    # Mark best point
    if best['best_ij'] is not None:
        ib, ia = best['best_ij']
        ax.plot([angle_scales[ia]], [bond_scales[ib]], 'wo', ms=10, mec='red', mew=2)
    
    fig.tight_layout()
    heatmap_path = outdir / 'error_heatmap.png'
    fig.savefig(str(heatmap_path), dpi=200)
    plt.close(fig)
    print(f"Saved: {heatmap_path}")
    
    return best, errors, bond_scales, angle_scales


if __name__ == '__main__':
    import sys
    
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 15
    best, errors, bond_scales, angle_scales = run_grid_fit_ch4(n=n)
    print(f"\nDone! Best: bond_scale={best['scale_bond']:.4f}, angle_scale={best['scale_angle']:.4f}")
