#!/usr/bin/env python3
"""
run_vib_spectra.py - Compute vibrational spectra with Hessian caching for small molecules.

Usage:
    python run_vib_spectra.py CH4
    python run_vib_spectra.py SiH4
    python run_vib_spectra.py CH4 --methods pyscf_b3lyp_dftb_mio

Caches: relaxed XYZ, Hessian .npy, frequencies .npy, ASCII modes, multi-frame XYZ.
"""

import argparse
import numpy as np
from ase.build import molecule
from ase.io import read
from pathlib import Path
from vib_utils import (
    run_dftb_with_hessian, run_pyscf_with_hessian,
    freq_npy_path, relaxed_xyz_path, export_all_results,
    filter_real_freqs, plot_hessians
)

def read_mol2(path):
    """Read mol2 via OpenBabel conversion to XYZ, then ASE."""
    from openbabel import openbabel
    obConversion = openbabel.OBConversion()
    obConversion.SetInAndOutFormats('mol2', 'xyz')
    mol = openbabel.OBMol()
    obConversion.ReadFile(mol, str(path))
    xyz_tmp = '/tmp/_vibtmp_adamantane.xyz'
    obConversion.WriteFile(mol, xyz_tmp)
    return read(xyz_tmp)

MOLECULES = {
    'CH4':        lambda: molecule('CH4'),
    'SiH4':       lambda: molecule('SiH4'),
    'adamantane': lambda: read_mol2('/home/prokop/git/CompChemUtils/data/mol/adamantane.mol2'),
    'Si10_H':     lambda: read('/home/prokop/git/CompChemUtils/data/xyz/Si10_H.xyz'),
}

METHODS = {
    'dftb_mio':    lambda mol, atoms, wd: run_dftb_with_hessian(mol, atoms, sk_set='mio-1-1',    workdir=wd),
    'dftb_3ob':    lambda mol, atoms, wd: run_dftb_with_hessian(mol, atoms, sk_set='3ob-3-1',    workdir=wd),
    'dftb_matsci': lambda mol, atoms, wd: run_dftb_with_hessian(mol, atoms, sk_set='matsci-0-3', workdir=wd),
    'dftb_pbc':    lambda mol, atoms, wd: run_dftb_with_hessian(mol, atoms, sk_set='pbc-0-3',    workdir=wd),
    'pyscf_b3lyp': lambda mol, atoms, wd: run_pyscf_with_hessian(mol, atoms, method='b3lyp', basis='cc-pVDZ', workdir=wd),
}

DEFAULT_METHODS = {
    'CH4':        ['pyscf_b3lyp', 'dftb_mio', 'dftb_3ob'],
    'SiH4':       ['pyscf_b3lyp', 'dftb_matsci', 'dftb_pbc'],
    'adamantane': ['pyscf_b3lyp', 'dftb_mio', 'dftb_3ob'],
    'Si10_H':     ['pyscf_b3lyp', 'dftb_matsci', 'dftb_pbc'],
}


def main():
    parser = argparse.ArgumentParser(description='Compute vibrational spectra with Hessian caching')
    parser.add_argument('molecule', choices=list(MOLECULES.keys()), help='Molecule to compute')
    parser.add_argument('--methods', nargs='+', choices=list(METHODS.keys()),
                        help='Methods to use (default: per-molecule defaults)')
    parser.add_argument('--workdir', default='.', help='Directory for cached files and output')
    parser.add_argument('--plot', action='store_true', help='Generate overlay plot after computation')
    parser.add_argument('--plot-hessians', action='store_true', help='Plot cached Hessian matrices side-by-side')
    args = parser.parse_args()

    mol_name = args.molecule
    methods = args.methods or DEFAULT_METHODS[mol_name]
    workdir = args.workdir
    Path(workdir).mkdir(parents=True, exist_ok=True)

    # Plot-only mode for Hessians
    if args.plot_hessians:
        print(f"\n=== Plotting Hessian comparison for {mol_name} ===")
        method_tags = []
        for mkey in methods:
            if mkey.startswith('dftb_'):
                sk_set = mkey.replace('dftb_', '')
                tag = f'dftb_{sk_set}'
            elif mkey.startswith('pyscf_'):
                method = mkey.replace('pyscf_', '')
                tag = f'pyscf_{method}_ccpVDZ'
            else:
                tag = mkey
            method_tags.append(tag)
        plot_hessians(mol_name, method_tags, workdir=workdir)
        return

    print(f"\n=== {mol_name} | methods: {methods} ===\n")
    atoms_in = MOLECULES[mol_name]()

    results = {}  # mkey -> (freqs, hessian, modes, method_tag, atoms_opt)
    for mkey in methods:
        print(f"\n--- Method: {mkey} ---")
        try:
            freqs, hess, modes, method_tag = METHODS[mkey](mol_name, atoms_in, workdir)
            # Load relaxed geometry for export
            xyz_path = relaxed_xyz_path(mol_name, method_tag, workdir)
            from ase.io import read
            atoms_opt = read(str(xyz_path)) if xyz_path.exists() else atoms_in.copy()
            results[mkey] = (freqs, hess, modes, method_tag, atoms_opt)
            n_vib = len(filter_real_freqs(freqs))
            print(f"  {n_vib} vibrational modes, tag: {method_tag}")
        except Exception as e:
            print(f"  FAILED: {e}")
            import traceback
            traceback.print_exc()
            continue

    # Export all results (ASCII + XYZ) for each method
    print(f"\n=== Exporting modes (ASCII + XYZ) ===")
    for mkey, (freqs, hess, modes, method_tag, atoms_opt) in results.items():
        print(f"\n--- {mkey} ---")
        try:
            export_all_results(atoms_opt, freqs, modes, mol_name, method_tag, workdir=workdir)
        except Exception as e:
            print(f"  FAILED export: {e}")

    # Summary
    print(f"\n=== Summary: {mol_name} ===")
    print("Method          |  Real modes  |  Tag")
    print("-" * 60)
    for mkey, (freqs, hess, modes, method_tag, atoms_opt) in results.items():
        n_vib = len(filter_real_freqs(freqs))
        print(f"{mkey:15s} |  {n_vib:4d}       |  {method_tag}")
        print(f"  freqs:  {freq_npy_path(mol_name, method_tag, workdir)}")
        print(f"  hess:   {Path(workdir) / f'{mol_name}_{method_tag}_hessian.npy'}")
        print(f"  modes:  {Path(workdir) / f'{mol_name}_{method_tag}_modes.txt'}")
        print(f"  xyz:    {Path(workdir) / f'{mol_name}_{method_tag}_all_modes.xyz'}")

    # Generate overlay plot
    if args.plot and results:
        print(f"\n=== Generating overlay plot ===")
        from plot_vib_spectra import plot_overlay
        data = {}
        for mkey, (freqs, hess, modes, method_tag, atoms_opt) in results.items():
            data[method_tag] = freqs
        plot_overlay(mol_name, data, xmax=3500, width=20, workdir=workdir, noshow=True)

    # Print numerical comparison
    print(f"\n=== Frequency comparison (cm^-1) ===")
    for mkey, (freqs, hess, modes, method_tag, atoms_opt) in results.items():
        rf = filter_real_freqs(freqs)
        print(f"\n{mkey:15s} ({method_tag}):")
        print(f"  {rf}")


if __name__ == '__main__':
    main()
