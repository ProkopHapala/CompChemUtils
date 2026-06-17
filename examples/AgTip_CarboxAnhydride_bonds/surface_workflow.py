#!/usr/bin/env python3
"""
surface_workflow.py — unified CLI for metal-surface + molecule geometry generation and QC export.

Replaces:
    geom_ag111_export_movies.py
    geom_ag111_edgepair_export_movies.py
    geom_ag4_attach_movies.py
    geom_ag7_edge_attach_movies.py
    geom_ag111_edgepair_gpaw_inputs.py
    geom_psi4_export_inputs.py
    geom_ag7_edge_psi4_inputs.py

Usage:
    python surface_workflow.py generate-adatom --metal Ag --molecules data/xyz/H2O.xyz --outdir DIR
    python surface_workflow.py generate-edgepair --metal Ag --molecules mol.xyz --outdir DIR
    python surface_workflow.py generate-cluster --mode apex --substrate data/xyz/Ag4.xyz --molecules mol.xyz --outdir DIR
    python surface_workflow.py generate-cluster --mode edge --substrates Ag7sym.xyz Ag7asym.xyz --molecules mol.xyz --outdir DIR
    python surface_workflow.py export-qc --backend psi4 --movie FILE.xyz --outdir DIR
    python surface_workflow.py export-qc --backend psi4 --movie-dir DIR --outdir DIR
    python surface_workflow.py export-qc --backend gpaw --frame-dir DIR --outdir DIR
"""

import os
import sys
import argparse

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from py.interfaces import gpaw as egj
from py import geom_engine as ge
from py.interfaces.psi4 import Psi4Backend
from py import plotUtils as pu

import matplotlib.pyplot as plt


# =============================================================
#  Shared helpers
# =============================================================

def _infer_anchor_element(mol_path: str) -> str:
    b = os.path.basename(mol_path).lower()
    if 'pyridin' in b or 'pyridine' in b:
        return 'N'
    return None


def _tag_from_path(path: str) -> str:
    return os.path.splitext(os.path.basename(path))[0]


def _add_molecule_args(sub, outdir_default: str):
    """Add common molecule-loop arguments to a subparser."""
    sub.add_argument('--molecules', nargs='+', required=True, help='Molecule XYZ file(s)')
    sub.add_argument('--outdir', default=outdir_default, help='Output directory')


def _add_surface_args(sub):
    """Add common ASE surface-build arguments to a subparser."""
    sub.add_argument('--metal', default='Ag', help='Metal symbol (e.g. Cu, Ag, Au)')
    sub.add_argument('--size', type=int, nargs=3, default=[2, 2, 2], help='Surface supercell (calculation cell)')
    sub.add_argument('--a', type=float, default=None, help='Lattice constant (A); auto if omitted')
    sub.add_argument('--vacuum', type=float, default=10.0, help='Vacuum (A)')
    sub.add_argument('--adatom-height', type=float, default=2.0, help='Adatom height (A)')
    sub.add_argument('--export-structs', action='store_true', help='Write extxyz/cif/POSCAR per frame')


def _add_tilt_args(sub, default_tilts=(20.0, 45.0)):
    """Add common tilt/angle arguments."""
    sub.add_argument('--tilts', type=float, nargs='*', default=list(default_tilts))


def _add_viz_args(sub):
    """Add visualization arguments."""
    sub.add_argument('--visualize', action='store_true', help='Generate XY/XZ preview PNG for each system')
    sub.add_argument('--viz-replicate', type=int, nargs=2, default=[1, 1], help='nx ny replication for visualization')


def _plot_preview(xyz_path, outdir, replicate=(1, 1)):
    """Load first frame and plot XY/XZ preview using plotUtils.plotGeometry."""
    try:
        from ase.io import read
    except ImportError:
        return
    atoms = read(xyz_path, index=0)
    es = list(atoms.get_chemical_symbols())
    ps = atoms.get_positions()
    lvs = atoms.get_cell()
    tag = os.path.splitext(os.path.basename(xyz_path))[0]
    fig, axes = plt.subplots(1, 2, figsize=(10, 5))
    pu.plotGeometry(ps, es, lvs=lvs, replicate=(replicate[0], replicate[1], 1),
                    axes=(0, 1), title='XY view', ax=axes[0], bDrawBox=True,
                    bAtomNumLabels=True, bBlackLabels=True, bNoEdge=True)
    pu.plotGeometry(ps, es, lvs=lvs, replicate=(replicate[0], replicate[1], 1),
                    axes=(0, 2), title='XZ view', ax=axes[1], bDrawBox=True,
                    bAtomNumLabels=True, bBlackLabels=True, bNoEdge=True)
    fig.suptitle(tag, fontsize=11)
    fig.tight_layout()
    fname = os.path.join(outdir, f'{tag}.png')
    fig.savefig(fname, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"Wrote preview {fname}")


