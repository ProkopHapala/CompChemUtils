#!/usr/bin/env python3
"""Export phonon band data from multiple calculators to a single text file.

Output format:
    qx qy qz distance method1_b1 ... method1_bN method2_b1 ... method2_bN ... label

Usage:
    python export_phonon_bands.py --material Si --results-dir phonon_results
                                  --output Si_phonon_bands.dat
                                  --phonondb-ref phonondb_ref/Si_phonondb_band.yaml
"""

import argparse
import os
import sys
import yaml
import numpy as np


def read_band_yaml(path):
    """Read phonopy band.yaml and return q-positions, distances, frequencies, labels."""
    with open(path) as f:
        data = yaml.safe_load(f)

    nq = data["nqpoint"]
    phonon = data["phonon"]

    qpts = []
    dists = []
    freqs = []
    labels = []
    for q in phonon:
        qpts.append(q["q-position"])
        dists.append(q["distance"])
        freqs.append([b["frequency"] for b in q["band"]])
        labels.append(q.get("label", ""))

    return np.array(qpts), np.array(dists), np.array(freqs), labels


def discover_band_yamls(results_dir, material):
    """Find all band.yaml files for a given material."""
    bands = {}
    if not os.path.isdir(results_dir):
        return bands

    for subdir in os.listdir(results_dir):
        subpath = os.path.join(results_dir, subdir)
        if not os.path.isdir(subpath):
            continue
        if not subdir.startswith(material):
            continue
        band_yaml = os.path.join(subpath, "band.yaml")
        if os.path.exists(band_yaml):
            label = subdir.replace(f"{material}_", "").replace("_2x2x2", "")
            bands[label] = band_yaml
    return bands


def export_bands(material, results_dir, output, phonondb_ref=None):
    bands = discover_band_yamls(results_dir, material)

    if phonondb_ref and os.path.exists(phonondb_ref):
        bands["phonondb_DFT"] = phonondb_ref

    if not bands:
        print(f"ERROR: No band.yaml files found for {material} in {results_dir}")
        sys.exit(1)

    # Read all data
    data_all = {}
    for label, path in bands.items():
        try:
            qpts, dists, freqs, labels = read_band_yaml(path)
            data_all[label] = (qpts, dists, freqs, labels)
        except Exception as e:
            print(f"WARNING: Could not read {path}: {e}")

    if not data_all:
        print("ERROR: No valid band.yaml files could be read")
        sys.exit(1)

    # Use first calculator as reference for q-points
    ref_label = list(data_all.keys())[0]
    ref_qpts, ref_dists, ref_freqs, ref_labels = data_all[ref_label]
    nq = len(ref_qpts)
    nbands = ref_freqs.shape[1]

    print(f"[export] Material: {material}")
    print(f"[export] nqpoint: {nq}, nbands: {nbands}")
    print(f"[export] Methods: {list(data_all.keys())}")

    # Verify alignment
    for label, (qpts, dists, freqs, labels) in data_all.items():
        if len(qpts) != nq:
            print(f"WARNING: {label} has {len(qpts)} qpoints, expected {nq}")
            continue
        max_qdiff = np.max(np.abs(qpts - ref_qpts))
        if max_qdiff > 1e-6:
            print(f"WARNING: {label} q-points differ by {max_qdiff}")

    # Build header
    header = "# qx qy qz distance"
    for label in data_all.keys():
        for b in range(nbands):
            header += f" {label}_b{b+1}"
    header += " label\n"

    with open(output, "w") as f:
        f.write(header)
        for i in range(nq):
            q = ref_qpts[i]
            dist = ref_dists[i]
            line = f"{q[0]:12.8f} {q[1]:12.8f} {q[2]:12.8f} {dist:12.8f}"
            for label in data_all.keys():
                qpts, dists, freqs, labels = data_all[label]
                for b in range(nbands):
                    line += f" {freqs[i, b]:14.8f}"
            line += f" {ref_labels[i]}\n"
            f.write(line)

    print(f"[export] Saved to {output}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--material", choices=["Si", "diamond"], required=True)
    parser.add_argument("--results-dir", default="phonon_results")
    parser.add_argument("--phonondb-ref", default=None)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    export_bands(args.material, args.results_dir, args.output, args.phonondb_ref)


if __name__ == "__main__":
    main()
