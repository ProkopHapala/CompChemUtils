#!/usr/bin/env python3
"""
plot_comparison.py
====================
Overlay phonon dispersion curves from multiple calculations with experimental data.

Usage:
  python plot_comparison.py --material Si --output plots/Si_comparison.png
  python plot_comparison.py --material diamond --output plots/diamond_comparison.png
"""

import argparse
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plot_phonon_benchmark import (
    read_phonopy_band_yaml, read_alamode_band_dat, read_experimental_json,
    match_exp_to_labels, normalize_labels, DEFAULT_LABEL_POS
)


def load_phonopy_results(results_dir, material):
    """Find all band.yaml files for a material in results_dir."""
    bands = {}
    if not os.path.isdir(results_dir):
        return bands
    for name in sorted(os.listdir(results_dir)):
        subdir = os.path.join(results_dir, name)
        if not os.path.isdir(subdir):
            continue
        if not name.startswith(material):
            continue
        band_yaml = os.path.join(subdir, "band.yaml")
        if os.path.exists(band_yaml):
            label = name.replace(f"{material}_", "").replace("_2x2x2", "")
            bands[label] = band_yaml
    return bands


def load_alamode_results(results_dir, material):
    """Find all .bands files for a material in results_dir."""
    bands = {}
    if not os.path.isdir(results_dir):
        return bands
    for name in sorted(os.listdir(results_dir)):
        subdir = os.path.join(results_dir, name)
        if not os.path.isdir(subdir):
            continue
        if not name.startswith(material):
            continue
        band_dat = os.path.join(subdir, f"{name}.bands")
        if os.path.exists(band_dat):
            label = name.replace(f"{material}_", "").replace("_2x2x2", "")
            bands[f"alamode_{label}"] = band_dat
    return bands


def plot_comparison(material, results_dir, exp_path, output, phonondb_ref=None, alamode_dir="alamode_results"):
    fig, ax = plt.subplots(figsize=(10, 6))

    colors = {
        "sw": "tab:blue",
        "tersoff": "tab:orange",
        "meam": "tab:green",
        "dftb": "tab:red",
    }

    all_label_positions = []
    plotted_any = False

    # Load phononDB DFT reference (high-quality theoretical reference)
    if phonondb_ref and os.path.exists(phonondb_ref):
        try:
            dist, freqs, labels = read_phonopy_band_yaml(phonondb_ref)
            for i in range(freqs.shape[1]):
                ax.plot(dist, freqs[:, i], color="gray", alpha=0.5, lw=1.0, ls="--")
            ax.plot([], [], color="gray", ls="--", label="DFT reference (phononDB)", lw=2)
            all_label_positions.extend(labels)
            plotted_any = True
        except Exception as e:
            print(f"WARNING: Could not read phononDB reference {phonondb_ref}: {e}")

    # Load computed bands
    bands = load_phonopy_results(results_dir, material)
    if not bands:
        print(f"WARNING: No band.yaml files found for {material} in {results_dir}")

    for label, band_yaml in sorted(bands.items()):
        try:
            dist, freqs, labels = read_phonopy_band_yaml(band_yaml)
        except Exception as e:
            print(f"WARNING: Could not read {band_yaml}: {e}")
            continue

        color = colors.get(label.split("_")[0], None)
        if color is None:
            # Generate color from hash
            import hashlib
            hue = int(hashlib.md5(label.encode()).hexdigest(), 16) % 360 / 360.0
            from matplotlib.colors import hsv_to_rgb
            color = hsv_to_rgb([hue, 0.7, 0.8])

        for i in range(freqs.shape[1]):
            ax.plot(dist, freqs[:, i], color=color, alpha=0.7, lw=1.2)
        ax.plot([], [], color=color, label=label.replace("_", " "), lw=2)
        all_label_positions.extend(labels)
        plotted_any = True

    # Load ALAMODE results
    alamode_bands = load_alamode_results(alamode_dir, material)
    for label, band_dat in sorted(alamode_bands.items()):
        try:
            dist, freqs = read_alamode_band_dat(band_dat)
        except Exception as e:
            print(f"WARNING: Could not read {band_dat}: {e}")
            continue
        color = "tab:purple"
        for i in range(freqs.shape[1]):
            ax.plot(dist, freqs[:, i], color=color, alpha=0.7, lw=1.2)
        ax.plot([], [], color=color, label=label.replace("_", " "), lw=2)
        plotted_any = True

    # Experimental points
    exp_matched = []
    if exp_path and os.path.exists(exp_path):
        exp_data = read_experimental_json(exp_path, material)
        if exp_data:
            exp_matched = match_exp_to_labels(exp_data, all_label_positions)
            if exp_matched:
                for pt in exp_matched:
                    q = pt.get("q", 0.0)
                    freq = pt.get("frequency", 0.0)
                    err = pt.get("error", 0.0)
                    ax.errorbar(q, freq, yerr=err, fmt="o", color="black",
                                markersize=5, capsize=3, zorder=5)
                ax.plot([], [], "ko", label="Experiment (INS)", markersize=5)
                plotted_any = True

    # Axis formatting
    ax.set_ylabel("Frequency (THz)", fontsize=12)
    ax.set_xlabel("Wave Vector", fontsize=12)

    if all_label_positions:
        all_label_positions = sorted(set(normalize_labels(all_label_positions)), key=lambda x: x[0])
        tick_pos = [x[0] for x in all_label_positions]
        tick_lab = [x[1] for x in all_label_positions]
        ax.set_xticks(tick_pos)
        ax.set_xticklabels(tick_lab, fontsize=11)

    ax.axhline(0, color="black", lw=0.5)
    ax.set_ylim(bottom=0)
    if plotted_any:
        ax.legend(loc="upper right", fontsize=9)
    ax.grid(axis="y", alpha=0.3)

    ax.set_title(f"Phonon Dispersion: {material}", fontsize=13)

    plt.tight_layout()
    plt.savefig(output, dpi=300)
    print(f"[plot] Saved comparison to {output}")


def main():
    parser = argparse.ArgumentParser(description="Overlay phonon bands from multiple calculators")
    parser.add_argument("--material", choices=["Si", "diamond"], required=True)
    parser.add_argument("--results-dir", default="phonon_results")
    parser.add_argument("--experimental", default="experimental_phonon_data.json")
    parser.add_argument("--phonondb-ref", default=None,
                        help="Path to phononDB DFT reference band.yaml")
    parser.add_argument("--alamode-dir", default="alamode_results",
                        help="Directory containing ALAMODE results")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    plot_comparison(args.material, args.results_dir, args.experimental, args.output,
                    args.phonondb_ref, args.alamode_dir)


if __name__ == "__main__":
    main()
