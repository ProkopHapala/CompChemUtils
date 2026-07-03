#!/usr/bin/env python3
"""
plot_alamode_overlay.py
=======================
Overlay ALAMODE phonon bands with existing multi-method data.

Usage:
  python plot_alamode_overlay.py --material Si --alamode alamode_results/Si_sw_2x2x2/Si_sw_prim.bands --output plots/Si_alamode_overlay.png
  python plot_alamode_overlay.py --material diamond --alamode alamode_results/diamond_tersoff_2x2x2/diamond_tersoff_prim.bands --output plots/diamond_alamode_overlay.png
"""

import argparse
import json
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plot_phonon_benchmark import read_alamode_band_dat, read_phonopy_band_yaml


# Standard FCC high-symmetry labels along phonopy band path
FCC_LABELS = ["Γ", "X", "U", "K", "Γ", "L", "W", "X"]


def read_multi_method_dat(path):
    """Read Si_phonon_bands.dat or diamond_phonon_bands.dat format."""
    with open(path) as f:
        header = f.readline().strip()
    if header.startswith("#"):
        header = header[1:].strip()
    cols = header.split()
    data = np.loadtxt(path, comments="#")
    qpts = data[:, :3]
    dist = data[:, 3]
    # Find frequency column groups from header
    freq_start = 4
    freq_end = data.shape[1]
    freqs = data[:, freq_start:freq_end]
    method_cols = {}
    for i, name in enumerate(cols[freq_start:freq_end]):
        parts = name.split("_")
        method = parts[0]
        if method not in method_cols:
            method_cols[method] = []
        method_cols[method].append(i)
    methods = {}
    for method, idxs in method_cols.items():
        methods[method] = freqs[:, idxs]
    return qpts, dist, methods


def derive_label_positions_from_phonopy(band_yaml_path):
    """Read high-symmetry labels from phonopy band.yaml."""
    import yaml
    with open(band_yaml_path) as f:
        data = yaml.safe_load(f)
    phonon = data["phonon"]
    segments = data.get("segment_nqpoint", [data["nqpoint"]])
    labels_raw = data.get("labels", [])

    positions = []
    idx = 0
    for seg_i, seg_nq in enumerate(segments):
        if seg_i < len(labels_raw):
            start_lab, end_lab = labels_raw[seg_i]
            # Normalize labels
            start_lab = start_lab.replace("$\\mathrm{", "").replace("$", "").replace("\\mathrm{", "").replace("}", "")
            start_lab = start_lab.replace("\\Gamma", "Γ").replace("Gamma", "Γ")
            start_lab = "Γ" if start_lab in ("G", "GAMMA", "\\Gamma") else start_lab
            end_lab = end_lab.replace("$\\mathrm{", "").replace("$", "").replace("\\mathrm{", "").replace("}", "")
            end_lab = end_lab.replace("\\Gamma", "Γ").replace("Gamma", "Γ")
            end_lab = "Γ" if end_lab in ("G", "GAMMA", "\\Gamma") else end_lab
            dist_start = phonon[idx]["distance"]
            dist_end = phonon[idx + seg_nq - 1]["distance"]
            positions.append((dist_start, start_lab))
            positions.append((dist_end, end_lab))
        idx += seg_nq

    # Merge adjacent labels at same distance (e.g. U|K)
    dedup = []
    for d, lab in positions:
        if dedup and abs(dedup[-1][0] - d) < 1e-5:
            # Same distance: merge labels
            old_lab = dedup[-1][1]
            if lab not in old_lab:
                dedup[-1] = (dedup[-1][0], old_lab + "|" + lab)
        else:
            dedup.append((float(d), lab))
    return dedup