def _loop_molecules(args, fn):
    """Loop over args.molecules, calling fn(mol_path, tag, outdir) for each."""
    os.makedirs(args.outdir, exist_ok=True)
    for mol_path in args.molecules:
        tag = _tag_from_path(mol_path)
        fn(mol_path, tag)


# =============================================================
#  generate-adatom
# =============================================================

def cmd_generate_adatom(args):
    plot_png = os.path.join(args.outdir, 'scan_directions.png') if args.plot_dirs else None

    def _one(mol_path, tag):
        out_xyz = os.path.join(args.outdir, f'{tag}_{args.metal}111_attach_orients.xyz')
        frame_dir = os.path.join(args.outdir, f'{tag}_frames') if args.export_structs else None
        plot_here = plot_png if (plot_png is not None and mol_path == args.molecules[0]) else None

        res = egj.export_surface_movie_from_molecule_frames(
            mol_xyz=mol_path,
            out_xyz=out_xyz,
            metal=args.metal,
            surface_size=tuple(args.size),
            a=args.a,
            vacuum=args.vacuum,
            adatom_height=args.adatom_height,
            dist=args.dist,
            tilt_degs=tuple(args.tilts),
            roll_degs=tuple(args.rolls),
            remove_epairs=(not args.keep_epairs),
            outdir_struct=frame_dir,
            plot_dirs_png=plot_here,
        )
        print(f"Wrote {res['n_frames']} frames to {out_xyz}  adatom_index={res['surface_adatom_index']} base3={res['base3']}")
        if frame_dir is not None:
            print(f"Wrote per-frame structures to {frame_dir}")
        if args.visualize:
            _plot_preview(out_xyz, args.outdir, replicate=tuple(args.viz_replicate))

    _loop_molecules(args, _one)
    if plot_png is not None:
        print(f"Wrote direction plot: {plot_png}")


# =============================================================
#  generate-edgepair
# =============================================================

def cmd_generate_edgepair(args):
    def _one(mol_path, tag):
        out_xyz = os.path.join(args.outdir, f'{tag}_{args.metal}111_edgepair_tilts.xyz')
        frame_dir = os.path.join(args.outdir, f'{tag}_frames') if args.export_structs else None
        anchor = _infer_anchor_element(mol_path) if args.anchor is None else args.anchor

        res = egj.export_surface_edgepair_movie_from_molecule(
            mol_xyz=mol_path,
            out_xyz=out_xyz,
            metal=args.metal,
            surface_size=tuple(args.size),
            a=args.a,
            vacuum=args.vacuum,
            adatom_height=args.adatom_height,
            shift_frac=tuple(args.shift_frac),
            lift=args.lift,
            tilts_deg=tuple(args.tilts),
            anchor_element=anchor,
            origin_mode=args.origin_mode,
            target_up_mode=args.target_up_mode,
            outdir_struct=frame_dir,
        )
        print(f"Wrote {res['n_frames']} frames to {out_xyz}  adatom_pair={res['adatom_pair']} anchor={res['anchor_index']} axis_pair={res['axis_pair']}")
        if frame_dir is not None:
            print(f"Wrote per-frame structures to {frame_dir}")
        if args.visualize:
            _plot_preview(out_xyz, args.outdir, replicate=tuple(args.viz_replicate))

    _loop_molecules(args, _one)


# =============================================================
#  generate-cluster
# =============================================================

