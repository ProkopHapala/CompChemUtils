#!/usr/bin/env python3
"""generate_metal_geometries.py — build FCC(111) slabs (bare + adatom) for all study metals.

Outputs follow the ChemBook protocol (doc/ChemBook.chat.md):
  systems/<Metal>/bare_111_3x3x3/
    meta.json          # job metadata
    input/CONTCAR      # VASP format
    input/start.xyz    # extended XYZ with lattice
  systems/<Metal>/bare_111_3x3x3.png   # preview plot (next to job dir)
  systems/<Metal>/adatom_111_3x3x3/
    ...

Colors from py/elements.py (Jmol).

Usage:
    python generate_metal_geometries.py
    python generate_metal_geometries.py --metals Cu Ag Au
    python generate_metal_geometries.py --metals Cu --size 3 3 3 --vacuum-bottom 5 --vacuum-top 10
"""

import os, sys, json, argparse
import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from py.system_specific.MetalTips import (
    build_fcc111_adatom, build_fcc111_multi_adatom, lattice_constant, supported_metals,
    bottom_layer_indices, top_layer_indices, layer_indices, slab_to_arrays
)
from py.AtomicSystem import AtomicSystem
from py.elements import getColor, ELEMENT_DICT

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe


# Metal study set (from spec §3.2)
STUDY_METALS = ['Ti', 'V', 'Cr', 'Mn', 'Fe', 'Co', 'Ni', 'Cu',
                 'Zn', 'Mo', 'W', 'Al', 'Pd', 'Ag', 'Pt', 'Au']


# =============================================================
#  Geometry generation
# =============================================================

def build_slab(metal, with_adatom, size=(3, 3, 3), vacuum_top=10.0, vacuum_bottom=5.0, adatom_height=2.0):
    """Build FCC(111) slab, optionally with adatom. Cell arranged for dipole correction below slab."""
    from ase.build import fcc111, add_adsorbate
    a = lattice_constant(metal)
    slab = fcc111(metal, size=size, a=a, vacuum=0.0, periodic=True)
    if with_adatom:
        add_adsorbate(slab, metal, height=adatom_height, position='fcc')
    ps = slab.get_positions()
    z_min, z_max = ps[:, 2].min(), ps[:, 2].max()
    slab_thickness = z_max - z_min
    cell = slab.get_cell()
    cell[2, 2] = slab_thickness + vacuum_top + vacuum_bottom
    slab.set_cell(cell)
    slab.positions[:, 2] += vacuum_bottom - z_min
    return slab


# Multi-adatom configs for coinage metals (spec: dimer, trimer, row)
# Shifts are in supercell fractional coords. For 3x3 cell, 1/3 = one primitive surface lattice vector.
MULTI_ADATOM_CONFIGS = {
    'dimer':  [(1/3, 0)],                        # 2 adatoms, nearest-neighbor along a0
    'trimer': [(1/3, 0), (0, 1/3)],              # 3 adatoms, equilateral triangle
    'row':    [(1/3, 0), (2/3, 0)],              # 3 adatoms, row along a0
}

def build_slab_multi(metal, adatom_shifts, size=(3, 3, 3), vacuum_top=10.0, vacuum_bottom=5.0, adatom_height=2.0):
    """Build FCC(111) slab with multiple adatoms. Cell arranged for dipole correction below slab."""
    slab, adatom_indices = build_fcc111_multi_adatom(
        metal, size=size, vacuum=0.0, height=adatom_height, adatom_shifts=adatom_shifts, periodic=True)
    ps = slab.get_positions()
    z_min, z_max = ps[:, 2].min(), ps[:, 2].max()
    slab_thickness = z_max - z_min
    cell = slab.get_cell()
    cell[2, 2] = slab_thickness + vacuum_top + vacuum_bottom
    slab.set_cell(cell)
    slab.positions[:, 2] += vacuum_bottom - z_min
    return slab, adatom_indices


# =============================================================
#  ChemBook meta.json writers
# =============================================================

