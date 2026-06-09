#!/usr/bin/env python3
"""
export_phonon_bands_json.py
============================
Export multiple phonon_bands.npz files to a single JSON for the interactive viewer.

All datasets MUST share the exact same q-point sequence.

Usage:
  python export_phonon_bands_json.py \
      --calc test_primitive/diamond_primitive_tersoff_3x3x3/phonon_bands.npz \
      --calc test_primitive/diamond_primitive_dftb_3x3x3/phonon_bands.npz \
      --label "lammps/tersoff" --label "dftb+/pbc-0-3" \
      --output plots/diamond_bands.json

  # Generate standalone HTML (embeds JSON):
  python export_phonon_bands_json.py ... --html plots/diamond_bands.html

  # Solver comparison from cached runs (use ML venv for phonopy):
  python export_phonon_bands_json.py --solver-comparison \
      --result-dir test_primitive/diamond_primitive_dftb_3x3x3 \
      --result-dir test_primitive/diamond_primitive_mmff_3x3x3 \
      --q-path-file plots/diamond_qpath_280.dat \
      --output plots/diamond_solver_comparison.json \
      --html plots/diamond_solver_comparison.html --embed --png plots/diamond_solver_comparison.png
"""

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

from plot_phonon_comparison import read_phonon_bands_npz, make_label, validate_qpath_match
from phonon_utils import QPath, build_solver_comparison_payload


def load_dataset(path, user_label=None):
    data = read_phonon_bands_npz(path)
    return {
        "name": make_label(data, user_label),
        "frequencies": data["freqs"].tolist(),
        "visible": True,
        "qpts": data["qpts"],
        "distances": data["distances"],
        "labels": data.get("labels", []),
        "path": path,
    }


def export_json(calc_paths, labels, output, title=None):
    if not calc_paths:
        raise ValueError("No --calc files provided")
    datasets = []
    master_qpts = None
    master_dists = None
    master_labels = None
    for i, path in enumerate(calc_paths):
        if not os.path.exists(path):
            print(f"[SKIP] {path}: not found")
            continue
        user_label = labels[i] if labels and i < len(labels) else None
        ds = load_dataset(path, user_label)
        if master_qpts is None:
            master_qpts = ds["qpts"]
            master_dists = ds["distances"]
            master_labels = ds["labels"]
        elif not validate_qpath_match(master_qpts, ds["qpts"], ds["name"]):
            continue
        datasets.append({"name": ds["name"], "frequencies": ds["frequencies"], "visible": True})
        print(f"[export] {ds['name']}: {len(ds['frequencies'])} qpts, {len(ds['frequencies'][0])} bands")
    if not datasets:
        print("ERROR: no valid datasets exported")
        sys.exit(1)
    tick_pos, tick_lab = [], []
    seen = set()
    for d, lab in zip(master_dists, master_labels):
        if lab and lab not in seen:
            tick_pos.append(float(d))
            tick_lab.append(str(lab))
            seen.add(lab)
    payload = {
        "title": title or "Phonon Band Comparison",
        "qpts": master_qpts.tolist(),
        "distances": master_dists.tolist(),
        "labels": list(master_labels) if master_labels is not None else [],
        "tick_positions": tick_pos,
        "tick_labels": tick_lab,
        "datasets": datasets,
    }
    os.makedirs(os.path.dirname(output) if os.path.dirname(output) else ".", exist_ok=True)
    with open(output, "w") as f:
        json.dump(payload, f)
    print(f"[export] Saved {output} ({len(datasets)} datasets)")
    return payload


def write_html(json_path, html_path, embed=False, payload=None):
    viewer_src = Path(__file__).parent / "phonon_bands_viewer.html"
    if not viewer_src.exists():
        raise FileNotFoundError(f"Viewer template not found: {viewer_src}")
    with open(viewer_src) as f:
        html = f.read()
    if embed:
        if payload is None:
            with open(json_path) as f:
                payload = json.load(f)
        html = html.replace("/*__PHONON_DATA__*/null;", json.dumps(payload) + ";")
        html = html.replace('data-file="phonon_bands.json"', 'data-file=""')
    else:
        json_name = os.path.basename(json_path)
        html = html.replace('data-file="phonon_bands.json"', f'data-file="{json_name}"')
    os.makedirs(os.path.dirname(html_path) if os.path.dirname(html_path) else ".", exist_ok=True)
    with open(html_path, "w") as f:
        f.write(html)
    print(f"[export] Saved {html_path}")


