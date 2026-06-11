#!/usr/bin/env python3
"""
Export phonon band comparison to interactive HTML viewer.

Usage:
    python export_phonon_html.py \
        --calc test_primitive/diamond_primitive_dftb_3x3x3/phonon_bands.npz \
        --label "DFTB+" \
        --calc test_primitive/diamond_primitive_mmff_default_3x3x3/phonon_bands.npz \
        --label "MMFF default" \
        --ref mp_diamond_phonon_bands.dat \
        --ref-label "REF DFT (MP)" \
        --output plots/diamond_comparison.html
"""

import argparse
import json
import numpy as np
from pathlib import Path


def read_phonon_bands_npz(path):
    """Read phonon_bands.npz and extract frequencies, distances, labels."""
    data = np.load(path, allow_pickle=True)
    return {
        'frequencies': data['frequencies'].tolist(),
        'distances': data['distances'].tolist(),
        'labels': data['labels'].tolist() if 'labels' in data else [],
    }


def read_mp_dat(path):
    """Read Materials Project .dat file (qx qy qz distance freq1...freq6 label)."""
    qpts, dists, freqs, labels = [], [], [], []
    with open(path) as f:
        for line in f:
            if line.startswith('#'):
                continue
            parts = line.strip().split()
            if len(parts) < 10:  # Need at least qx,qy,qz,distance + 6 frequencies
                continue
            qpts.append([float(parts[0]), float(parts[1]), float(parts[2])])
            dists.append(float(parts[3]))
            freqs.append([float(parts[i]) for i in range(4, 10)])
            labels.append(parts[10] if len(parts) > 10 else '')
    print(f"[read_mp_dat] Loaded {len(freqs)} q-points from {path}")
    return {
        'frequencies': freqs,
        'distances': dists,
        'labels': labels,
    }


def extract_ticks(dists, labels):
    """Extract unique tick positions from labeled q-points."""
    tick_pos, tick_lab, seen = [], [], set()
    for d, lab in zip(dists, labels):
        if lab and lab not in seen:
            tick_pos.append(d)
            tick_lab.append(lab)
            seen.add(lab)
    return tick_pos, tick_lab


def normalize_label(lab):
    """Clean up high-symmetry labels."""
    lab = str(lab)
    for pat, repl in [(r"$\\mathrm\{", ""), ("$", ""), (r"\\mathrm\{", ""), ("}", ""),
                      (r"\\Gamma", "Γ"), ("Gamma", "Γ"), ("GAMMA", "Γ")]:
        lab = lab.replace(pat, repl)
    lab = "Γ" if lab in ("G", "GAMMA", r"\Gamma") else lab
    return lab


def main():
    parser = argparse.ArgumentParser(description="Export phonon bands to HTML viewer")
    parser.add_argument("--calc", action="append", required=True,
                        help="phonon_bands.npz files (one per --calc flag)")
    parser.add_argument("--label", action="append", default=None,
                        help="Legend label for corresponding --calc")
    parser.add_argument("--ref", default=None,
                        help="Reference .dat file (e.g., MP DFT)")
    parser.add_argument("--ref-label", default="Reference",
                        help="Legend label for reference")
    parser.add_argument("--title", default=None,
                        help="Plot title")
    parser.add_argument("--output", required=True, help="Output HTML file")
    args = parser.parse_args()

    # Load calculations
    datasets = []
    master_dists = None
    master_labels = None

    for i, cpath in enumerate(args.calc):
        if not Path(cpath).exists():
            print(f"[SKIP] {cpath}: not found")
            continue
        calc_data = read_phonon_bands_npz(cpath)
        user_label = args.label[i] if args.label and i < len(args.label) else None
        if not user_label:
            # Extract from directory name
            user_label = Path(cpath).parent.name
        datasets.append({
            'name': user_label,
            'frequencies': calc_data['frequencies'],
            'visible': True,
        })
        if master_dists is None:
            master_dists = calc_data['distances']
            master_labels = calc_data['labels']
        print(f"[load] {user_label}: {len(calc_data['frequencies'])} qpts, {len(calc_data['frequencies'][0])} bands")

    # Load reference
    if args.ref and Path(args.ref).exists():
        ref_data = read_mp_dat(args.ref)
        datasets.insert(0, {  # Insert at beginning as reference
            'name': args.ref_label,
            'frequencies': ref_data['frequencies'],
            'visible': True,
        })
        # Always use reference distances as master (it's the reference!)
        master_dists = ref_data['distances']
        master_labels = ref_data['labels']
        print(f"[load] {args.ref_label}: {len(ref_data['frequencies'])} qpts, {len(ref_data['frequencies'][0])} bands")

    if not datasets:
        print("ERROR: no valid data loaded")
        return

    # Extract ticks
    tick_pos, tick_lab = extract_ticks(master_dists, master_labels)
    tick_lab = [normalize_label(l) for l in tick_lab]

    # Build JSON data
    json_data = {
        'title': args.title or 'Phonon Band Comparison',
        'distances': master_dists,
        'tick_positions': tick_pos,
        'tick_labels': tick_lab,
        'datasets': datasets,
    }

    # Load HTML template
    template_path = Path(__file__).parent / 'phonon_bands_viewer.html'
    with open(template_path) as f:
        html_template = f.read()

    # Embed data
    html_output = html_template.replace(
        'let data = /*__PHONON_DATA__*/null;',
        f'let data = {json.dumps(json_data)};'
    )
    html_output = html_output.replace(
        '<body data-file="phonon_bands.json">',
        '<body>'
    )

    # Write output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        f.write(html_output)

    print(f"[saved] {output_path}")


if __name__ == "__main__":
    main()