def write_system_meta(system_dir, metal, a_fcc, rt_phase, fcc_source, variants_info):
    """Write system-level meta.json for a metal."""
    meta = {
        "schema": "chembook.system.v0.1",
        "element": metal,
        "a_fcc": a_fcc,
        "rt_phase": rt_phase,
        "fcc_source": fcc_source,
        "surface": "FCC(111)",
        "supercell": [3, 3, 3],
        "n_layers": 3,
        "n_frozen_layers": 2,
        "variants": [v['variant'] for v in variants_info],
    }
    with open(os.path.join(system_dir, 'meta.json'), 'w') as f:
        json.dump(meta, f, indent=2)


def write_system_readme(system_dir, metal, a_fcc, rt_phase, fcc_source, variants_info):
    """Write system-level README.md for a metal."""
    lines = [
        f"# {metal} — FCC(111) systematic study",
        "",
        f"- RT phase: {rt_phase}",
        f"- FCC lattice constant: {a_fcc:.3f} Å ({fcc_source})",
        f"- Surface: FCC(111), 3×3×3 supercell",
        f"- Frozen: bottom 2 layers",
        "",
        "## Variants",
        "",
        "| Variant | Atoms | Layers | Frozen | cell_z (Å) | vac_below (Å) | vac_above (Å) |",
        "|---------|-------|--------|--------|------------|---------------|----------------|",
    ]
    for v in variants_info:
        lines.append(f"| {v['variant']} | {v['n_atoms']} | {v['n_layers']} | {v['n_frozen']} | {v['cell_z']:.2f} | {v['vac_below']:.2f} | {v['vac_above']:.2f} |")
    lines.append("")
    with open(os.path.join(system_dir, 'README.md'), 'w') as f:
        f.write('\n'.join(lines))


def write_job_meta(job_dir, metal, variant, slab, frozen_indices, adatom_idx, params):
    """Write job-level meta.json for a geometry generation job."""
    es, ps, lvec, pbc = slab_to_arrays(slab)
    z = ps[:, 2]
    meta = {
        "schema": "chembook.job.v0.1",
        "title": f"{metal}_111_3x3x3_{variant}",
        "status": "geometry_generated",
        "project": "MetalTip_Molecule_interaction",
        "system": {
            "element": metal,
            "variant": variant,
            "formula": f"{metal}{len(es)}",
            "n_atoms": len(es),
            "structure_initial": "input/start.xyz",
            "pbc": list(pbc),
        },
        "method": {
            "code": "ASE",
            "level": "geometry_generation",
            "builder": "MetalTips.build_fcc111_adatom",
            "a_fcc": params['a_fcc'],
            "supercell": list(params['size']),
            "vacuum_top": params['vacuum_top'],
            "vacuum_bottom": params['vacuum_bottom'],
            "adatom_height": params['adatom_height'],
            "n_frozen_layers": params['n_frozen'],
        },
        "geometry": {
            "cell": lvec.tolist(),
            "z_min": float(z.min()),
            "z_max": float(z.max()),
            "cell_z": float(lvec[2, 2]),
            "vacuum_below": float(z.min()),
            "vacuum_above": float(lvec[2, 2] - z.max()),
            "frozen_indices": sorted(frozen_indices),
            "adatom_index": adatom_idx,
            "layer_indices": layer_indices(slab),
        },
        "files": {
            "input": ["input/CONTCAR", "input/start.xyz"],
            "figures": [f"{os.path.basename(job_dir)}.png"],
        },
        "tags": ["geometry", "fcc111", metal, variant],
    }
    with open(os.path.join(job_dir, 'meta.json'), 'w') as f:
        json.dump(meta, f, indent=2)