def export_solver_comparison(result_dirs, qpath_file, output, config=None, title=None):
    qpath = QPath.from_file(qpath_file)
    payload = build_solver_comparison_payload(result_dirs, qpath, config=config, title=title)
    os.makedirs(os.path.dirname(output) if os.path.dirname(output) else ".", exist_ok=True)
    with open(output, "w") as f:
        json.dump(payload, f)
    print(f"[export] Saved {output} ({len(payload['datasets'])} datasets)")
    return payload


def write_comparison_png(payload, png_path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    dists = payload["distances"]
    fig, ax = plt.subplots(figsize=(12, 7))
    colors = plt.cm.tab10(np.linspace(0, 1, 10))
    for i, ds in enumerate(payload["datasets"]):
        freqs = np.array(ds["frequencies"])
        c = colors[i % len(colors)]
        ls = "--" if "phonopy" in ds["name"] else "-"
        lw = 2.0 if ds.get("visible", True) else 1.0
        alpha = 0.85 if ds.get("visible", True) else 0.35
        for b in range(freqs.shape[1]):
            ax.plot(dists, freqs[:, b], color=c, ls=ls, lw=lw, alpha=alpha)
        ax.plot([], [], color=c, ls=ls, label=ds["name"], lw=2)
    if payload.get("tick_positions"):
        ax.set_xticks(payload["tick_positions"])
        ax.set_xticklabels(payload["tick_labels"], fontsize=11)
        for p in payload["tick_positions"]:
            ax.axvline(x=p, color="k", lw=0.4, alpha=0.25)
    ax.set_ylabel("Frequency (THz)")
    ax.set_xlabel("Wave Vector")
    ax.set_ylim(bottom=-12 if any("signed" in d["name"] for d in payload["datasets"]) else 0)
    ax.legend(loc="upper right", fontsize=8, ncol=2)
    ax.grid(axis="y", alpha=0.3)
    ax.set_title(payload.get("title", "Solver comparison"), fontsize=12)
    plt.tight_layout()
    os.makedirs(os.path.dirname(png_path) if os.path.dirname(png_path) else ".", exist_ok=True)
    plt.savefig(png_path, dpi=200)
    plt.close()
    print(f"[export] Saved {png_path}")


def _load_config(path):
    if not path or not os.path.exists(path):
        return {"tools": {}, "potentials": {}}
    with open(path) as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(description="Export phonon bands to JSON for interactive viewer")
    parser.add_argument("--calc", action="append", default=None, help="phonon_bands.npz file")
    parser.add_argument("--label", action="append", default=None, help="Dataset label")
    parser.add_argument("--solver-comparison", action="store_true",
                        help="Compare phonopy vs unified solvers from cached result dirs")
    parser.add_argument("--result-dir", action="append", default=None,
                        help="Cached run directory (with phonon_bands.npz); repeat per backend")
    parser.add_argument("--q-path-file", default=None, help="Shared q-path .dat (required for --solver-comparison)")
    parser.add_argument("--config", default="phonon_config.json", help="Config for loading cached backends")
    parser.add_argument("--title", default=None, help="Plot title")
    parser.add_argument("--output", required=True, help="Output JSON path")
    parser.add_argument("--html", default=None, help="Also write standalone HTML viewer")
    parser.add_argument("--embed", action="store_true", help="Embed JSON data inside HTML (single file)")
    parser.add_argument("--png", default=None, help="Also write static PNG comparison plot")
    args = parser.parse_args()
    if args.solver_comparison:
        if not args.result_dir or not args.q_path_file:
            parser.error("--solver-comparison requires --result-dir (repeatable) and --q-path-file")
        config = _load_config(args.config)
        payload = export_solver_comparison(args.result_dir, args.q_path_file, args.output, config=config, title=args.title)
    else:
        if not args.calc:
            parser.error("Provide --calc files or use --solver-comparison")
        payload = export_json(args.calc, args.label, args.output, title=args.title)
    if args.html:
        write_html(args.output, args.html, embed=args.embed, payload=payload if args.embed else None)
    if args.png:
        write_comparison_png(payload, args.png)


if __name__ == "__main__":
    main()
