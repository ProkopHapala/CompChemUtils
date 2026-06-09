#!/usr/bin/env python3
"""
plot_phonon_comparison.py
==========================
Rigorous multi-method phonon band comparison plot.

ALL calculations MUST share the exact same q-point sequence.
The reference q-path (from .dat file) defines the x-axis.

Label convention:
  - Title:  input structure filename (e.g. "diamond_primitive.cif")
  - Curves: "program/method/basis"  (e.g. "dftb+/pbc-0-3", "lammps/tersoff")

Usage:
  python plot_phonon_comparison.py \
      --calc test/diamond_primitive_tersoff_3x3x3/phonon_bands.npz \
      --calc test/diamond_primitive_dftb_3x3x3/phonon_bands.npz \
      --ref mp_diamond_phonon_bands.dat \
      --output plots/diamond_comparison.png
"""

import argparse
import os
import sys
import re
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def normalize_label(lab):
    """Clean up high-symmetry labels for display."""
    lab = str(lab)
    for pat, repl in [(r"$\\mathrm\{", ""), ("$", ""), (r"\\mathrm\{", ""), ("}", ""),
                      (r"\\Gamma", "Γ"), ("Gamma", "Γ"), ("GAMMA", "Γ")]:
        lab = lab.replace(pat, repl)
    lab = "Γ" if lab in ("G", "GAMMA", r"\Gamma") else lab
    return lab


def read_ref_dat(path, ref_method="phonondb_DFT"):
    """Read reference .dat: qpts, distances, freqs, labels.
    
    Handles multi-method .dat files with headers like:
      # qx qy qz distance meam_b1 ... sw_b1 ... tersoff_b1 ... dftb_b1 ... phonondb_DFT_b1 ... label
    Only columns matching ref_method are extracted as frequencies.
    """
    qpts, dists, freqs, labels = [], [], [], []
    freq_cols = None  # list of column indices for the selected method
    with open(path) as f:
        header = next(f).strip().split()
        # Identify frequency columns for the selected method.
        # Header starts with '#', so data index = header index - 1.
        for i, col in enumerate(header):
            if ref_method and ref_method in col:
                freq_cols = freq_cols or []
                data_idx = i - 1  # subtract '#' prefix
                if data_idx >= 0:
                    freq_cols.append(data_idx)
        # If no match found and file has few columns, assume all numeric cols are freqs
        if freq_cols is None:
            print(f"[warn] No '{ref_method}' columns found in {path}, using all numeric columns")
        
        for line in f:
            parts = line.strip().split()
            if len(parts) < 4:
                continue
            qpts.append([float(parts[0]), float(parts[1]), float(parts[2])])
            dists.append(float(parts[3]))
            if freq_cols is not None:
                freq_vals = [float(parts[i]) for i in freq_cols if i < len(parts)]
                label = parts[-1] if len(parts) > max(freq_cols) + 1 else ""
            else:
                freq_vals, label = [], ""
                for i in range(4, len(parts)):
                    try:
                        freq_vals.append(float(parts[i]))
                    except ValueError:
                        label = parts[i]
                        break
            freqs.append(freq_vals)
            labels.append(label)
    return np.array(qpts), np.array(dists), (np.array(freqs) if freqs else np.array([])), labels


def read_phonon_bands_npz(path):
    """Read modular phonon_bands.npz with metadata."""
    data = np.load(path, allow_pickle=True)
    labels = data['labels'].tolist() if 'labels' in data else []
    # Metadata
    meta = {}
    for key in ('structure_file', 'method', 'program', 'basis_set', 'supercell'):
        if key in data:
            meta[key] = str(data[key])
    return {
        'qpts': data['qpts'],
        'distances': data['distances'],
        'freqs': data['frequencies'],
        'labels': labels,
        'meta': meta,
        'path': path,
    }


