#!/usr/bin/env python3
"""
vib_spectra.py — unified CLI for molecular vibrational spectra.

Subcommands:
  run      compute frequencies + Hessians + mode XYZ (PySCF / DFTB+)
  plot     overlay stick/broadened spectra
  match    assign PySCF modes to DFTB modes via eigenvector projection
  export   backfill modes.npy from cached Hessians
  bundle   write self-contained SiCH_small_export/ for external FF fitting
  migrate  move legacy flat results/ layout into results/<mol>/<method>/
  list     show cached molecules and methods
"""

import argparse
import traceback
from pathlib import Path
from ase.build import molecule
from ase.io import read

from vib_store import (
    discover_molecules, discover_methods, migrate_flat_to_hierarchical,
    load_method, method_dir,
)
from vib_utils import (
    run_dftb_with_hessian, run_pyscf_with_hessian, export_all_results,
    filter_real_freqs, plot_hessians, relaxed_xyz_path,
)
from vib_plot import plot_overlay
from vib_match import run_match
from vib_export import export_sich_bundle, SICH_MOLECULES


def read_mol2(path):
    from openbabel import openbabel
    obConversion = openbabel.OBConversion()
    obConversion.SetInAndOutFormats('mol2', 'xyz')
    mol = openbabel.OBMol()
    obConversion.ReadFile(mol, str(path))
    xyz_tmp = '/tmp/_vibtmp_mol2.xyz'
    obConversion.WriteFile(mol, xyz_tmp)
    return read(xyz_tmp)


MOLECULES = {
    'CH4': lambda: molecule('CH4'), 'C2H6': lambda: molecule('C2H6'),
    'SiH4': lambda: molecule('SiH4'), 'Si2H6': lambda: molecule('Si2H6'),
    'adamantane': lambda: read_mol2('/home/prokop/git/CompChemUtils/data/mol/adamantane.mol2'),
    'Si10_H': lambda: read('/home/prokop/git/CompChemUtils/data/xyz/Si10_H.xyz'),
}

METHODS = {
    'dftb_mio': lambda mol, atoms, wd: run_dftb_with_hessian(mol, atoms, sk_set='mio-1-1', workdir=wd),
    'dftb_3ob': lambda mol, atoms, wd: run_dftb_with_hessian(mol, atoms, sk_set='3ob-3-1', workdir=wd),
    'dftb_matsci': lambda mol, atoms, wd: run_dftb_with_hessian(mol, atoms, sk_set='matsci-0-3', workdir=wd),
    'dftb_pbc': lambda mol, atoms, wd: run_dftb_with_hessian(mol, atoms, sk_set='pbc-0-3', workdir=wd),
    'pyscf_b3lyp': lambda mol, atoms, wd: run_pyscf_with_hessian(mol, atoms, method='b3lyp', basis='cc-pVDZ', workdir=wd),
}

DEFAULT_METHODS = {
    'CH4': ['pyscf_b3lyp', 'dftb_mio', 'dftb_3ob'],
    'C2H6': ['pyscf_b3lyp', 'dftb_mio', 'dftb_3ob'],
    'SiH4': ['pyscf_b3lyp', 'dftb_matsci', 'dftb_pbc'],
    'Si2H6': ['pyscf_b3lyp', 'dftb_matsci', 'dftb_pbc'],
    'adamantane': ['pyscf_b3lyp', 'dftb_mio', 'dftb_3ob'],
    'Si10_H': ['pyscf_b3lyp', 'dftb_matsci', 'dftb_pbc'],
}

DEFAULT_REF = 'pyscf_b3lyp_cc-pVDZ'


def cmd_run(args):
    mol_name = args.molecule
    methods = args.methods or DEFAULT_METHODS[mol_name]
    workdir = args.workdir
    Path(workdir).mkdir(parents=True, exist_ok=True)
    if args.plot_hessians:
        tags = [_method_tag(m) for m in methods]
        plot_hessians(mol_name, tags, workdir=workdir)
        return
    print(f'\n=== {mol_name} | methods: {methods} ===\n')
    atoms_in = MOLECULES[mol_name]()
    results = {}
    for mkey in methods:
        print(f'\n--- Method: {mkey} ---')
        try:
            freqs, hess, modes, method_tag = METHODS[mkey](mol_name, atoms_in, workdir)
            xyz_path = relaxed_xyz_path(mol_name, method_tag, workdir)
            atoms_opt = read(str(xyz_path)) if xyz_path.exists() else atoms_in.copy()
            results[mkey] = (freqs, hess, modes, method_tag, atoms_opt)
            print(f'  {len(filter_real_freqs(freqs))} vibrational modes, tag: {method_tag}')
        except Exception as e:
            print(f'  FAILED: {e}')
            traceback.print_exc()
    print(f'\n=== Exporting modes ===')
    for mkey, (freqs, hess, modes, method_tag, atoms_opt) in results.items():
        print(f'\n--- {mkey} ---')
        try:
            export_all_results(atoms_opt, freqs, modes, mol_name, method_tag, workdir=workdir)
        except Exception as e:
            print(f'  FAILED export: {e}')
    if args.plot and results:
        plot_overlay(mol_name, {t: f for _, f, _, t, _ in results.values()}, workdir=workdir, noshow=True)
    print(f'\n=== Summary: {mol_name} ===')
    for mkey, (freqs, hess, modes, method_tag, _) in results.items():
        d = method_dir(workdir, mol_name, method_tag)
        print(f'{mkey:15s} | {len(filter_real_freqs(freqs)):4d} modes | {d}')


