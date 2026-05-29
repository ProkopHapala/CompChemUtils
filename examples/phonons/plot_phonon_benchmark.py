#!/usr/bin/env python3
"""
plot_phonon_benchmark.py
==========================
Overlay phonon dispersion curves from multiple sources and compare
against experimental reference points.

Supports:
  - phonopy band.yaml (DFTB+, VASP, etc.)
  - ALAMODE band.dat
  - Materials Project JSON (phononwebsite format)
  - phonondb phonopy data
  - Experimental data points (JSON with labels or q positions)

Usage:
  python plot_phonon_benchmark.py \
      --dftb band.yaml --alamode band.dat --mp mp-149_phonon.json \
      --experimental experimental_phonon_data.json --material Si --output benchmark.png
"""

import argparse
import json
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


DEFAULT_LABEL_POS = {
    "G": 0.0,
    "Γ": 0.0,
    "X": 1.0,
    "K": 2.0,
    "L": 3.0,
}


def read_phonopy_band_yaml(path: str):
    """Read phonopy band.yaml and return distances, frequencies, labels.

    Handles phonopy v4 format where labels are in top-level 'labels' list
    paired with 'segment_nqpoint'.
    """
    try:
        import yaml
    except ImportError:
        print("ERROR: PyYAML required. Install: pip install pyyaml")
        sys.exit(1)

    with open(path) as f:
        data = yaml.safe_load(f)

    nq = data["nqpoint"]
    segments = data.get("segment_nqpoint", [nq])
    phonon = data["phonon"]

    all_dist = []
    all_freqs = []
    for q in phonon:
        all_dist.append(q["distance"])
        bands = q["band"]
        freqs = [b["frequency"] for b in bands]
        all_freqs.append(freqs)

    all_dist = np.array(all_dist)
    all_freqs = np.array(all_freqs)

    # Extract labels from top-level labels + segment_nqpoint
    all_labels = []
    top_labels = data.get("labels", [])
    if top_labels and segments:
        idx = 0
        for seg_i, seg_nq in enumerate(segments):
            if seg_i < len(top_labels):
                start_lab, end_lab = top_labels[seg_i]
                # Start label at first q-point of segment
                all_labels.append((all_dist[idx], start_lab))
                # End label at last q-point of segment
                end_idx = idx + seg_nq - 1
                if end_idx < len(all_dist):
                    all_labels.append((all_dist[end_idx], end_lab))
            idx += seg_nq

    # Deduplicate labels (keep first occurrence)
    labels = []
    seen = set()
    for d, lab in all_labels:
        key = (round(float(d), 6), str(lab))
        if key not in seen:
            labels.append((float(d), str(lab)))
            seen.add(key)

    return all_dist, all_freqs, labels


def read_alamode_band_dat(path: str):
    """Read ALAMODE band.dat (distance + frequencies per column)."""
    data = np.loadtxt(path)
    dist = data[:, 0]
    freqs = data[:, 1:]  # cm^-1
    freqs_thz = freqs / 33.356
    return dist, freqs_thz


def read_mp_phonon_json(path: str):
    """Read Materials Project phononwebsite JSON."""
    with open(path) as f:
        data = json.load(f)

    distances = np.array(data["distances"])
    eigenvalues = np.array(data["eigenvalues"])
    if eigenvalues.ndim == 2 and eigenvalues.shape[0] != len(distances) and eigenvalues.shape[1] == len(distances):
        eigenvalues = eigenvalues.T
    labels_raw = data.get("labels", [])
    line_breaks = data.get("line_breaks", [])

    labels = []
    if isinstance(labels_raw, dict):
        for lab, idx in labels_raw.items():
            if isinstance(idx, int) and 0 <= idx < len(distances):
                labels.append((distances[idx], lab))
    else:
        for item in labels_raw:
            if isinstance(item, list) and len(item) == 2:
                labels.append((item[0], item[1]))

    return distances, eigenvalues, labels, line_breaks