def cmd_generate_cluster(args):
    plot_png = os.path.join(args.outdir, 'scan_directions.png') if args.plot_dirs else None

    def _one(mol_path, tag):
        plot_here = plot_png if (plot_png is not None and mol_path == args.molecules[0]) else None
        if args.mode == 'apex':
            out_xyz = os.path.join(args.outdir, f'{tag}_cluster_attach_orients.xyz')
            res = ge.generate_ag4_attach_movie(
                mol_xyz=mol_path,
                out_xyz=out_xyz,
                ag4_xyz=args.substrate,
                dist=args.dist,
                tilt_degs=tuple(args.tilts),
                roll_degs=tuple(args.rolls),
                remove_epairs=(not args.keep_epairs),
                plot_dirs_png=plot_here,
            )
            print(f"Wrote {res['n_frames']} frames to {out_xyz}  host={res['host_element']}[{res['host_index']}] dist={args.dist}")
            if args.visualize:
                _plot_preview(out_xyz, args.outdir, replicate=tuple(args.viz_replicate))
        elif args.mode == 'edge':
            for sub_path in args.substrates:
                subtag = _tag_from_path(sub_path)
                out_xyz = os.path.join(args.outdir, f'{tag}_{subtag}_edge_tilts.xyz')
                anchor = _infer_anchor_element(mol_path) if args.anchor is None else args.anchor
                res = ge.generate_edge_attach_movie(
                    mol_xyz=mol_path,
                    substrate_xyz=sub_path,
                    out_xyz=out_xyz,
                    tilts_deg=tuple(args.tilts),
                    lift=args.lift,
                    anchor_element=anchor,
                    origin_mode=args.origin_mode,
                    target_up_mode=args.target_up_mode,
                )
                print(f"Wrote {res['n_frames']} frames to {out_xyz}  edge_pair={res['edge_pair']} anchor={res['anchor_index']} axis_pair={res['axis_pair']}")
                if args.visualize:
                    _plot_preview(out_xyz, args.outdir, replicate=tuple(args.viz_replicate))

    _loop_molecules(args, _one)
    if plot_png is not None:
        print(f"Wrote direction plot: {plot_png}")


# =============================================================
#  export-qc
# =============================================================

def cmd_export_qc(args):
    if args.backend == 'psi4':
        _export_psi4(args)
    elif args.backend == 'gpaw':
        _export_gpaw(args)
    else:
        raise ValueError(f"Unknown backend '{args.backend}'")


def _export_psi4(args):
    backend = Psi4Backend(mem=args.mem)
    outdir = args.outdir or 'tmp/psi4_inputs'
    os.makedirs(outdir, exist_ok=True)
    if args.movie:
        res = backend.export_movie(
            xyz_movie=args.movie, outdir=outdir,
            method=args.method, basis=args.basis, freeze_element=args.freeze_element,
        )
        print(f"Exported {res['n_frames']} Psi4 inputs to {res['outdir']}")
    elif args.movie_dir:
        for fname in sorted(os.listdir(args.movie_dir)):
            if not fname.endswith('.xyz'):
                continue
            xyz_path = os.path.join(args.movie_dir, fname)
            tag = fname.replace('.xyz', '')
            subdir = os.path.join(outdir, tag)
            os.makedirs(subdir, exist_ok=True)
            res = backend.export_movie(
                xyz_movie=xyz_path, outdir=subdir,
                method=args.method, basis=args.basis, freeze_element=args.freeze_element,
            )
            print(f"Wrote {res['n_frames']} Psi4 inputs to {subdir}")
    else:
        raise ValueError("export-qc psi4 requires --movie or --movie-dir")


def _export_gpaw(args):
    if not args.frame_dir:
        raise ValueError("export-qc gpaw requires --frame-dir")
    outdir = args.outdir or 'tmp/gpaw_runners'
    os.makedirs(outdir, exist_ok=True)
    written = 0
    fix = list(args.fix_indices) if args.fix_indices else None
    for fname in sorted(os.listdir(args.frame_dir)):
        if not fname.endswith('.xyz'):
            continue
        struct = os.path.join(args.frame_dir, fname)
        tag = fname.replace('.xyz', '')
        runner = os.path.join(outdir, f"run_{tag}.py")
        egj.write_gpaw_runner(
            fname=runner, structure_file=struct, txt=f"gpaw_{tag}.txt",
            xc=args.xc, pw=args.pw, kpts=tuple(args.kpts), fix_indices=fix,
        )
        print(f"Wrote {runner}")
        written += 1
    print(f"Wrote {written} GPAW runner scripts to {outdir}")


# =============================================================
#  CLI builder — single function
# =============================================================