def make_label(calc_data, user_label=None):
    """Build label as program/method/basis from npz metadata."""
    if user_label:
        return user_label
    meta = calc_data.get('meta', {})
    prog = meta.get('program', '')
    method = meta.get('method', '')
    basis = meta.get('basis_set', '')

    # Map raw program names to display names
    prog_map = {'dftb': 'dftb+', 'lammps': 'lammps'}
    prog_disp = prog_map.get(prog, prog)

    # Build label
    parts = [prog_disp] if prog_disp else []
    if method and method != prog:
        parts.append(method)
    if basis:
        parts.append(basis)

    if parts:
        return '/'.join(parts)

    # Fallback: parse from directory name
    dir_name = Path(calc_data['path']).parent.name
    name = re.sub(r'_\d+x\d+x\d+$', '', dir_name)
    parts = name.split('_')
    pots = ('tersoff', 'sw', 'meam', 'mtp', 'eam', 'reax')
    for i, p in enumerate(parts):
        pl = p.lower()
        if pl == 'dftb':
            return 'dftb+/' + '_'.join(parts[i+1:]) if i+1 < len(parts) else 'dftb+'
        elif pl in pots:
            return 'lammps/' + pl
        elif pl in ('gpaw', 'vasp', 'qe', 'firecore', 'lammps'):
            return pl + '/' + '_'.join(parts[i+1:]) if i+1 < len(parts) else pl
    return dir_name


def get_structure_title(calcs):
    """Extract single structure filename for title."""
    # Prefer metadata
    for c in calcs:
        sf = c.get('meta', {}).get('structure_file', '')
        if sf:
            return f"Phonon Dispersion: {sf}"
    # Fallback: parse from path
    for c in calcs:
        p = Path(c['path'])
        dir_name = p.parent.name
        name = re.sub(r'_\d+x\d+x\d+$', '', dir_name)
        parts = name.split('_')
        if parts:
            return f"Phonon Dispersion: {parts[0]}"
    return "Phonon Dispersion Comparison"


def extract_ticks(dists, labels):
    """Extract unique tick positions from labeled q-points."""
    tick_pos, tick_lab, seen = [], [], set()
    for d, lab in zip(dists, labels):
        if lab and lab not in seen:
            tick_pos.append(d)
            tick_lab.append(normalize_label(lab))
            seen.add(lab)
    return tick_pos, tick_lab


def validate_qpath_match(ref_qpts, calc_qpts, calc_name, tol=1e-5):
    """Check that two q-point arrays match exactly."""
    if len(ref_qpts) != len(calc_qpts):
        print(f"[SKIP] {calc_name}: {len(calc_qpts)} q-points, expected {len(ref_qpts)}")
        return False
    diff = np.max(np.abs(ref_qpts - calc_qpts))
    if diff > tol:
        print(f"[SKIP] {calc_name}: q-points differ by {diff:.2e} (max allowed {tol})")
        return False
    return True


