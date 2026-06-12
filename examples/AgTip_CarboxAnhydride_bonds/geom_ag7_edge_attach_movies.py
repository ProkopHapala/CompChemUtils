#!/usr/bin/env python3

import os
import argparse

from py.geom_engine import generate_edge_attach_movie


def _infer_anchor_element(mol_path):
    b = os.path.basename(mol_path).lower()
    if 'pyridin' in b or 'pyridine' in b:
        return 'N'
    return None


def main():
    parser = argparse.ArgumentParser(description='Generate Ag7(adatom-pair edge) + molecule tilt movies (cluster)')
    parser.add_argument('--substrates', nargs='*', default=[
        'data/xyz/Ag7sym.xyz',
        'data/xyz/Ag7asym.xyz',
    ], help='Substrate XYZs')
    parser.add_argument('--outdir', default='tmp/ag7_edge_movies', help='Output directory')
    parser.add_argument('--lift', type=float, default=2.0, help='Anchor height above edge midpoint along +z (A)')
    parser.add_argument('--tilts', type=float, nargs='*', default=[0.0, 15.0, 30.0], help='Tilts around edge axis (deg)')
    parser.add_argument('--origin-mode', default='axis_mid', choices=['axis_mid', 'anchor'])
    parser.add_argument('--target-up-mode', default='standing', choices=['standing', 'flat'])
    parser.add_argument('--mols', nargs='*', default=[
        'data/xyz/maleic_anhydride.xyz',
        'data/xyz/NDCA.xyz',
        'data/xyz/dihydroxy_pyridin.xyz',
    ])
    args = parser.parse_args()

    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    outdir = os.path.join(repo, args.outdir)
    os.makedirs(outdir, exist_ok=True)

    subs = []
    for s in args.substrates:
        subs.append(s if os.path.isabs(s) else os.path.join(repo, s))

    for sub_xyz in subs:
        subtag = os.path.splitext(os.path.basename(sub_xyz))[0]
        for mol_rel in args.mols:
            mol_xyz = mol_rel
            if not os.path.isabs(mol_xyz):
                mol_xyz = os.path.join(repo, mol_rel)
            tag = os.path.splitext(os.path.basename(mol_xyz))[0]
            out_xyz = os.path.join(outdir, f'{tag}_{subtag}_edge_tilts.xyz')

            anchor_element = _infer_anchor_element(mol_xyz)

            res = generate_edge_attach_movie(
                mol_xyz=mol_xyz,
                substrate_xyz=sub_xyz,
                out_xyz=out_xyz,
                tilts_deg=tuple(args.tilts),
                lift=float(args.lift),
                anchor_element=anchor_element,
                origin_mode=args.origin_mode,
                target_up_mode=args.target_up_mode,
            )
            print(f"Wrote {res['n_frames']} frames to {out_xyz}  edge_pair={res['edge_pair']} anchor={res['anchor_index']} axis_pair={res['axis_pair']}")


if __name__ == '__main__':
    main()