def build_cli():
    """Build and return the argparse CLI parser."""
    parser = argparse.ArgumentParser(description='Metal-surface + molecule geometry workflow')
    subs = parser.add_subparsers(dest='command', required=True)

    # ---- generate-adatom ----
    sub = subs.add_parser('generate-adatom', help='Generate FCC(111)+adatom orientation movies')
    _add_molecule_args(sub, 'tmp/surface_movies')
    _add_surface_args(sub)
    _add_tilt_args(sub, default_tilts=(20.0, 45.0))
    _add_viz_args(sub)
    sub.add_argument('--dist', type=float, default=2.0, help='Adatom-host distance (A)')
    sub.add_argument('--rolls', type=float, nargs='*', default=[0.0, 90.0])
    sub.add_argument('--keep-epairs', action='store_true', help='Keep E dummy atoms')
    sub.add_argument('--plot-dirs', action='store_true', help='Write direction plot PNG')

    # ---- generate-edgepair ----
    sub = subs.add_parser('generate-edgepair', help='Generate FCC(111)+edgepair tilt movies')
    _add_molecule_args(sub, 'tmp/edgepair_movies')
    _add_surface_args(sub)
    _add_tilt_args(sub, default_tilts=(0.0, 15.0, 30.0))
    _add_viz_args(sub)
    sub.add_argument('--lift', type=float, default=2.0, help='Anchor height above edge (A)')
    sub.add_argument('--shift-frac', type=float, nargs=2, default=[0.5, 0.0])
    sub.add_argument('--origin-mode', default='axis_mid', choices=['axis_mid', 'anchor'])
    sub.add_argument('--target-up-mode', default='standing', choices=['standing', 'flat'])
    sub.add_argument('--anchor', default=None, help='Anchor element symbol (auto-detect if omitted)')

    # ---- generate-cluster ----
    sub = subs.add_parser('generate-cluster', help='Generate cluster+molecule orientation movies')
    sub.add_argument('--mode', required=True, choices=['apex', 'edge'],
                     help="apex = tilt+roll from apex; edge = tilts around substrate edge")
    _add_molecule_args(sub, 'tmp/cluster_movies')
    _add_viz_args(sub)
    sub.add_argument('--substrate', default=None, help='Single substrate XYZ (--mode apex)')
    sub.add_argument('--substrates', nargs='+', default=None, help='Substrate XYZ files (--mode edge)')
    _add_tilt_args(sub, default_tilts=(20.0, 45.0))
    sub.add_argument('--rolls', type=float, nargs='*', default=[0.0, 90.0], help='Roll angles; apex mode only')
    sub.add_argument('--dist', type=float, default=2.0, help='Host-molecule distance (A); apex mode only')
    sub.add_argument('--lift', type=float, default=2.0, help='Anchor height (A); edge mode only')
    sub.add_argument('--keep-epairs', action='store_true', help='Keep E dummy atoms')
    sub.add_argument('--plot-dirs', action='store_true', help='Write direction plot PNG')
    sub.add_argument('--anchor', default=None, help='Anchor element; edge mode only (auto-detect if omitted)')
    sub.add_argument('--origin-mode', default='axis_mid', choices=['axis_mid', 'anchor'], help='edge mode only')
    sub.add_argument('--target-up-mode', default='standing', choices=['standing', 'flat'], help='edge mode only')

    # ---- export-qc ----
    sub = subs.add_parser('export-qc', help='Export QC input files from movies/frames')
    sub.add_argument('--backend', required=True, choices=['psi4', 'gpaw'])
    sub.add_argument('--outdir', default=None, help='Output directory')
    # psi4
    sub.add_argument('--movie', default=None, help='Single XYZ movie file')
    sub.add_argument('--movie-dir', default=None, help='Directory with *.xyz movies (batch mode)')
    sub.add_argument('--method', default='b3lyp')
    sub.add_argument('--basis', default='cc-pvdz')
    sub.add_argument('--freeze-element', default='Ag', help='Freeze atoms of this element (None=off)')
    sub.add_argument('--mem', default='2GB')
    # gpaw
    sub.add_argument('--frame-dir', default=None, help='Directory with per-frame .xyz structures')
    sub.add_argument('--xc', default='PBE')
    sub.add_argument('--pw', type=int, default=400)
    sub.add_argument('--kpts', type=int, nargs=3, default=[4, 4, 1])
    sub.add_argument('--fix-indices', type=int, nargs='*', default=None)

    return parser


# =============================================================
#  main
# =============================================================

def main():
    parser = build_cli()
    args = parser.parse_args()
    if args.command == 'generate-adatom':
        cmd_generate_adatom(args)
    elif args.command == 'generate-edgepair':
        cmd_generate_edgepair(args)
    elif args.command == 'generate-cluster':
        cmd_generate_cluster(args)
    elif args.command == 'export-qc':
        cmd_export_qc(args)


if __name__ == '__main__':
    main()