def derive_label_positions(dist):
    """Detect segment boundaries from distance jumps and assign FCC labels."""
    diffs = np.diff(dist)
    # A negative jump indicates a new segment (path discontinuity)
    jump_indices = np.where(diffs < -1e-6)[0]
    # Segment start indices: 0, and each jump+1
    seg_starts = [0] + [int(j + 1) for j in jump_indices]
    # Segment end indices: each jump, and last point
    seg_ends = [int(j) for j in jump_indices] + [len(dist) - 1]

    # Standard FCC path has 7 segments (8 points): Γ-X-U-K-Γ-L-W-X
    n_segments = len(seg_starts)
    labels = []
    for i in range(n_segments + 1):
        idx = min(i, len(FCC_LABELS) - 1)
        labels.append(FCC_LABELS[idx])

    positions = []
    for i, start in enumerate(seg_starts):
        positions.append((dist[start], labels[i]))
    positions.append((dist[seg_ends[-1]], labels[n_segments]))
    dedup = []
    for d, lab in positions:
        if dedup and abs(dedup[-1][0] - d) < 1e-5:
            old_lab = dedup[-1][1]
            if lab not in old_lab:
                dedup[-1] = (dedup[-1][0], old_lab + "|" + lab)
        else:
            dedup.append((float(d), lab))
    return dedup


def read_exp_json(path, material):
    with open(path) as f:
        data = json.load(f)
    return data.get(material, {})


def match_exp_to_labels(exp_data, label_positions):
    """Map experimental points to x-positions using high-symmetry label positions."""
    if not exp_data:
        return []
    # Build normalized label -> position mapping
    label_pos = {}
    for d, lab in label_positions:
        label_pos[lab] = d
        if lab == "Γ":
            label_pos["G"] = d
            label_pos["Gamma"] = d
            label_pos["GAMMA"] = d
            label_pos["\\Gamma"] = d
    matched = []
    for pt in exp_data.get("points", []):
        lab = pt.get("label", "")
        lab_norm = lab.replace("\\Gamma", "Γ").replace("Gamma", "Γ").replace("GAMMA", "Γ").replace("G", "Γ")
        if lab_norm in label_pos:
            matched.append({"q": label_pos[lab_norm], **pt})
        elif pt.get("q") is not None:
            matched.append(pt)
    return matched


def interpolate_to_grid(dist_src, freqs_src, dist_target):
    """Interpolate frequencies from src grid to target grid, handling segment jumps."""
    # Normalize both to [0, 1]
    t_src = (dist_src - dist_src[0]) / (dist_src[-1] - dist_src[0] + 1e-12)
    t_target = (dist_target - dist_target[0]) / (dist_target[-1] - dist_target[0] + 1e-12)
    # Ensure monotonic (should be)
    freqs_interp = np.zeros((len(dist_target), freqs_src.shape[1]))
    for b in range(freqs_src.shape[1]):
        freqs_interp[:, b] = np.interp(t_target, t_src, freqs_src[:, b])
    return freqs_interp