def normalize_labels(labels):
    out = []
    for d, lab in labels:
        lab = str(lab)
        # Strip phonopy LaTeX math mode wrappers
        lab = lab.replace("$\\mathrm{", "").replace("$", "").replace("\\mathrm{", "").replace("}", "")
        lab = lab.replace("\\Gamma", "Γ").replace("Gamma", "Γ")
        lab = "Γ" if lab in ("G", "GAMMA", "\\Gamma") else lab
        out.append((float(d), lab))
    return out


def read_experimental_json(path: str, material: str):
    """Read experimental phonon data points."""
    with open(path) as f:
        data = json.load(f)
    return data.get(material, {})


def match_exp_to_labels(exp_data, theory_labels):
    """Match experimental points by label to theoretical x-positions."""
    if not theory_labels:
        return [dict(pt, q=DEFAULT_LABEL_POS.get(pt.get("label", ""), pt.get("q", 0.0))) for pt in exp_data.get("points", [])]

    # Build label -> x-position mapping (use first occurrence)
    label_pos = {}
    for d, lab in normalize_labels(theory_labels):
        if lab not in label_pos:
            label_pos[lab] = d
        if lab == "Γ":
            label_pos.setdefault("G", d)

    matched = []
    for pt in exp_data.get("points", []):
        lab = pt.get("label", "")
        # Normalize experimental label for matching
        lab_norm = lab.replace("\\Gamma", "Γ").replace("Gamma", "Γ")
        lab_norm = "Γ" if lab_norm in ("G", "GAMMA", "\\Gamma") else lab_norm
        if lab_norm in label_pos:
            pt_copy = dict(pt)
            pt_copy["q"] = label_pos[lab_norm]
            matched.append(pt_copy)
        elif pt.get("q") is not None:
            matched.append(pt)
    return matched


def plot_benchmark(material, dftb_path, alamode_path, mp_path, phonondb_path,
                   exp_path, output, title=None):
    """Create overlay plot of all phonon data sources."""
    fig, ax = plt.subplots(figsize=(8, 6))

    colors = {
        "dftb": "tab:blue",
        "alamode": "tab:orange",
        "mp": "tab:green",
        "phonondb": "tab:purple",
        "exp": "black",
    }

    all_label_positions = []
    has_theory = False
    plotted_any = False

    # --- DFTB+ / phonopy ---
    if dftb_path and os.path.exists(dftb_path):
        dist, freqs, labels = read_phonopy_band_yaml(dftb_path)
        for i in range(freqs.shape[1]):
            ax.plot(dist, freqs[:, i], color=colors["dftb"], alpha=0.7, lw=1.2)
        ax.plot([], [], color=colors["dftb"], label="DFTB+ / phonopy", lw=2)
        all_label_positions.extend(labels)
        has_theory = True
        plotted_any = True

    # --- ALAMODE ---
    if alamode_path and os.path.exists(alamode_path):
        dist, freqs = read_alamode_band_dat(alamode_path)
        for i in range(freqs.shape[1]):
            ax.plot(dist, freqs[:, i], color=colors["alamode"], alpha=0.7, lw=1.2)
        ax.plot([], [], color=colors["alamode"], label="ALAMODE (LAMMPS)", lw=2)
        has_theory = True
        plotted_any = True

    # --- Materials Project ---
    if mp_path and os.path.exists(mp_path):
        dist, freqs, labels, breaks = read_mp_phonon_json(mp_path)
        for i in range(freqs.shape[1]):
            ax.plot(dist, freqs[:, i], color=colors["mp"], alpha=0.7, lw=1.2)
        ax.plot([], [], color=colors["mp"], label="Materials Project (DFT)", lw=2)
        all_label_positions.extend(labels)
        has_theory = True
        plotted_any = True
        for b in breaks:
            if 0 < b < len(dist) - 1:
                ax.axvline(dist[b], color="gray", lw=0.5, ls="--")

    # --- phonondb ---
    if phonondb_path and os.path.exists(phonondb_path):
        dist, freqs, labels = read_phonopy_band_yaml(phonondb_path)
        for i in range(freqs.shape[1]):
            ax.plot(dist, freqs[:, i], color=colors["phonondb"], alpha=0.7, lw=1.2)
        ax.plot([], [], color=colors["phonondb"], label="phonondb (DFT)", lw=2)
        all_label_positions.extend(labels)
        has_theory = True
        plotted_any = True

    # --- Experimental points ---
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
                    branch = pt.get("branch", "")
                    ax.errorbar(q, freq, yerr=err, fmt="o", color=colors["exp"],
                                markersize=5, capsize=3, zorder=5)
                ax.plot([], [], "ko", label="Experiment (INS)", markersize=5)
                plotted_any = True

    # --- Axis formatting ---
    ax.set_ylabel("Frequency (THz)", fontsize=12)
    ax.set_xlabel("Wave Vector", fontsize=12)

    if not all_label_positions and exp_matched:
        labs = []
        for pt in exp_matched:
            lab = pt.get("label", "")
            q = pt.get("q", None)
            if lab and q is not None:
                labs.append((q, lab))
        all_label_positions = labs

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

    plot_title = title or f"Phonon Dispersion Benchmark: {material}"
    ax.set_title(plot_title, fontsize=13)

    plt.tight_layout()
    plt.savefig(output, dpi=300)
    print(f"[plot] Saved benchmark plot to {output}")

    # --- RMS error ---
    if exp_matched and has_theory:
        compute_rms(material, exp_matched, dftb_path, alamode_path, mp_path, phonondb_path)


