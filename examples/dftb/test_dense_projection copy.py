#!/usr/bin/env python3
"""
test_dense_projection.py

Test dense-matrix projection methods vs old sparse methods for sp-only systems.
Uses point evaluation (orb2points/density2points style) for easy comparison.
Generates plots comparing dense vs sparse methods.

This validates that the new dense kernels produce identical results to the old
sparse kernels for systems without d-orbitals.

For systems with d-orbitals (e.g., Br with 3ob-3-1 basis), sparse comparison
is skipped and only dense projection is performed.

Usage:
    python test_dense_projection.py --dftb-dir tests/tAFM/pyocl_fdbm/test_pentacene_mio/dftb_work --plot
    python test_dense_projection.py --dftb-dir tests/tAFM/pyocl_fdbm/test_TBTAP_3mols_c3h_F_3ob/dftb_work --basis 3ob-3-1 --z-offset 1.5 --plot
"""

import sys, os, argparse
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from pyBall.DFTB.DFTBplusParser import (parse_basis_hsd_ang, parse_detailed_xml_custom, 
                                         parse_eigenvec_bin_custom, evec_to_kernel_coeffs,
                                         parse_wfc_hsd, convert_wfc_to_species_list_ang)
from pyBall.DFTB.Grid_dftb import GridProjector, setup_gridprojector_from_dftb
from pyBall.DFTB.TestUtils import generate_2d_point_grid
from pyBall.plotUtils import plot_comparison_2d
from pyBall.FireballOCL.STM_utils import plot_orbital_comparison

BOHR2ANG = 0.5291772109

