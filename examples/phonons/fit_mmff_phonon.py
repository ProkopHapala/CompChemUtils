#!/usr/bin/env python3
"""
Simple stiffness scaling fit for MMFF phonon bands.

Two methods:
  1. optical-gamma: Match highest optical frequency at Gamma point.
  2. acoustic-slope: Match acoustic band frequency at a small fraction
     of the Gamma->X distance (default 10%).

Physics: omega ~ sqrt(K/m)  =>  K_new = K_old * (f_ref / f_current)^2

Usage:
    python fit_mmff_phonon.py --method optical-gamma --structure structures/diamond.xyz --supercell 3 3 3
    python fit_mmff_phonon.py --method acoustic-slope --frac 0.10 --band la --structure structures/diamond.xyz
"""

import argparse
import sys
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from export_phonon_html import read_mp_dat
from run_phonon import run_phonon, ensure_mmff_runtime, load_config
from phonon_utils import QPath


def find_gamma_index(labels):
    """Find index of first Gamma point."""
    for i, lab in enumerate(labels):
        l = str(lab).strip()
        if l in ('Gamma', 'GAMMA', 'Γ', 'G'):
            return i
    return None


def find_point_at_fraction(dists, labels, start_label, end_label, frac):
    """Find index closest to fraction along the FIRST matching segment."""
    # Find all segment boundaries
    labeled_indices = [(i, str(lab).strip()) for i, lab in enumerate(labels) if str(lab).strip()]

    start_idx = None
    end_idx = None
    for i, (idx, lab) in enumerate(labeled_indices):
        if lab == start_label:
            # Look for the next occurrence of end_label
            for j in range(i + 1, len(labeled_indices)):
                if labeled_indices[j][1] == end_label:
                    start_idx = idx
                    end_idx = labeled_indices[j][0]
                    break
        if start_idx is not None:
            break

    if start_idx is None or end_idx is None:
        raise ValueError(f"Could not find segment {start_label} -> {end_label}")
    target_dist = dists[start_idx] + frac * (dists[end_idx] - dists[start_idx])
    best_idx = min(range(start_idx, end_idx + 1), key=lambda i: abs(dists[i] - target_dist))
    return best_idx


def compute_scale_factor(ref_freqs, calc_freqs, band='top', verbose=True):
    """Compute stiffness scaling factor from frequency ratio.

    band: 'top' (highest), 'bottom' (lowest), 'la' (highest of bottom 3),
          'ta' (lowest of bottom 3), or integer index.
    """
    ref = np.asarray(ref_freqs)
    calc = np.asarray(calc_freqs)
    assert len(ref) == len(calc), f"Band count mismatch: {len(ref)} vs {len(calc)}"

    # Sort by frequency for consistent band indexing
    ref_sorted = np.sort(ref)
    calc_sorted = np.sort(calc)

    n = len(ref_sorted)
    if band == 'top':
        idx = n - 1
    elif band == 'bottom':
        idx = 0
    elif band == 'la':
        # Highest acoustic = max of bottom half
        idx = n // 2 - 1  # for 6 bands, idx=2 (0,1,2 are acoustic-ish)
    elif band == 'ta':
        idx = 0
    elif isinstance(band, int):
        idx = band
    else:
        raise ValueError(f"Unknown band selector: {band}")

    f_ref = ref_sorted[idx]
    f_calc = calc_sorted[idx]

    # Use absolute values (some may be tiny negative from numerical noise)
    f_ref = abs(f_ref)
    f_calc = abs(f_calc)

    if f_calc < 1e-6:
        raise ValueError(f"Calculated frequency at band {idx} is ~zero, cannot scale")

    scale = (f_ref / f_calc) ** 2

    if verbose:
        print(f"  [fit] band={band} (sorted idx={idx}): ref={f_ref:.4f} THz, calc={f_calc:.4f} THz")
        print(f"  [fit] freq ratio f_ref/f_calc = {f_ref/f_calc:.4f}")
        print(f"  [fit] stiffness scale = (ratio)^2 = {scale:.4f}")

    return scale