def write_job_readme(job_dir, metal, variant, slab, frozen_indices, adatom_idx, params):
    """Write job-level README.md."""
    es = list(slab.get_chemical_symbols())
    ps = slab.get_positions()
    z = ps[:, 2]
    cell_z = float(slab.get_cell()[2, 2])
    lines = [
        f"# {metal} — FCC(111) 3×3×3 {variant}",
        "",
        f"- Atoms: {len(es)}",
        f"- Layers: {len(layer_indices(slab))}",
        f"- Frozen: {len(frozen_indices)} atoms (bottom 2 layers)",
        f"- Adatom: {'yes (index ' + str(adatom_idx) + ')' if adatom_idx is not None else 'no'}",
        f"- cell_z: {cell_z:.2f} Å",
        f"- Vacuum below slab: {z.min():.2f} Å (dipole correction zone)",
        f"- Vacuum above slab: {cell_z - z.max():.2f} Å",
        f"- a_FCC: {params['a_fcc']:.3f} Å",
        "",
        "## Files",
        "- `input/CONTCAR` — VASP format (Jmol, VESTA)",
        "- `input/start.xyz` — extended XYZ with lattice vectors",
        f"- `{os.path.basename(job_dir)}.png` — XY top view + XZ side view (3×3 replicated)",
        "- `meta.json` — machine-readable metadata",
        "",
    ]
    with open(os.path.join(job_dir, 'README.md'), 'w') as f:
        f.write('\n'.join(lines))


# =============================================================
#  Plotting — uses Jmol colors from elements.py
# =============================================================

def elem_color_hex(sym):
    """Get Jmol color for an element as hex string (for matplotlib)."""
    if sym in ELEMENT_DICT:
        return ELEMENT_DICT[sym][8]  # index_color = 8
    return '#daa520'  # fallback goldenrod


def plot_slab(slab, figpath, frozen_indices=None, adatom_indices=None,
              replicate=(3, 3, 1), vacuum_bottom=5.0):
    """Plot XY (top view) and XZ (side view) of the slab with replication.

    Uses Jmol colors from py/elements.py. Shows: unit cell box, 3x3 replication,
    frozen atoms (red edge), adatoms (blue edge), dipole correction plane.
    """
    if adatom_indices is None: adatom_indices = []
    if isinstance(adatom_indices, int): adatom_indices = [adatom_indices]
    adatom_set = set(adatom_indices)
    es = list(slab.get_chemical_symbols())
    ps = np.array(slab.get_positions(), dtype=float)
    lvec = np.array(slab.get_cell(), dtype=float)
    cell_z = lvec[2, 2]
    frozen_set = set(frozen_indices or [])

    fig, axes = plt.subplots(1, 2, figsize=(16, 7))

    for ax_idx, (ax_pair, ax_title) in enumerate([((0, 1), 'XY top view'), ((0, 2), 'XZ side view')]):
        ax = axes[ax_idx]
        ax1, ax2 = ax_pair
        nx, ny, nz = replicate
        for ix in range(nx):
            for iy in range(ny):
                for iz in range(nz):
                    shift = np.array([ix, iy, iz]) @ lvec
                    for i, (e, p) in enumerate(zip(es, ps)):
                        rp = p + shift
                        color = elem_color_hex(e)
                        is_frozen = i in frozen_set
                        is_adatom = i in adatom_set
                        size = 200 if is_adatom else 120
                        ec = 'red' if is_frozen else ('blue' if is_adatom else 'black')
                        lw = 2.5 if (is_frozen or is_adatom) else 0.5
                        ax.scatter(rp[ax1], rp[ax2], c=color, s=size, edgecolors=ec, linewidths=lw, zorder=10)
                        if ix == 0 and iy == 0 and iz == 0:
                            label = f'{e}{i}'
                            if is_adatom: label += '(ad)'
                            ax.text(rp[ax1], rp[ax2], label, color='black', fontsize=6,
                                    ha='center', va='center', fontweight='bold',
                                    path_effects=[pe.withStroke(linewidth=1.5, foreground='white')], zorder=11)

        # Unit cell box — full 3D, 12 edges
        c = np.array([[0,0,0],[1,0,0],[1,1,0],[0,1,0],[0,0,0],
                      [0,0,1],[1,0,1],[1,1,1],[0,1,1],[0,0,1],
                      [1,0,1],[1,0,0],[1,1,0],[1,1,1],[0,1,1],[0,1,0]]) @ lvec
        ax.plot(c[:, ax1], c[:, ax2], 'b--', lw=1.5, alpha=0.5, label='Unit cell')

        # Bonds (metal-metal within 3.0 Å)
        for i in range(len(es)):
            for j in range(i + 1, len(es)):
                for six in range(-1, 2):
                    for siy in range(-1, 2):
                        shift = np.array([six, siy, 0]) @ lvec
                        d = np.linalg.norm(ps[i] - (ps[j] + shift))
                        if d < 3.0:
                            pi, pj = ps[i], ps[j] + shift
                            ax.plot([pi[ax1], pj[ax1]], [pi[ax2], pj[ax2]], 'k-', lw=0.5, alpha=0.3, zorder=1)

        # Dipole correction plane (XZ view only)
        if ax_idx == 1:
            ax.axhline(y=vacuum_bottom / 2, color='green', ls='--', lw=2, alpha=0.7,
                       label=f'Dipole correction (z={vacuum_bottom/2:.1f} Å)')
            z_min, z_max = ps[:, 2].min(), ps[:, 2].max()
            ax.axhspan(z_min, z_max, alpha=0.05, color='blue', label='Slab region')

        ax.set_aspect('equal')
        ax.set_xlabel(f"{'xyz'[ax1]} (Å)")
        ax.set_ylabel(f"{'xyz'[ax2]} (Å)")
        ax.set_title(ax_title)
        ax.legend(loc='upper right', fontsize=7)
        ax.grid(True, alpha=0.2)

    n_frozen = len(frozen_indices or [])
    fig.suptitle(f'{len(es)} atoms  |  frozen={n_frozen}  |  cell_z={cell_z:.1f} Å', fontsize=11)
    fig.tight_layout()
    fig.savefig(figpath, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"  Saved plot: {figpath}")