def parse_args():
    p = argparse.ArgumentParser(description='Test dense vs sparse projection',formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument('--dftb-dir', type=str, default=None,help='DFTB+ run dir containing detailed.xml, eigenvec.bin (default: auto-selected based on basis)')
    p.add_argument('--basis', type=str, default='mio-1-1', choices=['mio-1-1', '3ob-3-1'],help='Basis set to use (mio-1-1 or 3ob-3-1)')
    p.add_argument('--basis-path', type=str, default=None, help='Path to basis files (default: pyBall/DFTB/data/)')
    p.add_argument('--tol', type=float, default=1e-6,  help='Tolerance for comparing dense vs sparse results')
    p.add_argument('--step', type=float, default=0.1,  help='Grid step in Angstrom for 2D plots (default: 0.1)')
    p.add_argument('--z-offset', type=float, default=2.0, help='Z offset in Angstrom for XY plane (default: 2.0)')
    p.add_argument('--no-plot', action='store_true', help='Disable plot generation (default: plots enabled)')
    p.add_argument('--output-dir', type=str, default=None,   help='Output directory for plots (default: same as dftb-dir)')
    p.add_argument('--dpi', type=int, default=150,help='DPI for output images (default: 150)')
    return p.parse_args()


def main():
    args = parse_args()
    
    # Auto-select dftb-dir if not provided
    if args.dftb_dir is None:
        if args.basis == 'mio-1-1':
            dftb_dir = REPO_ROOT / 'tests/tAFM/pyocl_fdbm/test_pentacene_mio/dftb_work'
        elif args.basis == '3ob-3-1':
            dftb_dir = REPO_ROOT / 'tests/tAFM/pyocl_fdbm/test_TBTAP_3mols_c3h_F_3ob/dftb_work'
        else:
            raise RuntimeError(f"Cannot auto-select dftb-dir for basis {args.basis}")
        print(f"Auto-selected dftb-dir: {dftb_dir}")
    else:
        dftb_dir = Path(args.dftb_dir)
    
    output_dir = Path(args.output_dir) if args.output_dir else dftb_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 70)
    print("Dense vs Sparse Projection Test")
    print("=" * 70)
    
    # Check required files
    detailed_xml = dftb_dir / 'detailed.xml'
    eigenvec_bin = dftb_dir / 'eigenvec.bin'
    
    if not detailed_xml.exists():
        raise RuntimeError(f"detailed.xml not found in {dftb_dir}")
    if not eigenvec_bin.exists():
        raise RuntimeError(f"eigenvec.bin not found in {dftb_dir}")
    
    print(f"\nLoading data from {dftb_dir}")
    
    # Parse detailed.xml
    print("  Parsing detailed.xml...")
    detailed = parse_detailed_xml_custom(detailed_xml)
    coords_bohr = detailed['coords_bohr']
    species_per_atom = detailed['species_per_atom']
    species_names = detailed['species_names']
    natoms = len(coords_bohr)
    nstates = detailed['nstates']
    norb_total = detailed['norb']
    
    # Parse eigenvectors
    print("  Parsing eigenvec.bin...")
    evecs = parse_eigenvec_bin_custom(eigenvec_bin, nstates, norb_total)  # (nStates, nOrb)
    print(f"    nStates={nstates}, nOrb={norb_total}")
    
    # Load real basis from wfc file
    if args.basis_path is None:
        basis_path = REPO_ROOT / 'pyBall/DFTB/data' / f'wfc.{args.basis}.hsd'
    else:
        basis_path = Path(args.basis_path) / f'wfc.{args.basis}.hsd'
    
    print(f"  Loading basis from {basis_path}")
    basis_data = parse_wfc_hsd(str(basis_path))
    basis = convert_wfc_to_species_list_ang(basis_data, resolution_bohr=0.04)
    print(f"  Loaded {len(basis)} species: {[sp['name'] for sp in basis]}")
    
    # Detect if any atom in the system requires d-orbitals (l=2)
    sp_by_name = {sp['name']: sp for sp in basis}
    has_d_orbitals = False
    max_l = 0
    for ia in range(natoms):
        sp_name = species_names[species_per_atom[ia]]
        sp_info = sp_by_name[sp_name]
        for orb in sp_info['orbitals']:
            max_l = max(max_l, orb['l'])
            if orb['l'] == 2:
                has_d_orbitals = True
    
    if has_d_orbitals:
        print(f"  ⚠️  System contains d-orbitals (max_l={max_l})")
        print(f"     Sparse comparison will be skipped.")
    
    # Determine max_shells and whether to use sparse comparison
    max_shells = 3 if has_d_orbitals else 2
    use_sparse = not has_d_orbitals  # Sparse method only supports sp (max_shells=2)
    
    dftb_data = {
        'coords_bohr': coords_bohr,
        'species_per_atom': species_per_atom,
        'species_names': species_names,
    }
    
    if use_sparse:
        # Build projector with max_shells=2 (sp only, for old sparse method)
        print(f"\nSetting up projector (sparse, max_shells=2)...")
        projector_sparse, atoms_dict = setup_gridprojector_from_dftb( dftb_data, basis, verbosity=1, max_shells=2 )
        
        # Build projector with max_shells=2 (for dense method on sp system)
        print("Setting up projector (dense, max_shells=2)...")
        projector_dense, _ = setup_gridprojector_from_dftb(  dftb_data, basis, verbosity=1, max_shells=2 )
    else:
        print(f"\nSetting up projector (dense-only, max_shells={max_shells})...")
        projector_dense, atoms_dict = setup_gridprojector_from_dftb( dftb_data, basis, verbosity=1, max_shells=max_shells )
        projector_sparse = None  # No sparse comparison for d-orbitals
    
    # Compute norb_per_atom and orb_offsets for dense method
    norb_per_atom = []
    for ia in range(natoms):
        sp_name = species_names[species_per_atom[ia]]
        sp_info = sp_by_name[sp_name]
        norb = sum(2*orb['l']+1 for orb in sp_info['orbitals'])
        norb_per_atom.append(norb)
    norb_per_atom = np.array(norb_per_atom, dtype=np.int32)
    orb_offsets = np.zeros(natoms + 1, dtype=np.int32)
    orb_offsets[1:] = np.cumsum(norb_per_atom)
    
    print(f"  norb_per_atom: {norb_per_atom}")
    print(f"  orb_offsets: {orb_offsets}")
    print(f"  norb_total: {orb_offsets[-1]}")
    print(f"  max_l: {max_l}")
    
    # Generate 2D grid for visualization (XY plane at fixed Z offset)
    coords_ang = coords_bohr * BOHR2ANG
    rmin = coords_ang.min() - 2.0
    rmax = coords_ang.max() + 2.0
    range_size = rmax - rmin
    ngrid = int(np.ceil(range_size / args.step))
    
    print(f"\nGenerating 2D XY grid (step={args.step} Å, z-offset={args.z_offset} Å)")
    print(f"  Range: [{rmin:.2f}, {rmax:.2f}] Å")
    print(f"  Grid size: {ngrid}x{ngrid}")
    
    # Use library function for grid generation
    points, extent = generate_2d_point_grid(plane='xy', npoints=ngrid, z_offset=args.z_offset, xy_range=(rmin, rmax))
    points = points.astype(np.float32)
    
    # Determine number of occupied orbitals from occupations
    occupations = detailed.get('occupations')
    if occupations is not None:
        # occupations shape: (nstates, nkpoints, nspin)
        occ_1d = occupations[:, 0, 0]  # First k-point, first spin
        nocc = int(np.sum(occ_1d > 0.5))  # Count orbitals with occupation > 0.5
        print(f"\nDetected {nocc} occupied orbitals from detailed.xml")
    else:
        # Fallback: assume closed-shell with all electrons paired
        # For systems with Br (35 e-), total electrons = sum of valence electrons
        # This is a rough estimate; better to get from occupations
        nocc = nstates // 2  # Rough estimate
        print(f"\nWarning: occupations not found, estimating {nocc} occupied orbitals")
    
    # Select MOs to test: HOMO-1, HOMO, LUMO (or just a few around HOMO)
    homo_idx = nocc - 1
    mo_indices = [max(0, homo_idx-1), homo_idx, min(nstates-1, homo_idx+1)]
    
    print(f"\nTesting orbital projection for MOs {mo_indices} (around HOMO={homo_idx})")
    print("-" * 70)
    
    max_orb_diff = 0.0
    orb_results = {}  # Store results for plotting
    for imo in mo_indices:
        if imo >= nstates or imo < 0:
            print(f"  Skipping MO{imo+1} (index out of range)")
            continue
        
        # NEW: dense method
        coeffs_dense = evecs[imo].astype(np.float32)
        psi_dense = projector_dense.project_orbital_dense_points(  points, coeffs_dense, norb_per_atom, orb_offsets, atoms_dict )
        
        if use_sparse:
            # OLD: sparse method (only for sp-only systems)
            coeffs_sparse = evec_to_kernel_coeffs(  evecs[imo], natoms, species_per_atom, species_names, basis  )
            psi_sparse = projector_sparse.project_orbital_points(  points, coeffs_sparse, norb_per_atom, atoms_dict    )
            
            # Compare
            diff = np.max(np.abs(psi_sparse - psi_dense))
            max_orb_diff = max(max_orb_diff, diff)
            print(f"  MO{imo+1}: max|diff| = {diff:.2e}")
            
            if diff > args.tol:
                print(f"    WARNING: difference exceeds tolerance {args.tol}")
                print(f"    sparse: mean={psi_sparse.mean():.2e}, std={psi_sparse.std():.2e}")
                print(f"    dense:  mean={psi_dense.mean():.2e}, std={psi_dense.std():.2e}")
            
            # Store for plotting
            orb_results[imo] = {
                'sparse': psi_sparse,
                'dense': psi_dense,
                'diff': psi_sparse - psi_dense
            }
        else:
            # Dense-only mode (d-orbitals present)
            print(f"  MO{imo+1}: dense projection computed")
            orb_results[imo] = {
                'dense': psi_dense
            }
    
    # Test density projection
    print(f"\nTesting density projection")
    print("-" * 70)
    
    # Build density matrix from occupied orbitals
    dm_dense = np.zeros((norb_total, norb_total), dtype=np.float32)
    for iocc in range(nocc):
        c = evecs[iocc].astype(np.float32)
        dm_dense += np.outer(c, c)
    
    # NEW: dense method using density matrix
    rho_dense_dm = projector_dense.project_density_dense_points( points, dm_dense, norb_per_atom, orb_offsets, atoms_dict )
    
    # Also compute sum of orbitals with dense method for comparison
    rho_dense_sum = np.zeros(len(points), dtype=np.float32)
    for iocc in range(nocc):
        coeffs_dense = evecs[iocc].astype(np.float32)
        psi = projector_dense.project_orbital_dense_points(points, coeffs_dense, norb_per_atom, orb_offsets, atoms_dict  )
        rho_dense_sum += psi ** 2
    
    # Compare
    diff_sum_dm = np.max(np.abs(rho_dense_sum - rho_dense_dm))
    print(f"  dense sum vs dense DM: max|diff| = {diff_sum_dm:.2e}")
    
    if use_sparse:
        # OLD: sparse method uses sum of orbitals (no direct density projection in old code)
        rho_sparse = np.zeros(len(points), dtype=np.float32)
        for iocc in range(nocc):
            coeffs_sparse = evec_to_kernel_coeffs(evecs[iocc], natoms, species_per_atom, species_names, basis )
            psi = projector_sparse.project_orbital_points( points, coeffs_sparse, norb_per_atom, atoms_dict )
            rho_sparse += psi ** 2
        
        diff_sparse_dense = np.max(np.abs(rho_sparse - rho_dense_sum))
        print(f"  sparse vs dense sum: max|diff| = {diff_sparse_dense:.2e}")
        
        # Store density results for plotting
        density_results = {
            'sparse': rho_sparse,
            'dense_sum': rho_dense_sum,
            'dense_dm': rho_dense_dm,
            'diff_sparse_dense': rho_sparse - rho_dense_sum,
            'diff_sum_dm': rho_dense_sum - rho_dense_dm
        }
    else:
        diff_sparse_dense = 0.0  # Not applicable
        density_results = {
            'dense_sum': rho_dense_sum,
            'dense_dm': rho_dense_dm,
            'diff_sum_dm': rho_dense_sum - rho_dense_dm
        }
    
    # Generate plots if requested
    if not args.no_plot:
        print("\nGenerating plots...")
        
        # Reshape 1D point data to 2D grid for imshow
        def to_grid(data_1d, ngrid):
            return data_1d.reshape(ngrid, ngrid)
        
        plane_desc = f'XY plane  z={args.z_offset:.3f} Å'
        title_prefix = f'{args.basis} basis'
        
        if use_sparse:
            # Prepare data for plot_comparison_2d (sparse vs dense)
            nstates_plot = len(mo_indices)
            sparse_vals = np.zeros((nstates_plot, ngrid, ngrid))
            dense_vals = np.zeros((nstates_plot, ngrid, ngrid))
            diff_vals = np.zeros((nstates_plot, ngrid, ngrid))
            energies = []
            for i, imo in enumerate(mo_indices):
                if imo not in orb_results:
                    continue
                res = orb_results[imo]
                sparse_vals[i] = to_grid(res['sparse'], ngrid)
                dense_vals[i] = to_grid(res['dense'], ngrid)
                diff_vals[i] = to_grid(res['diff'], ngrid)
                energies.append(0.0)
            
            homo = mo_indices[-1]
            
            # Use library function for orbital comparison
            plot_path = output_dir / 'orbital_comparison.png'
            plot_comparison_2d(sparse_vals, dense_vals, diff_vals, extent, title_prefix, plane_desc, 'orb2points', mo_indices, energies, homo, plot_path, dpi=args.dpi, atom_coords=coords_ang)
            print(f"  Saved: {plot_path}")
            
            # Plot density comparisons using library function
            rho_sparse_grid = to_grid(density_results['sparse'], ngrid)
            rho_dense_sum_grid = to_grid(density_results['dense_sum'], ngrid)
            rho_diff_grid = to_grid(density_results['diff_sparse_dense'], ngrid)
            
            density_sparse_vals = rho_sparse_grid[np.newaxis, :, :]
            density_dense_vals = rho_dense_sum_grid[np.newaxis, :, :]
            density_diff_vals = rho_diff_grid[np.newaxis, :, :]
            
            plot_path = output_dir / 'density_comparison.png'
            plot_comparison_2d(density_sparse_vals, density_dense_vals, density_diff_vals, extent, title_prefix, plane_desc, 'density2points', [0], [0.0], 0, plot_path, dpi=args.dpi, atom_coords=coords_ang)
            print(f"  Saved: {plot_path}")
        else:
            # Dense-only mode: plot dense results directly
            fig, axes = plt.subplots(1, len(mo_indices), figsize=(5*len(mo_indices), 4))
            if len(mo_indices) == 1:
                axes = [axes]
            
            for i, imo in enumerate(mo_indices):
                if imo not in orb_results:
                    continue
                psi_grid = to_grid(orb_results[imo]['dense'], ngrid)
                vmax = np.max(np.abs(psi_grid))
                im = axes[i].imshow(psi_grid, origin='lower', extent=extent, cmap='RdBu_r', vmin=-vmax, vmax=vmax)
                axes[i].set_title(f'MO{imo+1} (dense)')
                axes[i].set_xlabel('X (Å)')
                axes[i].set_ylabel('Y (Å)')
                plt.colorbar(im, ax=axes[i])
                axes[i].scatter(coords_ang[:, 0], coords_ang[:, 1], c='black', marker='o', s=20, alpha=0.5, zorder=10)
            
            plt.suptitle(f'Dense Orbital Projection ({title_prefix}, {plane_desc})', fontsize=14)
            plt.tight_layout()
            plot_path = output_dir / 'orbital_comparison.png'
            plt.savefig(plot_path, dpi=args.dpi)
            print(f"  Saved: {plot_path}")
            plt.close()
            
            # Density plot
            fig, axes = plt.subplots(1, 2, figsize=(12, 5))
            
            rho_sum_grid = to_grid(density_results['dense_sum'], ngrid)
            rho_dm_grid = to_grid(density_results['dense_dm'], ngrid)
            
            vmax = max(rho_sum_grid.max(), rho_dm_grid.max())
            
            im0 = axes[0].imshow(rho_sum_grid, origin='lower', extent=extent, cmap='viridis', vmin=0, vmax=vmax)
            axes[0].set_title('Density (sum of orbitals)')
            axes[0].set_xlabel('X (Å)')
            axes[0].set_ylabel('Y (Å)')
            plt.colorbar(im0, ax=axes[0])
            
            im1 = axes[1].imshow(rho_dm_grid, origin='lower', extent=extent, cmap='viridis', vmin=0, vmax=vmax)
            axes[1].set_title('Density (from DM)')
            axes[1].set_xlabel('X (Å)')
            axes[1].set_ylabel('Y (Å)')
            plt.colorbar(im1, ax=axes[1])
            
            for ax in axes:
                ax.scatter(coords_ang[:, 0], coords_ang[:, 1], c='black', marker='o', s=20, alpha=0.5, zorder=10)
            
            plt.suptitle(f'Dense Density Projection ({title_prefix}, {plane_desc})', fontsize=14)
            plt.tight_layout()
            plot_path = output_dir / 'density_comparison.png'
            plt.savefig(plot_path, dpi=args.dpi)
            print(f"  Saved: {plot_path}")
            plt.close()
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    if use_sparse:
        print(f"  Mode: Dense + Sparse comparison")
        print(f"  Max orbital difference: {max_orb_diff:.2e}")
        print(f"  Max density difference (sparse vs dense sum): {diff_sparse_dense:.2e}")
        print(f"  Max density difference (dense sum vs dense DM): {diff_sum_dm:.2e}")
        
        if max_orb_diff < args.tol and diff_sparse_dense < args.tol and diff_sum_dm < args.tol:
            print("\n✓ All tests PASSED within tolerance")
            return 0
        else:
            print(f"\n✗ Some tests FAILED (tolerance = {args.tol})")
            return 1
    else:
        print(f"  Mode: Dense-only (d-orbitals detected, max_l=2)")
        print(f"  Max density difference (dense sum vs dense DM): {diff_sum_dm:.2e}")
        print(f"  Dense-only projection completed successfully")
        return 0


if __name__ == '__main__':
    sys.exit(main())