def fit_mmff(
    structure_path,
    ref_path,
    fit_method,
    supercell,
    outdir_base,
    config,
    frac=0.10,
    band='top',
    segment=('Gamma', 'X'),
    mmff_enable_angles=False,
    mmff_use_uff=False,
):
    """Run MMFF, compute scale factor from reference, re-run with scaled stiffness."""

    # --- Step 1: Load reference data ---
    print(f"\n{'='*60}")
    print(f"[fit] Loading reference: {ref_path}")
    ref_data = read_mp_dat(ref_path)
    ref_freqs = np.array(ref_data['frequencies'])
    ref_dists = np.array(ref_data['distances'])
    ref_labels = ref_data['labels']

    # --- Step 2: Identify comparison point ---
    if fit_method == 'optical-gamma':
        comp_idx = find_gamma_index(ref_labels)
        if comp_idx is None:
            raise ValueError("Gamma point not found in reference")
        print(f"\n[fit] Method: optical-gamma")
        print(f"[fit] Comparison point: Gamma (idx={comp_idx}, dist={ref_dists[comp_idx]:.4f})")
        band_selector = 'top'
    elif fit_method == 'acoustic-slope':
        start_lab, end_lab = segment
        comp_idx = find_point_at_fraction(ref_dists, ref_labels, start_lab, end_lab, frac)
        print(f"\n[fit] Method: acoustic-slope")
        print(f"[fit] Segment: {start_lab} -> {end_lab}, fraction={frac}")
        print(f"[fit] Comparison point: idx={comp_idx}, dist={ref_dists[comp_idx]:.4f}")
        band_selector = band
    else:
        raise ValueError(f"Unknown fit method: {fit_method}")

    ref_point_freqs = ref_freqs[comp_idx]
    print(f"[fit] Reference frequencies at comparison point: {ref_point_freqs}")

    # --- Step 3: Run initial MMFF calculation ---
    print(f"\n{'='*60}")
    print("[fit] Step 1: Running MMFF with DEFAULT parameters")
    outdir_default = Path(outdir_base) / f"fit_default_{fit_method}"
    qpath = QPath.from_file(ref_path)

    freqs_default, dists_default, labels_default = run_phonon(
        structure_path=structure_path,
        method='mmff',
        qpath=qpath,
        supercell=supercell,
        outdir=outdir_default,
        config=config,
        mmff_enable_angles=True,  # Enable angles (user requirement)
        mmff_use_uff=mmff_use_uff,
        force_recompute=True,
    )

    # Get frequencies at comparison point
    calc_point_freqs = freqs_default[comp_idx]
    print(f"\n[fit] MMFF default frequencies at comparison point: {calc_point_freqs}")

    # --- Step 4: Compute scaling factor ---
    print(f"\n{'='*60}")
    print("[fit] Step 2: Computing stiffness scale factor")
    scale = compute_scale_factor(ref_point_freqs, calc_point_freqs, band=band_selector, verbose=True)

    # --- Step 5: Run scaled MMFF calculation ---
    print(f"\n{'='*60}")
    print(f"[fit] Step 3: Re-running MMFF with scale_bond={scale:.4f}, scale_angle={scale:.4f}")
    outdir_scaled = Path(outdir_base) / f"fit_scaled_{fit_method}_{scale:.3f}"

    freqs_scaled, dists_scaled, labels_scaled = run_phonon(
        structure_path=structure_path,
        method='mmff',
        qpath=qpath,
        supercell=supercell,
        outdir=outdir_scaled,
        config=config,
        mmff_enable_angles=True,  # Enable angles for fitting (user requirement)
        mmff_use_uff=mmff_use_uff,
        mmff_scale_bond=scale,
        mmff_scale_angle=scale,  # Scale both bonds and angles by same factor
        force_recompute=True,
    )

    scaled_point_freqs = freqs_scaled[comp_idx]
    print(f"\n[fit] MMFF scaled frequencies at comparison point: {scaled_point_freqs}")

    # --- Step 6: Summary ---
    print(f"\n{'='*60}")
    print("[fit] SUMMARY")
    print(f"  Method:          {fit_method}")
    print(f"  Comparison idx:  {comp_idx}")
    print(f"  Ref freqs:       {ref_point_freqs}")
    print(f"  Default freqs:   {calc_point_freqs}")
    print(f"  Scaled freqs:    {scaled_point_freqs}")
    print(f"  Scale factor:    {scale:.4f}")
    print(f"  Default outdir:  {outdir_default}")
    print(f"  Scaled outdir:   {outdir_scaled}")

    return {
        'scale': scale,
        'fit_method': fit_method,
        'comp_idx': comp_idx,
        'ref_freqs': ref_point_freqs,
        'default_freqs': calc_point_freqs,
        'scaled_freqs': scaled_point_freqs,
        'outdir_default': outdir_default,
        'outdir_scaled': outdir_scaled,
        'freqs_default': freqs_default,
        'freqs_scaled': freqs_scaled,
        'dists': dists_default,
        'labels': labels_default,
    }


def main():
    parser = argparse.ArgumentParser(description="Simple MMFF stiffness scaling fit")
    parser.add_argument("--structure", required=True, help="Structure file (.cif or .xyz)")
    parser.add_argument("--ref", default="mp_diamond_phonon_bands.dat",
                        help="Reference phonon .dat file (Materials Project format)")
    parser.add_argument("--method", choices=["optical-gamma", "acoustic-slope"],
                        default="optical-gamma", help="Fitting target")
    parser.add_argument("--supercell", nargs=3, type=int, default=[3, 3, 3],
                        help="Supercell dimensions")
    parser.add_argument("--outdir", default="fit_results",
                        help="Base output directory")
    parser.add_argument("--config", default="phonon_config.json",
                        help="Config file with tool paths")
    parser.add_argument("--frac", type=float, default=0.10,
                        help="Fraction along segment for acoustic-slope method")
    parser.add_argument("--band", default="top",
                        choices=["top", "bottom", "la", "ta"],
                        help="Which band to match for acoustic-slope")
    parser.add_argument("--segment-start", default="Gamma",
                        help="Start label for acoustic-slope segment")
    parser.add_argument("--segment-end", default="X",
                        help="End label for acoustic-slope segment")
    parser.add_argument("--mmff-enable-angles", action="store_true",
                        help="Enable MMFF angle forces")
    parser.add_argument("--mmff-use-uff", action="store_true",
                        help="Use UFF instead of MMFF")
    args = parser.parse_args()

    ensure_mmff_runtime()
    config = load_config(args.config)

    result = fit_mmff(
        structure_path=args.structure,
        ref_path=args.ref,
        fit_method=args.method,
        supercell=args.supercell,
        outdir_base=args.outdir,
        config=config,
        frac=args.frac,
        band=args.band,
        segment=(args.segment_start, args.segment_end),
        mmff_enable_angles=args.mmff_enable_angles,
        mmff_use_uff=args.mmff_use_uff,
    )

    print(f"\n[fit] Done. Scale factor = {result['scale']:.4f}")


if __name__ == "__main__":
    main()
