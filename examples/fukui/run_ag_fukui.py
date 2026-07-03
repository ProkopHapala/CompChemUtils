#!/usr/bin/env python3
"""Fukui function cubes for metal clusters (Ag, Au) via PySCF.

Runs single-point DFT for N, N+1, N-1 charge states at fixed geometry,
writes electron-density .cube files, then subtracts them to obtain
f+, f-, f0 Fukui grids.

Usage:
    python run_metal_fukui.py --mol Ag4 --basis def2-svp
    python run_metal_fukui.py --mol Au4 --basis lanl2dz

Results are written to results/<cluster>_<xc>_<basis>/.
"""

import os
import sys
import argparse

fukui_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, fukui_dir)
from fukui_backend import run_fukui_for_molecule, read_xyz

XYZ_DIR = '/home/prokop/git/CompChemUtils/data/xyz'
OUTDIR = os.path.join(fukui_dir, 'results_metal')

# Spin multiplicities: mol.spin = 2S = Nalpha - Nbeta
# Ag/Au: def2-svp ECP replaces 28 core -> 19 valence e-/atom.
# Cu: def2-svp ECP replaces 10 core -> 11 valence e-/atom.
# 4 atoms: 4*19 = 76 val e- (Ag/Au) -> neutral spin=0, anion spin=1, cation spin=1
# 4 atoms: 4*11 = 44 val e- (Cu) -> neutral spin=0, anion spin=1, cation spin=1
# 7 atoms: 7*19 = 133 val e- -> neutral spin=1, anion spin=0, cation spin=0
CLUSTER_SPECS = {
    'Ag4':     {'spin_N': 0, 'spin_A': 1, 'spin_C': 1},
    'Ag7sym':  {'spin_N': 1, 'spin_A': 0, 'spin_C': 0},
    'Ag7asym': {'spin_N': 1, 'spin_A': 0, 'spin_C': 0},
    'Au4':     {'spin_N': 0, 'spin_A': 1, 'spin_C': 1},
    'Cu4':     {'spin_N': 0, 'spin_A': 1, 'spin_C': 1},
}


def main():
    parser = argparse.ArgumentParser(description='Fukui cubes for Ag clusters (PySCF PBE/def2-svp)')
    parser.add_argument('--mol', type=str, default=None,
                        help='Run only one cluster (Ag4, Ag7sym, Ag7asym). Default: all.')
    parser.add_argument('--basis', type=str, default='def2-svp',
                        help='Basis set (default: def2-svp — valence single-zeta + ECP for Ag)')
    parser.add_argument('--xc', type=str, default='pbe',
                        help='XC functional (default: pbe)')
    parser.add_argument('--resolution', type=float, default=0.20,
                        help='Cube grid resolution in Angstrom (default: 0.20)')
    parser.add_argument('--margin', type=float, default=5.0,
                        help='Cube box margin in Angstrom (default: 5.0)')
    parser.add_argument('--smearing', type=float, default=0.01,
                        help='Fermi-Dirac smearing width in Hartree (default: 0.01 for metallic clusters)')
    parser.add_argument('--outdir', type=str, default=OUTDIR,
                        help='Output directory (default: results_Ag/)')
    args = parser.parse_args()

    clusters = [args.mol] if args.mol else list(CLUSTER_SPECS.keys())

    for name in clusters:
        spec = CLUSTER_SPECS.get(name)
        if spec is None:
            print(f"ERROR: Unknown cluster '{name}'. Available: {list(CLUSTER_SPECS.keys())}")
            sys.exit(1)

        xyz_path = os.path.join(XYZ_DIR, f'{name}.xyz')
        if not os.path.isfile(xyz_path):
            print(f"ERROR: XYZ file not found: {xyz_path}")
            sys.exit(1)

        geom = read_xyz(xyz_path)
        print(f"\n{'='*60}")
        print(f"  Cluster: {name}  ({len(geom.split(';'))} atoms)")
        print(f"  Method:  {args.xc} / {args.basis}")
        print(f"  Grid:    {args.resolution} A, margin {args.margin} A")
        print(f"  Smearing: {args.smearing} Ha")
        print(f"{'='*60}")

        subdir = f"{name}_{args.xc}_{args.basis.replace('-','')}"
        resdir = run_fukui_for_molecule(
            subdir, geom, args.outdir,
            basis=args.basis, xc_func=args.xc,
            resolution=args.resolution, margin=args.margin,
            ecp=args.basis,
            spin_N=spec['spin_N'],
            spin_A=spec['spin_A'],
            spin_C=spec['spin_C'],
            smearing_sigma=args.smearing
        )
        print(f"  -> {resdir}")

    print(f"\n{'='*60}")
    print(f"  All done. Results in: {args.outdir}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
