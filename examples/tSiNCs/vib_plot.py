#!/usr/bin/env python3
"""Plotting for vibrational spectra."""

import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

from vib_store import discover_methods, load_method, overlay_png_path
from vib_utils import filter_real_freqs

COLORS = ['tab:blue', 'tab:red', 'tab:green', 'tab:orange', 'tab:purple', 'tab:brown', 'tab:pink', 'tab:olive']

METHOD_LABELS = {
    'dftb_mio-1-1': 'DFTB+ mio-1-1', 'dftb_3ob-3-1': 'DFTB+ 3ob-3-1',
    'dftb_matsci-0-3': 'DFTB+ matsci-0-3', 'dftb_pbc-0-3': 'DFTB+ pbc-0-3',
    'pyscf_b3lyp_cc-pVDZ': 'PySCF B3LYP/cc-pVDZ', 'pyscf_b3lyp_ccpVDZ': 'PySCF B3LYP/cc-pVDZ',
}


def broaden(freqs, x, width):
    spec = np.zeros_like(x)
    for f in freqs:
        spec += np.exp(-((x - f) ** 2) / (2 * width ** 2))
    return spec


def load_all(mol_name, workdir='.', method_tags=None):
    tags = method_tags or discover_methods(mol_name, workdir)
    data = {}
    for tag in tags:
        rec = load_method(mol_name, tag, workdir=workdir)
        data[tag] = rec['freqs']
        print(f'  Loaded {tag}: {len(rec["freqs"])} modes')
    return data


def plot_overlay(mol_name, data=None, xmax=3500, width=20, workdir='.', noshow=True, method_tags=None):
    if data is None:
        data = load_all(mol_name, workdir=workdir, method_tags=method_tags)
    assert data, f'No frequency data for {mol_name}'
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 8), sharex=True)
    fig.suptitle(f'Vibrational spectra — {mol_name}', fontsize=14)
    x = np.arange(0, xmax + 1, 0.5)
    for i, (tag, freqs) in enumerate(data.items()):
        color = COLORS[i % len(COLORS)]
        label = METHOD_LABELS.get(tag, tag)
        rf = filter_real_freqs(freqs, threshold=10.0)
        ax1.vlines(rf, 0, 1, color=color, linewidth=0.8, alpha=0.7, label=label)
        spec = broaden(rf, x, width)
        if spec.max() > 0:
            spec /= spec.max()
        ax2.plot(x, spec, color=color, linewidth=1.5, label=label, alpha=0.85)
    ax1.set_ylabel('Stick intensity (arb.)', fontsize=11)
    ax1.set_ylim(0, 1.3)
    ax1.legend(fontsize=9, loc='upper left')
    ax1.grid(True, alpha=0.25)
    ax1.tick_params(labelbottom=False)
    ax2.set_xlabel('Frequency (cm$^{-1}$)', fontsize=12)
    ax2.set_ylabel('Intensity (normalized)', fontsize=11)
    ax2.set_xlim(0, xmax)
    ax2.legend(fontsize=9, loc='upper left')
    ax2.grid(True, alpha=0.25)
    plt.tight_layout()
    out = overlay_png_path(mol_name, workdir)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(out), dpi=150)
    print(f'Saved: {out}')
    if not noshow:
        plt.show()
    return fig