# =============================================================
#  Main
# =============================================================

# RT phase info for meta.json (from spec §3.2)
RT_PHASE = {
    'Ti': ('HCP', 'vol-preserving'), 'V': ('BCC', 'vol-preserving'),
    'Cr': ('BCC', 'vol-preserving'), 'Mn': ('α-Mn complex', 'γ-Mn HT FCC'),
    'Fe': ('BCC (α-Fe)', 'γ-Fe HT FCC'), 'Co': ('HCP', 'β-Co HT FCC'),
    'Ni': ('FCC', 'stable FCC'), 'Cu': ('FCC', 'stable FCC'),
    'Zn': ('HCP', 'vol-preserving'), 'Mo': ('BCC', 'vol-preserving'),
    'W': ('BCC', 'vol-preserving'), 'Al': ('FCC', 'stable FCC'),
    'Pd': ('FCC', 'stable FCC'), 'Ag': ('FCC', 'stable FCC'),
    'Pt': ('FCC', 'stable FCC'), 'Au': ('FCC', 'stable FCC'),
}

def main():
    parser = argparse.ArgumentParser(description='Generate FCC(111) metal slab geometries (ChemBook protocol)')
    parser.add_argument('--metals', nargs='*', default=STUDY_METALS, help='Metal symbols (default: all 16)')
    parser.add_argument('--size', type=int, nargs=3, default=[3, 3, 3], help='Supercell size (default: 3 3 3)')
    parser.add_argument('--vacuum-top', type=float, default=10.0, help='Vacuum above slab (Å)')
    parser.add_argument('--vacuum-bottom', type=float, default=5.0, help='Vacuum below slab for dipole correction (Å)')
    parser.add_argument('--adatom-height', type=float, default=2.0, help='Adatom height above surface (Å)')
    parser.add_argument('--n-frozen', type=int, default=2, help='Number of bottom layers to freeze')
    parser.add_argument('--no-plots', action='store_true', help='Skip plot generation')
    args = parser.parse_args()

    size = tuple(args.size)
    metals = args.metals
    project_dir = os.path.dirname(os.path.abspath(__file__))
    systems_dir = os.path.join(project_dir, 'systems')

    print("=" * 70)
    print(f"Generating FCC(111) metal slab geometries (ChemBook protocol)")
    print(f"  Metals: {metals}")
    print(f"  Size: {size}  |  vacuum_top={args.vacuum_top} Å  |  vacuum_bottom={args.vacuum_bottom} Å")
    print(f"  Frozen: bottom {args.n_frozen} layers  |  adatom_height={args.adatom_height} Å")
    print(f"  Output: {systems_dir}")
    print("=" * 70)

    summary = []

    for metal in metals:
        a = lattice_constant(metal)
        rt_phase, fcc_source = RT_PHASE.get(metal, ('?', '?'))
        system_dir = os.path.join(systems_dir, metal)
        os.makedirs(system_dir, exist_ok=True)

        variants_info = []
        for with_adatom in [False, True]:
            variant = 'adatom' if with_adatom else 'bare'
            variant_tag = f'{variant}_111_{size[0]}x{size[1]}x{size[2]}'
            job_dir = os.path.join(system_dir, variant_tag)
            input_dir = os.path.join(job_dir, 'input')
            os.makedirs(input_dir, exist_ok=True)

            print(f"\n--- {metal}/{variant_tag} ---")
            print(f"  a_FCC = {a:.3f} Å")

            # Build
            slab = build_slab(metal, with_adatom=with_adatom, size=size,
                              vacuum_top=args.vacuum_top, vacuum_bottom=args.vacuum_bottom,
                              adatom_height=args.adatom_height)

            n_atoms = len(slab)
            ps = slab.get_positions()
            z = ps[:, 2]
            z_min, z_max = float(z.min()), float(z.max())
            cell_z = float(slab.get_cell()[2, 2])

            layers = layer_indices(slab)
            n_layers = len(layers)
            frozen = bottom_layer_indices(slab, args.n_frozen) if n_layers > args.n_frozen else []

            adatom_idx = int(np.argmax(z)) if with_adatom else None
            if with_adatom:
                print(f"  Adatom: index {adatom_idx}, z={z[adatom_idx]:.3f} Å")

            print(f"  Atoms: {n_atoms}  |  Layers: {n_layers}  |  Frozen: {len(frozen)}")
            print(f"  z: {z_min:.2f}–{z_max:.2f} Å  |  cell_z: {cell_z:.2f} Å  |  vac_below: {z_min:.2f}  vac_above: {cell_z-z_max:.2f}")

            # Save CONTCAR (VASP format — Jmol reads cell from this)
            contcar_path = os.path.join(input_dir, 'CONTCAR')
            slab.write(contcar_path, format='vasp')
            print(f"  Saved: {contcar_path}")

            # Save extended XYZ
            es, ps_arr, lvec, pbc = slab_to_arrays(slab)
            sys_obj = AtomicSystem(apos=ps_arr, enames=es, lvec=lvec)
            xyz_path = os.path.join(input_dir, 'start.xyz')
            sys_obj.saveXYZ(xyz_path)
            print(f"  Saved: {xyz_path}")

            # Plot — saved next to the job dir as <variant_tag>.png
            if not args.no_plots:
                fig_path = os.path.join(system_dir, f'{variant_tag}.png')
                plot_slab(slab, fig_path, frozen_indices=frozen, adatom_indices=adatom_idx,
                          replicate=(3, 3, 1), vacuum_bottom=args.vacuum_bottom)

            # Write meta.json + README.md
            params = {'a_fcc': a, 'size': size, 'vacuum_top': args.vacuum_top,
                      'vacuum_bottom': args.vacuum_bottom, 'adatom_height': args.adatom_height,
                      'n_frozen': args.n_frozen}
            write_job_meta(job_dir, metal, variant, slab, frozen, adatom_idx, params)
            write_job_readme(job_dir, metal, variant, slab, frozen, adatom_idx, params)

            vac_below = z_min
            vac_above = cell_z - z_max
            variants_info.append({'variant': variant, 'n_atoms': n_atoms, 'n_layers': n_layers,
                                  'n_frozen': len(frozen), 'cell_z': cell_z, 'vac_below': vac_below, 'vac_above': vac_above})
            summary.append({'metal': metal, 'a': a, 'variant': variant, 'n_atoms': n_atoms,
                            'n_layers': n_layers, 'n_frozen': len(frozen), 'cell_z': cell_z,
                            'vac_below': vac_below, 'vac_above': vac_above})

        # Multi-adatom variants (dimer, trimer, row) — only for coinage metals
        if metal in ('Cu', 'Ag', 'Au'):
            for config_name, shifts in MULTI_ADATOM_CONFIGS.items():
                variant_tag = f'{config_name}_111_{size[0]}x{size[1]}x{size[2]}'
                job_dir = os.path.join(system_dir, variant_tag)
                input_dir = os.path.join(job_dir, 'input')
                os.makedirs(input_dir, exist_ok=True)

                print(f"\n--- {metal}/{variant_tag} ---")
                slab, adatom_indices = build_slab_multi(metal, shifts, size=size,
                    vacuum_top=args.vacuum_top, vacuum_bottom=args.vacuum_bottom, adatom_height=args.adatom_height)
                n_atoms = len(slab)
                ps = slab.get_positions()
                z = ps[:, 2]
                z_min, z_max = float(z.min()), float(z.max())
                cell_z = float(slab.get_cell()[2, 2])
                layers = layer_indices(slab)
                n_layers = len(layers)
                frozen = bottom_layer_indices(slab, args.n_frozen) if n_layers > args.n_frozen else []
                print(f"  Adatoms: {len(adatom_indices)} at indices {adatom_indices}, z={[f'{z[i]:.2f}' for i in adatom_indices]}")
                print(f"  Atoms: {n_atoms}  |  Layers: {n_layers}  |  Frozen: {len(frozen)}")
                print(f"  z: {z_min:.2f}–{z_max:.2f} Å  |  cell_z: {cell_z:.2f} Å  |  vac_below: {z_min:.2f}  vac_above: {cell_z-z_max:.2f}")

                # Save CONTCAR + XYZ
                contcar_path = os.path.join(input_dir, 'CONTCAR')
                slab.write(contcar_path, format='vasp')
                print(f"  Saved: {contcar_path}")
                es, ps_arr, lvec, pbc = slab_to_arrays(slab)
                sys_obj = AtomicSystem(apos=ps_arr, enames=es, lvec=lvec)
                xyz_path = os.path.join(input_dir, 'start.xyz')
                sys_obj.saveXYZ(xyz_path)
                print(f"  Saved: {xyz_path}")

                # Plot — saved next to the job dir as <variant_tag>.png
                if not args.no_plots:
                    fig_path = os.path.join(system_dir, f'{variant_tag}.png')
                    plot_slab(slab, fig_path, frozen_indices=frozen, adatom_indices=adatom_indices,
                              replicate=(3, 3, 1), vacuum_bottom=args.vacuum_bottom)

                # Write meta.json + README.md
                params = {'a_fcc': a, 'size': size, 'vacuum_top': args.vacuum_top,
                          'vacuum_bottom': args.vacuum_bottom, 'adatom_height': args.adatom_height,
                          'n_frozen': args.n_frozen, 'adatom_shifts': shifts}
                write_job_meta(job_dir, metal, config_name, slab, frozen, adatom_indices, params)
                write_job_readme(job_dir, metal, config_name, slab, frozen, adatom_indices, params)

                vac_below = z_min
                vac_above = cell_z - z_max
                variants_info.append({'variant': config_name, 'n_atoms': n_atoms, 'n_layers': n_layers,
                                      'n_frozen': len(frozen), 'cell_z': cell_z, 'vac_below': vac_below, 'vac_above': vac_above})
                summary.append({'metal': metal, 'a': a, 'variant': config_name, 'n_atoms': n_atoms,
                                'n_layers': n_layers, 'n_frozen': len(frozen), 'cell_z': cell_z,
                                'vac_below': vac_below, 'vac_above': vac_above})

        # Write system-level meta.json + README.md
        write_system_meta(system_dir, metal, a, rt_phase, fcc_source, variants_info)
        write_system_readme(system_dir, metal, a, rt_phase, fcc_source, variants_info)

    # Write project-level README.md with summary table
    project_readme = os.path.join(project_dir, 'README.md')
    lines = [
        "# MetalTip × Molecule Interaction Study",
        "",
        "Systematic study of coordination bond strength between small molecules and",
        "FCC(111) metal surfaces (bare vs. adatom vs. multi-adatom). See",
        "[spec](../../doc/MetalTip_Molecule_Interaction_Study_Spec.md) for full design.",
        "",
        "## Phase 1: Metal geometry generation",
        "",
        f"Generated {len(summary)} geometries: 16 metals × {{bare, adatom}} + Cu/Ag/Au × {{dimer, trimer, row}}.",
        "",
        "### Directory structure (ChemBook protocol)",
        "```",
        "systems/<Metal>/",
        "  meta.json                    # system metadata (element, a_fcc, rt_phase)",
        "  README.md                    # system summary table",
        "  bare_111_3x3x3.png           # preview plot (next to job dir)",
        "  bare_111_3x3x3/",
        "    meta.json                  # job metadata (cell, frozen indices, adatom index, ...)",
        "    README.md                  # job summary",
        "    input/CONTCAR              # VASP format (Jmol, VESTA)",
        "    input/start.xyz            # extended XYZ with lattice",
        "  adatom_111_3x3x3.png",
        "  adatom_111_3x3x3/",
        "    ...",
        "  dimer_111_3x3x3.png          # Cu, Ag, Au only",
        "  dimer_111_3x3x3/",
        "    ...",
        "  trimer_111_3x3x3.png",
        "  trimer_111_3x3x3/",
        "    ...",
        "  row_111_3x3x3.png",
        "  row_111_3x3x3/",
        "    ...",
        "```",
        "",
        "### Summary table",
        "",
        "| Metal | a_FCC (Å) | Variant | Atoms | Layers | Frozen | cell_z (Å) | vac_below | vac_above |",
        "|-------|-----------|---------|-------|--------|--------|------------|-----------|-----------|",
    ]
    for s in summary:
        lines.append(f"| {s['metal']} | {s['a']:.3f} | {s['variant']} | {s['n_atoms']} | {s['n_layers']} | {s['n_frozen']} | {s['cell_z']:.2f} | {s['vac_below']:.2f} | {s['vac_above']:.2f} |")
    lines += [
        "",
        "### Key parameters",
        "- Supercell: 3×3×3 FCC(111)",
        "- Vacuum: 5 Å below slab (dipole correction), 10 Å above (molecule/scan room)",
        "- Frozen: bottom 2 layers (18 atoms)",
        "- Adatom: fcc hollow site, 2.0 Å above top layer",
        "- Multi-adatom (Cu, Ag, Au only): dimer (2, NN), trimer (3, equilateral triangle), row (3, line) — all at a/√2 spacing",
        "- Colors: Jmol (from `py/elements.py`)",
        "- Plots: `<variant>.png` next to each job dir (not inside)",
        "",
        "### Usage",
        "```bash",
        "python generate_metal_geometries.py                    # all 16 metals",
        "python generate_metal_geometries.py --metals Cu Ag Au  # subset",
        "```",
        "",
    ]
    with open(project_readme, 'w') as f:
        f.write('\n'.join(lines))
    print(f"\n  Saved project README: {project_readme}")

    # Print summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"{'Metal':>5} {'a(Å)':>7} {'Variant':>8} {'Atoms':>6} {'Layers':>7} {'Frozen':>7} {'cell_z':>8} {'vac_below':>10} {'vac_above':>10}")
    print("-" * 70)
    for s in summary:
        print(f"{s['metal']:>5} {s['a']:>7.3f} {s['variant']:>8} {s['n_atoms']:>6} {s['n_layers']:>7} {s['n_frozen']:>7} {s['cell_z']:>8.2f} {s['vac_below']:>10.2f} {s['vac_above']:>10.2f}")
    print(f"\nTotal: {len(summary)} geometries in {systems_dir}")


if __name__ == '__main__':
    main()