def cmd_plot(args):
    plot_overlay(args.molecule, xmax=args.xmax, width=args.width, workdir=args.workdir, noshow=args.noshow)


def cmd_match(args):
    ref = args.ref or DEFAULT_REF
    tgts = args.targets
    if not tgts:
        all_tags = discover_methods(args.molecule, args.workdir)
        tgts = [t for t in all_tags if t != ref]
    run_match(args.molecule, ref, tgts, workdir=args.workdir, align=not args.no_align)


def cmd_bundle(args):
    mols = args.molecules or None
    export_sich_bundle(workdir=args.workdir, out_dir=args.out_dir, molecules=mols)


def cmd_export(args):
    """Backfill modes.npy + all_modes.xyz from cached Hessian/freq data."""
    mol_name = args.molecule
    tags = args.methods or discover_methods(mol_name, args.workdir)
    if not tags:
        print(f'No methods found for {mol_name}')
        return
    for tag in tags:
        print(f'\n--- export {mol_name}/{tag} ---')
        rec = load_method(mol_name, tag, workdir=args.workdir)
        if rec['atoms'] is None:
            print('  skip: no relaxed.xyz')
            continue
        export_all_results(rec['atoms'], rec['freqs'], rec['all_modes'], mol_name, tag, workdir=args.workdir)
        print(f'  {len(rec["modes"])} vib modes -> {method_dir(args.workdir, mol_name, tag)}')


def cmd_migrate(args):
    moved = migrate_flat_to_hierarchical(args.workdir, dry_run=args.dry_run)
    if not moved:
        print('Nothing to migrate.')
        return
    print(f'{"[dry-run] " if args.dry_run else ""}{len(moved)} files:')
    for src, dst in moved:
        print(f'  {src} -> {dst}')


def cmd_list(args):
    mols = discover_molecules(args.workdir)
    if not mols:
        print(f'No results in {args.workdir}')
        return
    for mol in mols:
        tags = discover_methods(mol, args.workdir)
        print(f'{mol}: {", ".join(tags) if tags else "(flat cache only)"}')


def _method_tag(mkey):
    if mkey.startswith('dftb_'):
        return f'dftb_{mkey.replace("dftb_", "")}'
    if mkey.startswith('pyscf_'):
        return f'pyscf_{mkey.replace("pyscf_", "")}_cc-pVDZ'
    return mkey


def _add_workdir(p):
    p.add_argument('--workdir', default='results', help='Root results directory')


def main():
    parser = argparse.ArgumentParser(description='Molecular vibrational spectra pipeline')
    sub = parser.add_subparsers(dest='command', required=True)

    p_run = sub.add_parser('run', help='Compute vibrations')
    _add_workdir(p_run)
    p_run.add_argument('molecule', choices=list(MOLECULES.keys()))
    p_run.add_argument('--methods', nargs='+', choices=list(METHODS.keys()))
    p_run.add_argument('--plot', action='store_true')
    p_run.add_argument('--plot-hessians', action='store_true')
    p_run.set_defaults(func=cmd_run)

    p_plot = sub.add_parser('plot', help='Plot overlay spectra')
    _add_workdir(p_plot)
    p_plot.add_argument('molecule', choices=list(MOLECULES.keys()))
    p_plot.add_argument('--xmax', type=float, default=3500)
    p_plot.add_argument('--width', type=float, default=20)
    p_plot.add_argument('--noshow', action='store_true')
    p_plot.set_defaults(func=cmd_plot)

    p_match = sub.add_parser('match', help='Match modes ref vs target(s) by projection')
    _add_workdir(p_match)
    p_match.add_argument('molecule', choices=list(MOLECULES.keys()))
    p_match.add_argument('--ref', help=f'Reference method tag (default {DEFAULT_REF})')
    p_match.add_argument('--targets', nargs='+', help='Target method tags (default: all except ref)')
    p_match.add_argument('--no-align', action='store_true', help='Skip Kabsch alignment of geometries')
    p_match.set_defaults(func=cmd_match)

    p_exp = sub.add_parser('export', help='Backfill modes.npy from cache')
    _add_workdir(p_exp)
    p_exp.add_argument('molecule', choices=list(MOLECULES.keys()))
    p_exp.add_argument('--methods', nargs='+', help='Method tags (default: all cached)')
    p_exp.set_defaults(func=cmd_export)

    p_bundle = sub.add_parser('bundle', help='Export SiCH_small_export/ for external FF fitting')
    _add_workdir(p_bundle)
    p_bundle.add_argument('--out-dir', default='SiCH_small_export', help='Output folder')
    p_bundle.add_argument('--molecules', nargs='+', choices=list(SICH_MOLECULES), help='Subset (default: all SiCH)')
    p_bundle.set_defaults(func=cmd_bundle)

    p_mig = sub.add_parser('migrate', help='Migrate flat layout to hierarchical')
    _add_workdir(p_mig)
    p_mig.add_argument('--dry-run', action='store_true')
    p_mig.set_defaults(func=cmd_migrate)

    p_list = sub.add_parser('list', help='List cached molecules/methods')
    _add_workdir(p_list)
    p_list.set_defaults(func=cmd_list)

    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
