#!/usr/bin/env python3
"""
plot_phonons.py
===============
Overlay phonon dispersion curves on a common reference q-path.

All computed band.yaml files are expected to have been evaluated on the
same q-points as the reference (e.g. from run_phonon.py). No interpolation
is performed — the reference distance axis is used directly.

Usage:
  python plot_phonons.py \
      --ref mp_diamond_phonon_bands.dat \
      --computed phonon_results/diamond_dftb_2x2x2/band.yaml \
      --computed phonon_results/diamond_tersoff_2x2x2/band.yaml \
      --output plots/diamond_comparison.png
"""

import argparse
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def read_ref_dat(path):
    """Read reference .dat file: qpts, distances, freqs, labels."""
    qpts, dists, freqs, labels = [], [], [], []
    with open(path) as f:
        header = next(f)
        for line in f:
            parts = line.strip().split()
            if len(parts) < 4:
                continue
            qpts.append([float(parts[0]), float(parts[1]), float(parts[2])])
            dists.append(float(parts[3]))
            # Columns 4+ are either frequencies or a label (non-numeric last column)
            freq_vals = []
            label = ""
            if len(parts) >= 5:
                for i in range(4, len(parts)):
                    try:
                        freq_vals.append(float(parts[i]))
                    except ValueError:
                        label = parts[i]
                        break
            freqs.append(freq_vals)
            labels.append(label)
    return np.array(qpts), np.array(dists), np.array(freqs) if freqs else np.array([]), labels


def read_band_yaml(path):
    """Read phonopy band.yaml and return qpts, freqs, labels."""
    import yaml
    with open(path) as f:
        data = yaml.safe_load(f)
    phonon = data["phonon"]
    qpts = []
    freqs = []
    for q in phonon:
        qpts.append(q["q-position"])
        freqs.append([b["frequency"] for b in q["band"]])
    qpts = np.array(qpts)
    freqs = np.array(freqs)

    # Extract labels from segments
    all_labels = []
    segments = data.get("segment_nqpoint", [data["nqpoint"]])
    top_labels = data.get("labels", [])
    idx = 0
    for seg_i, seg_nq in enumerate(segments):
        if seg_i < len(top_labels):
            start_lab, end_lab = top_labels[seg_i]
            all_labels.append((idx, start_lab))
            all_labels.append((idx + seg_nq - 1, end_lab))
        idx += seg_nq

    return qpts, freqs, all_labels


def normalize_label(lab):
    lab = str(lab).replace("$\\mathrm{", "").replace("$", "").replace("\\mathrm{", "").replace("}", "")
    lab = lab.replace("\\Gamma", "Γ").replace("Gamma", "Γ")
    lab = "Γ" if lab in ("G", "GAMMA", "\\Gamma") else lab
    return lab


def plot_overlay(ref_path, computed_paths, output, computed_names=None):
    ref_qpts, ref_dists, ref_freqs, ref_labels = read_ref_dat(ref_path)
    n_bands = ref_freqs.shape[1] if ref_freqs.size > 0 else 0
    print(f"[plot] Reference: {len(ref_qpts)} q-points, {n_bands} bands")

    fig, ax = plt.subplots(figsize=(10, 6))

    # Plot reference (gray dashed) if frequencies available
    if n_bands > 0:
        for b in range(n_bands):
            ax.plot(ref_dists, ref_freqs[:, b], color="gray", alpha=0.5, lw=1.0, ls="--")
        ax.plot([], [], color="gray", ls="--", label="DFT reference (MP)", lw=2)

    # Extract label tick positions from reference
    tick_positions = []
    tick_labels = []
    seen = set()
    for i, lab in enumerate(ref_labels):
        if lab and lab not in seen:
            tick_positions.append(ref_dists[i])
            tick_labels.append(normalize_label(lab))
            seen.add(lab)

    # Plot computed curves
    colors = {"dftb": "tab:red", "tersoff": "tab:orange", "sw": "tab:blue", "meam": "tab:green"}
    for cp_idx, cpath in enumerate(computed_paths):
        if not os.path.exists(cpath):
            print(f"WARNING: {cpath} not found, skipping")
            continue

        qpts, freqs, _ = read_band_yaml(cpath)
        if len(qpts) != len(ref_qpts):
            print(f"WARNING: {cpath} has {len(qpts)} q-points, expected {len(ref_qpts)}")
            continue
        max_qdiff = np.max(np.abs(qpts - ref_qpts))
        if max_qdiff > 1e-5:
            print(f"WARNING: {cpath} q-points differ by {max_qdiff:.2e} from reference")
            continue

        name = computed_names[cp_idx] if computed_names and cp_idx < len(computed_names) else os.path.basename(os.path.dirname(cpath))
        color = colors.get(name.split("_")[0], None)
        if color is None:
            import hashlib
            from matplotlib.colors import hsv_to_rgb
            hue = int(hashlib.md5(name.encode()).hexdigest(), 16) % 360 / 360.0
            color = hsv_to_rgb([hue, 0.7, 0.8])

        n_plot_bands = n_bands if n_bands > 0 else freqs.shape[1]
        for b in range(min(freqs.shape[1], n_plot_bands)):
            ax.plot(ref_dists, freqs[:, b], color=color, alpha=0.7, lw=1.2)
        ax.plot([], [], color=color, label=name.replace("_", " "), lw=2)
        print(f"[plot] Plotted {name}: {freqs.shape[1]} bands, q-match OK (max_diff={max_qdiff:.2e})")

    # Axis formatting
    if tick_positions:
        ax.set_xticks(tick_positions)
        ax.set_xticklabels(tick_labels, fontsize=11)
    ax.set_ylabel("Frequency (THz)", fontsize=12)
    ax.set_xlabel("Wave Vector", fontsize=12)
    ax.axhline(0, color="black", lw=0.5)
    ax.set_ylim(bottom=0)
    ax.legend(loc="upper right", fontsize=9)
    ax.grid(axis="y", alpha=0.3)
    material = os.path.basename(ref_path).split('_')[0].capitalize()
    if material == 'Mp':
        material = 'Diamond'
    ax.set_title(f"Phonon Dispersion: {material} (exact q-points)", fontsize=13)

    plt.tight_layout()
    plt.savefig(output, dpi=300)
    print(f"[plot] Saved {output}")


def main():
    parser = argparse.ArgumentParser(description="Overlay phonon bands on reference q-path")
    parser.add_argument("--ref", required=True, help="Reference .dat file")
    parser.add_argument("--computed", nargs="+", required=True, help="Computed band.yaml files")
    parser.add_argument("--names", nargs="+", default=None, help="Legend names for computed curves")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.output) if os.path.dirname(args.output) else ".", exist_ok=True)
    plot_overlay(args.ref, args.computed, args.output, args.names)


if __name__ == "__main__":
    main()
