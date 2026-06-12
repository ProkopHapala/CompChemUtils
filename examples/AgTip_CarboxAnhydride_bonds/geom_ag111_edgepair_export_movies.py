#!/usr/bin/env python3

import os
import argparse

from py.export_gpaw_jobs import export_surface_edgepair_movie_from_molecule


def _infer_anchor_element(mol_path):
    b = os.path.basename(mol_path).lower()
    if 'pyridin' in b or 'pyridine' in b:
        return 'N'
    return None


def main():
    parser = argparse.ArgumentParser(description='Generate Ag(111) + two-adatom edge + molecule tilt movies (PBC)')
    parser.add_argument('--outdir', default='tmp/ag111_edgepair_movies', help='Output directory')
    parser.add_argument('--lift', type=float, default=2.0, help='Anchor height above edge midpoint along +z (A)')
    parser.add_argument('--tilts', type=float, nargs='*', default=[0.0, 15.0, 30.0], help='Tilts around edge axis (deg)')
    parser.add_argument('--size', type=int, nargs=3, default=[2, 2, 2], help='Surface size nx ny nz')
    parser.add_argument('--a', type=float, default=4.086, help='Ag lattice constant (A)')
    parser.add_argument('--vacuum', type=float, default=10.0, help='Vacuum (A)')
    parser.add_argument('--adatom-height', type=float, default=2.0, help='Adatom height above top layer (A)')
    parser.add_argument('--shift-frac', type=float, nargs=2, default=[0.5, 0.0], help='Second adatom shift in (a0,a1) fractional coords')
    parser.add_argument('--origin-mode', default='axis_mid', choices=['axis_mid', 'anchor'])
    parser.add_argument('--target-up-mode', default='standing', choices=['standing', 'flat'])
    parser.add_argument('--export-structs', action='store_true', help='Write extxyz/cif/POSCAR for each tilt')
    parser.add_argument('--mols', nargs='*', default=[
        'data/xyz/maleic_anhydride.xyz',
        'data/xyz/NDCA.xyz',
        'data/xyz/dihydroxy_pyridin.xyz',
    ])
    args = parser.parse_args()

    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    outdir = os.path.join(repo, args.outdir)
    os.makedirs(outdir, exist_ok=True)

    for mol_rel in args.mols:
        mol_xyz = mol_rel
        if not os.path.isabs(mol_xyz):
            mol_xyz = os.path.join(repo, mol_rel)
        tag = os.path.splitext(os.path.basename(mol_xyz))[0]

        out_xyz = os.path.join(outdir, f'{tag}_Ag111_edgepair_tilts.xyz')
        frame_dir = os.path.join(outdir, f'{tag}_frames') if args.export_structs else None

        anchor_element = _infer_anchor_element(mol_xyz)

        res = export_surface_edgepair_movie_from_molecule(
            mol_xyz=mol_xyz,
            out_xyz=out_xyz,
            surface_size=tuple(args.size),
            a=float(args.a),
            vacuum=float(args.vacuum),
            adatom_height=float(args.adatom_height),
            shift_frac=tuple(float(x) for x in args.shift_frac),
            lift=float(args.lift),
            tilts_deg=tuple(float(x) for x in args.tilts),
            anchor_element=anchor_element,
            origin_mode=args.origin_mode,
            target_up_mode=args.target_up_mode,
            outdir_struct=frame_dir,
        )

        print(f"Wrote {res['n_frames']} frames to {out_xyz}  adatom_pair={res['adatom_pair']} anchor={res['anchor_index']} axis_pair={res['axis_pair']}")
        if frame_dir is not None:
            print(f"Wrote per-frame structures to {frame_dir}")


if __name__ == '__main__':
    main()