def plot_overlay(material, alamode_path, dat_path, exp_path, output, mp_dat=None):
    fig, ax = plt.subplots(figsize=(10, 6))

    qpts, dist, methods = read_multi_method_dat(dat_path)
    nbands = list(methods.values())[0].shape[1]
    print(f"[plot] Loaded {len(methods)} methods from {dat_path}")

    # Derive high-symmetry label positions
    # Try phonopy band.yaml first (has proper labels)
    band_yaml = None
    for name in sorted(os.listdir("phonon_results")):
        if name.startswith(material) and os.path.isdir(os.path.join("phonon_results", name)):
            by = os.path.join("phonon_results", name, "band.yaml")
            if os.path.exists(by):
                band_yaml = by
                break
    if band_yaml:
        label_positions = derive_label_positions_from_phonopy(band_yaml)
    else:
        label_positions = derive_label_positions(dist)
    print(f"[plot] Label positions: {label_positions}")

    # Plot existing methods (light, thin)
    colors_existing = {
        "meam": "tab:green",
        "sw": "tab:blue",
        "tersoff": "tab:orange",
        "dftb": "tab:red",
        "phonondb_DFT": "gray",
    }

    for method, freqs in methods.items():
        color = colors_existing.get(method, None)
        if color is None:
            import hashlib
            from matplotlib.colors import hsv_to_rgb
            hue = int(hashlib.md5(method.encode()).hexdigest(), 16) % 360 / 360.0
            color = hsv_to_rgb([hue, 0.7, 0.8])
        for b in range(nbands):
            ax.plot(dist, freqs[:, b], color=color, alpha=0.4, lw=1.0)
        ax.plot([], [], color=color, label=method, lw=2)

    # Plot ALAMODE
    if alamode_path and os.path.exists(alamode_path):
        dist_al, freqs_al = read_alamode_band_dat(alamode_path)
        # Interpolate ALAMODE onto the common distance grid
        freqs_interp = interpolate_to_grid(dist_al, freqs_al, dist)
        for b in range(freqs_interp.shape[1]):
            ax.plot(dist, freqs_interp[:, b], color="tab:purple", alpha=0.8, lw=1.5)
        ax.plot([], [], color="tab:purple", label="ALAMODE", lw=2)
        print(f"[plot] Loaded ALAMODE from {alamode_path}")

    # Plot MP reference for diamond (if provided)
    if mp_dat and os.path.exists(mp_dat):
        with open(mp_dat) as f:
            next(f)  # skip header
            mp_dists = []
            mp_freqs = []
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 10:
                    mp_dists.append(float(parts[3]))
                    mp_freqs.append([float(parts[4 + i]) for i in range(6)])
        mp_dists = np.array(mp_dists)
        mp_freqs = np.array(mp_freqs)
        freqs_mp_interp = interpolate_to_grid(mp_dists, mp_freqs, dist)
        for b in range(6):
            ax.plot(dist, freqs_mp_interp[:, b], color="black", alpha=0.5, lw=1.0, ls="--")
        ax.plot([], [], color="black", ls="--", label="MP-DFT", lw=2)
        print(f"[plot] Loaded MP reference from {mp_dat}")

    # Experimental points
    if exp_path and os.path.exists(exp_path):
        exp_data = read_exp_json(exp_path, material)
        matched = match_exp_to_labels(exp_data, label_positions)
        if matched:
            for pt in matched:
                ax.errorbar(pt["q"], pt["frequency"], yerr=pt.get("error", 0.0),
                            fmt="o", color="black", markersize=5, capsize=3, zorder=5)
            ax.plot([], [], "ko", label="Experiment", markersize=5)
            print(f"[plot] Plotted {len(matched)} experimental points")

    # Axis formatting
    ax.set_ylabel("Frequency (THz)", fontsize=12)
    ax.set_xlabel("Wave Vector", fontsize=12)
    if label_positions:
        tick_pos = [x[0] for x in label_positions]
        tick_lab = [x[1] for x in label_positions]
        ax.set_xticks(tick_pos)
        ax.set_xticklabels(tick_lab, fontsize=11)
    ax.axhline(0, color="black", lw=0.5)
    ax.set_ylim(bottom=0)
    ax.legend(loc="upper right", fontsize=9)
    ax.grid(axis="y", alpha=0.3)
    ax.set_title(f"Phonon Dispersion: {material}", fontsize=13)
    plt.tight_layout()
    plt.savefig(output, dpi=300)
    print(f"[plot] Saved {output}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--material", choices=["Si", "diamond"], required=True)
    parser.add_argument("--alamode", required=True, help="Path to ALAMODE .bands file")
    parser.add_argument("--dat", default=None, help="Path to existing multi-method .dat file")
    parser.add_argument("--mp-dat", default=None, help="Path to MP reference .dat file")
    parser.add_argument("--experimental", default="experimental_phonon_data.json")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    material = args.material
    if args.dat is None:
        args.dat = f"{material.lower()}_phonon_bands.dat"
        if material == "Si":
            args.dat = "Si_phonon_bands.dat"

    plot_overlay(material, args.alamode, args.dat, args.experimental, args.output, args.mp_dat)


if __name__ == "__main__":
    main()
