#!/usr/bin/env python3
"""
plot_mp_diamond.py
==================
Overlay Materials Project DFT phonon data for diamond with our calculations.

Usage:
  python plot_mp_diamond.py --output plots/diamond_with_mp.png
"""

import argparse
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plot_phonon_benchmark import read_phonopy_band_yaml


def read_mp_dat(path):
    """Read MP phonon data from custom .dat file."""
    qpts = []
    dists = []
    freqs = []
    labels = []
    with open(path) as f:
        header = next(f)  # skip header
        # Count frequency columns from header
        n_bands = 6  # diamond has 6 bands
        for line in f:
            parts = line.strip().split()
            if len(parts) < 4 + n_bands:
                continue
            qpts.append([float(parts[0]), float(parts[1]), float(parts[2])])
            dists.append(float(parts[3]))
            band_freqs = [float(parts[4 + i]) for i in range(n_bands)]
            freqs.append(band_freqs)
            # Label is anything after the frequency columns that isn't a number
            label = ''
            if len(parts) > 4 + n_bands:
                label = parts[-1] if not parts[-1].replace('.', '', 1).replace('-', '', 1).isdigit() else ''
            labels.append(label)
    return np.array(qpts), np.array(dists), np.array(freqs), labels


def interpolate_onto_path(qpts_target, qpts_src, freqs_src):
    """Interpolate source frequencies onto target q-points (frac coords)."""
    # For each target q, find nearest source q in fractional space
    # (periodic boundary conditions)
    freqs_interp = []
    for qt in qpts_target:
        # Minimum image convention for distance
        dq = qpts_src - qt
        dq -= np.round(dq)  # wrap to [-0.5, 0.5]
        dists = np.linalg.norm(dq, axis=1)
        idx = np.argmin(dists)
        freqs_interp.append(freqs_src[idx])
    return np.array(freqs_interp)


def plot_diamond_mp_comparison(output, mp_path="mp_diamond_phonon_bands.dat",
                                  results_dir="phonon_results"):
    fig, ax = plt.subplots(figsize=(10, 6))

    # Load MP DFT data (reference)
    mp_qpts, mp_dists, mp_freqs, mp_labels = read_mp_dat(mp_path)
    print(f"[plot] MP data: {len(mp_qpts)} q-points, {mp_freqs.shape[1]} bands")

    # Plot MP DFT reference
    for i in range(mp_freqs.shape[1]):
        ax.plot(mp_dists, mp_freqs[:, i], color="gray", alpha=0.5, lw=1.0, ls="--")
    ax.plot([], [], color="gray", ls="--", label="DFT reference (Materials Project)", lw=2)

    # Load our computed bands and interpolate onto MP path
    colors = {
        "dftb": "tab:red",
        "tersoff": "tab:orange",
        "sw": "tab:blue",
        "meam": "tab:green",
    }

    for name in sorted(os.listdir(results_dir)):
        if not name.startswith("diamond_"):
            continue
        subdir = os.path.join(results_dir, name)
        if not os.path.isdir(subdir):
            continue
        band_yaml = os.path.join(subdir, "band.yaml")
        if not os.path.exists(band_yaml):
            continue

        label = name.replace("diamond_", "").replace("_2x2x2", "")
        try:
            dist, freqs, labels = read_phonopy_band_yaml(band_yaml)
        except Exception as e:
            print(f"WARNING: Could not read {band_yaml}: {e}")
            continue

        # Need to reconstruct q-points from band.yaml for interpolation
        import yaml
        with open(band_yaml) as f:
            data = yaml.safe_load(f)
        our_qpts = np.array([p["q-position"] for p in data["phonon"]])

        # Interpolate our frequencies onto MP q-points
        interp_freqs = interpolate_onto_path(mp_qpts, our_qpts, freqs)

        color = colors.get(label.split("_")[0], None)
        if color is None:
            import hashlib
            hue = int(hashlib.md5(label.encode()).hexdigest(), 16) % 360 / 360.0
            from matplotlib.colors import hsv_to_rgb
            color = hsv_to_rgb([hue, 0.7, 0.8])

        for i in range(interp_freqs.shape[1]):
            ax.plot(mp_dists, interp_freqs[:, i], color=color, alpha=0.7, lw=1.2)
        ax.plot([], [], color=color, label=label.replace("_", " "), lw=2)

    # Extract labels from MP data
    label_positions = []
    seen = set()
    for i, lab in enumerate(mp_labels):
        if lab and lab not in seen:
            label_positions.append((mp_dists[i], lab))
            seen.add(lab)

    if label_positions:
        tick_pos = [x[0] for x in label_positions]
        tick_lab = [x[1] for x in label_positions]
        ax.set_xticks(tick_pos)
        ax.set_xticklabels(tick_lab, fontsize=11)

    ax.set_ylabel("Frequency (THz)", fontsize=12)
    ax.set_xlabel("Wave Vector", fontsize=12)
    ax.axhline(0, color="black", lw=0.5)
    ax.set_ylim(bottom=0)
    ax.legend(loc="upper right", fontsize=9)
    ax.grid(axis="y", alpha=0.3)
    ax.set_title("Phonon Dispersion: Diamond (interpolated to MP path)", fontsize=13)

    plt.tight_layout()
    plt.savefig(output, dpi=300)
    print(f"[plot] Saved comparison to {output}")


def main():
    parser = argparse.ArgumentParser(description="Plot diamond phonons with MP DFT reference")
    parser.add_argument("--mp-data", default="mp_diamond_phonon_bands.dat")
    parser.add_argument("--results-dir", default="phonon_results")
    parser.add_argument("--output", default="plots/diamond_with_mp.png")
    args = parser.parse_args()
    plot_diamond_mp_comparison(args.output, args.mp_data, args.results_dir)


if __name__ == "__main__":
    main()