def compute_rms(material, exp_matched, dftb_path, alamode_path, mp_path, phonondb_path):
    """Compute RMS error between theoretical curves and experimental points."""
    print("\n[benchmark] RMS Error Analysis (vs. experiment)")
    print("-" * 50)

    sources = []
    if dftb_path and os.path.exists(dftb_path):
        dist, freqs, _ = read_phonopy_band_yaml(dftb_path)
        sources.append(("DFTB+", dist, freqs))
    if alamode_path and os.path.exists(alamode_path):
        dist, freqs = read_alamode_band_dat(alamode_path)
        sources.append(("ALAMODE", dist, freqs))
    if mp_path and os.path.exists(mp_path):
        dist, freqs, _, _ = read_mp_phonon_json(mp_path)
        sources.append(("MP-DFT", dist, freqs))
    if phonondb_path and os.path.exists(phonondb_path):
        dist, freqs, _ = read_phonopy_band_yaml(phonondb_path)
        sources.append(("phonondb", dist, freqs))

    for name, dist, freqs in sources:
        errors = []
        for pt in exp_matched:
            q_target = pt.get("q", 0.0)
            freq_exp = pt.get("frequency", 0.0)
            idx = np.argmin(np.abs(dist - q_target))
            if freqs.ndim == 2:
                band_freqs = freqs[idx, :]
                idx_band = np.argmin(np.abs(band_freqs - freq_exp))
                freq_theory = band_freqs[idx_band]
            else:
                freq_theory = freqs[idx]
            errors.append((freq_theory - freq_exp) ** 2)
        if errors:
            rms = np.sqrt(np.mean(errors))
            print(f"  {name:12s} RMS error: {rms:.3f} THz")
    print("-" * 50)


def main():
    parser = argparse.ArgumentParser(
        description="Overlay and benchmark phonon dispersion curves"
    )
    parser.add_argument("--material", choices=["Si", "diamond", "C"],
                        default="Si", help="Material name")
    parser.add_argument("--dftb", default=None,
                        help="Path to phonopy band.yaml from DFTB+")
    parser.add_argument("--alamode", default=None,
                        help="Path to ALAMODE band.dat")
    parser.add_argument("--mp", default=None,
                        help="Path to Materials Project phonon JSON")
    parser.add_argument("--phonondb", default=None,
                        help="Path to phonondb band.yaml")
    parser.add_argument("--experimental", default="experimental_phonon_data.json",
                        help="Path to experimental data JSON")
    parser.add_argument("--output", default="phonon_benchmark.png",
                        help="Output plot file")
    parser.add_argument("--title", default=None,
                        help="Plot title")
    args = parser.parse_args()

    mat = args.material
    if mat == "C":
        mat = "diamond"

    plot_benchmark(mat, args.dftb, args.alamode, args.mp, args.phonondb,
                   args.experimental, args.output, args.title)


if __name__ == "__main__":
    main()