def plot_comparison(calcs, refs, output, title=None, ref_label="DFT reference (MP)"):
    """Plot overlay.  All calcs must share the same q-points as the first entry."""
    if not calcs and not refs:
        raise ValueError("No data to plot")

    # Master q-path: from first calc or ref
    if calcs:
        master_qpts = calcs[0]['qpts']
        master_dists = calcs[0]['distances']
        master_labels = calcs[0].get('labels', [])
    else:
        master_qpts = refs[0]['qpts']
        master_dists = refs[0]['distances']
        master_labels = refs[0].get('labels', [])

    fig, ax = plt.subplots(figsize=(11, 6.5))

    # X-axis: ticks + vertical lines at high-symmetry points
    tick_pos, tick_lab = extract_ticks(master_dists, master_labels)
    if tick_pos:
        ax.set_xticks(tick_pos)
        ax.set_xticklabels(tick_lab, fontsize=12)
        for p in tick_pos:
            ax.axvline(x=p, color='k', lw=0.5, alpha=0.3)

    # Colors
    colors = plt.cm.tab10(np.linspace(0, 1, 10))
    color_idx = 0

    # Reference curves (gray dashed) — must share exact q-path with master
    for ref in refs:
        ref_name = ref.get('display_label', ref_label)
        if not validate_qpath_match(master_qpts, ref['qpts'], ref_name):
            continue
        freqs = ref['freqs']
        if freqs.size == 0:
            continue
        for b in range(freqs.shape[1]):
            ax.plot(master_dists, freqs[:, b], color="gray", alpha=0.5, lw=1.0, ls="--")
        ax.plot([], [], color="gray", ls="--", label=ref_name, lw=2)
        print(f"[plot] {ref_name}: {freqs.shape[1]} bands")
        color_idx += 1

    # Calculations — validated against master q-path
    for calc in calcs:
        if not validate_qpath_match(master_qpts, calc['qpts'], calc['display_label']):
            continue
        freqs = calc['freqs']
        color = colors[color_idx % len(colors)]
        for b in range(freqs.shape[1]):
            ax.plot(master_dists, freqs[:, b], color=color, alpha=0.7, lw=1.2)
        ax.plot([], [], color=color, label=calc['display_label'], lw=2)
        print(f"[plot] {calc['display_label']}: {freqs.shape[1]} bands")
        color_idx += 1

    ax.set_ylabel("Frequency (THz)", fontsize=12)
    ax.set_xlabel("Wave Vector", fontsize=12)
    ax.axhline(0, color="black", lw=0.5)
    ax.set_ylim(bottom=0)
    ax.legend(loc="upper right", fontsize=10,
              ncol=1 if len(calcs) + len(refs) < 6 else 2)
    ax.grid(axis="y", alpha=0.3)
    if title:
        ax.set_title(title, fontsize=13)

    plt.tight_layout()
    os.makedirs(os.path.dirname(output) if os.path.dirname(output) else ".", exist_ok=True)
    plt.savefig(output, dpi=300)
    print(f"[plot] Saved {output}")
    plt.close()


def main():
    parser = argparse.ArgumentParser(description="Overlay phonon bands — requires identical q-paths")
    parser.add_argument("--calc", action="append", required=True,
                        help="phonon_bands.npz files (one per --calc flag)")
    parser.add_argument("--label", action="append", default=None,
                        help="Legend label for corresponding --calc")
    parser.add_argument("--ref", nargs="+", default=None,
                        help="Reference .dat file(s)")
    parser.add_argument("--ref-label", default="DFT reference (MP)",
                        help="Legend label for reference")
    parser.add_argument("--title", default=None,
                        help="Plot title (auto = structure filename)")
    parser.add_argument("--output", required=True, help="Output PNG path")
    args = parser.parse_args()

    # Load calculations
    calcs = []
    for i, cpath in enumerate(args.calc):
        if not os.path.exists(cpath):
            print(f"[SKIP] {cpath}: not found")
            continue
        if not cpath.endswith('.npz'):
            print(f"[SKIP] {cpath}: expected .npz file")
            continue
        data = read_phonon_bands_npz(cpath)
        user_label = args.label[i] if args.label and i < len(args.label) else None
        data['display_label'] = make_label(data, user_label)
        calcs.append(data)
        print(f"[load] {data['display_label']}: {len(data['freqs'])} qpts, {data['freqs'].shape[1]} bands")

    # Load references
    refs = []
    if args.ref:
        for rpath in args.ref:
            if not os.path.exists(rpath):
                print(f"[SKIP] {rpath}: not found")
                continue
            qpts, dists, freqs, labels = read_ref_dat(rpath)
            refs.append({
                'qpts': qpts, 'distances': dists, 'freqs': freqs,
                'labels': labels, 'display_label': args.ref_label, 'path': rpath,
            })
            print(f"[load] Ref: {len(qpts)} qpts, {freqs.shape[1] if freqs.size > 0 else 0} bands")

    if not calcs:
        print("ERROR: no valid calculations loaded")
        sys.exit(1)

    title = args.title
    if title is None:
        title = get_structure_title(calcs)

    plot_comparison(calcs, refs, args.output, title=title, ref_label=args.ref_label)


if __name__ == "__main__":
    main()
