#!/usr/bin/env python3
"""generate_molecule_on_surface.py — place molecules on relaxed Cu/Ag/Au FCC(111) slabs (bare + adatom).

Phase 2 of the metal-tip × molecule interaction study. Reads **relaxed** slab geometries
from `jobs_coinage/results_{Metal}_{variant}_111_3x3x3/relaxed.xyz` (Phase 1 output).
Molecule is oriented so its electron lone pair faces the target metal atom at ~2.4 Å
(epair-to-metal distance). Uses existing infrastructure: AtomicSystem.add_electron_pairs(),
geom_engine._find_host_atom(), _mol_frame_from_epairs(), _transform_positions().

Binary hydrides (H2O, H2S, NH3, PH3) generated via geom_engine.make_hydride() from
experimental bond lengths and H-X-H angles. Non-hydrides (HCN, CH2O, CH2NH) loaded
from XYZ files. Cell z-height fixed to 22 Å for consistent vacuum across all systems.

Output: systems/<Metal>/<variant>_<molecule>_111_3x3x3/input/  with CONTCAR + start.xyz.

Usage:
    python generate_molecule_on_surface.py                              # all 3 metals, 2 variants, 7 molecules
    python generate_molecule_on_surface.py --metals Cu --molecules H2O  # subset
    python generate_molecule_on_surface.py --dist 2.4                   # custom epair-to-metal distance
"""
import os, sys, json, argparse
import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from py.AtomicSystem import AtomicSystem
from py import geom_engine as ge
from py import atomicUtils as au
from py.geom_engine import make_hydride, HYDRIDE_PARAMS

# Binary hydrides generated from bond length + angle (excludes CH4/SiH4 — no lone pair)
HYDRIDES = ['H2O', 'H2S', 'NH3', 'PH3']
# Non-hydride molecules still loaded from XYZ
NON_HYDRIDE_XYZ = {
    'HCN':  os.path.join(REPO, 'data', 'xyz', 'HCN.xyz'),
    'CH2O': os.path.join(REPO, 'data', 'xyz', 'CH2O.xyz'),
    'CH2NH':os.path.join(REPO, 'data', 'xyz', 'CH2NH.xyz'),
}
MOLECULES = HYDRIDES + list(NON_HYDRIDE_XYZ.keys())

# Relaxed slab geometries from previous optimization runs
RELAXED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'jobs_coinage')


def read_contcar(path):
    """Read VASP CONTCAR/POSCAR. Returns (symbols, positions, cell)."""
    with open(path) as f:
        lines = f.readlines()
    scale = float(lines[1].strip())
    cell = np.array([[float(x) for x in lines[i].split()] for i in (2, 3, 4)]) * scale
    elements = lines[5].split()
    counts = [int(x) for x in lines[6].split()]
    syms = []
    for el, n in zip(elements, counts):
        syms.extend([el] * n)
    coord_line = 7
    if lines[coord_line].strip().lower().startswith('s'):
        coord_line = 8
    coord_type = lines[coord_line].strip().lower()[0]
    n_atoms = sum(counts)
    ps = np.array([[float(x) for x in lines[coord_line + 1 + i].split()[:3]] for i in range(n_atoms)])
    if coord_type == 'd':
        ps = ps @ cell
    return syms, ps, cell


def find_top_atom(ps, exclude_idx=None):
    """Find highest-z atom index, optionally excluding a specific index."""
    z = ps[:, 2].copy()
    if exclude_idx is not None:
        z[exclude_idx] = -1e9
    return int(np.argmax(z))


def find_adatom(syms, ps):
    """Find adatom: the single highest-z atom that is the same element as the slab metal."""
    z = ps[:, 2]
    z_max = z.max()
    # Atoms at the top z level
    top_mask = np.abs(z - z_max) < 0.01
    top_indices = np.where(top_mask)[0]
    # The adatom is the one with the fewest neighbors at similar z (it sits above the surface layer)
    # For a 3x3x3 slab with 1 adatom: the topmost atom is the adatom
    # But we need to distinguish from surface layer atoms
    # Simple: the adatom is the one with highest z, and there should be only 1 at that exact height
    if len(top_indices) == 1:
        return int(top_indices[0])
    # If multiple at same z, pick the one that's clearly above the surface layer
    # Sort by z descending, look for a gap
    sorted_z = np.sort(z)[::-1]
    # Find gap between adatom and surface layer
    for i in range(len(sorted_z) - 1):
        if sorted_z[i] - sorted_z[i + 1] > 0.5:
            # Atoms above this gap are adatoms
            adatom_z = sorted_z[i]
            return int(np.where(np.abs(z - adatom_z) < 0.01)[0][0])
    # Fallback: just return the highest
    return int(np.argmax(z))


def place_molecule_on_surface(slab_syms, slab_ps, cell, mol_syms, mol_ps, target_idx, dist=2.4):
    """Place molecule on surface so its lone pair faces target atom at given distance.
    mol_syms/mol_ps: molecule symbols and positions (without electron pairs).
    Returns (combined_syms, combined_ps, mol_host_idx_in_combined)."""
    # Build AtomicSystem from molecule arrays for epair computation
    mol = AtomicSystem(enames=list(mol_syms), apos=mol_ps.copy())
    mol.neighs(bBond=True)
    i_host, host_element = ge._find_host_atom(mol)
    origin_m, fw_m, up_m, mask_keep = ge._mol_frame_from_epairs(mol, i_host, host_element=host_element)
    M_rows = au.makeRotMat(fw_m, up_m)

    # Remove electron pairs from molecule
    mol_es = [e for e, m in zip(mol.enames, mask_keep) if m]
    mol_ps = mol.apos[mask_keep]

    # Target: place molecule so host atom's epair direction points toward metal atom
    # fw_m is the direction from epair to host (E -> host), so -fw_m is host -> epair
    # We want epair to point toward the metal, so the molecule's fw should be -z (downward)
    # and the epair (at -fw direction from host) should face the metal

    # Target frame: fwd = -z (pointing down toward surface), up = any perpendicular
    target_pos = slab_ps[target_idx]
    fwd_t = np.array([0.0, 0.0, -1.0])  # pointing down toward surface
    up_t = ge._safe_up_from_ref(fwd_t, (1.0, 0.0, 0.0))
    T_rows = au.makeRotMat(fwd_t, up_t)

    # Place host atom at target_pos + dist * (-z) = target_pos + [0,0,dist]
    # But we need the epair to be at distance from metal, not the host atom
    # The epair is at origin_m + (-fw_m) * 0.5 (distance=0.5 in place_electron_pair)
    # After transformation, the epair position = T^T @ (M @ (epair_pos - origin_m)) + target_origin
    # We want epair_pos to be at target_pos + dist * (-z) = target_pos + [0,0,-dist]... no
    # We want the epair to be at distance `dist` from the metal atom, along -z
    # So target_origin (host atom position) should be at target_pos + [0, 0, dist + 0.5]
    # because epair is 0.5 Å below host in the transformed frame

    # Actually, let's think more carefully:
    # In molecule frame: host is at origin_m, epair is at origin_m + (-fw_m) * 0.5
    # After transform: host goes to target_origin, epair goes to target_origin + (-z) * 0.5
    # We want epair at target_pos + (-z) * dist = target_pos - [0,0,dist]
    # So target_origin = target_pos - [0,0,dist] + [0,0,0.5] = target_pos + [0,0, -dist + 0.5]
    # Wait, no. The transform maps epair to: T^T @ (M @ (epair_local - origin_m)) + target_origin
    # epair_local - origin_m = (-fw_m) * 0.5
    # M @ (-fw_m * 0.5) = -0.5 * (M @ fw_m) = -0.5 * [1,0,0] (since fw_m is the first row of M)
    # T^T @ (-0.5 * [1,0,0]) = -0.5 * T^T @ [1,0,0] = -0.5 * fwd_t = -0.5 * [0,0,-1] = [0,0,0.5]
    # So epair_world = target_origin + [0, 0, 0.5]
    # We want epair at target_pos + [0, 0, dist] (above the metal atom by dist)
    # So target_origin = target_pos + [0, 0, dist - 0.5]

    # Hmm, that puts the epair above the host... Let me reconsider.
    # fwd_t = [0,0,-1] means the "forward" direction is downward.
    # In the molecule frame, fw_m points from epair to host.
    # After transform, fw_m maps to fwd_t = [0,0,-1].
    # So host is "forward" (downward) relative to epair, meaning epair is "backward" (upward) from host.
    # That's wrong — we want epair pointing DOWN toward the metal.

    # We need fw to point UP (from metal toward host), so epair (at -fw from host) points DOWN toward metal.
    # So fwd_t should be [0, 0, +1] (upward), and host is above the epair.
    # Then epair is below host, pointing toward the metal.

    fwd_t = np.array([0.0, 0.0, 1.0])  # pointing up (away from surface)
    up_t = ge._safe_up_from_ref(fwd_t, (1.0, 0.0, 0.0))
    T_rows = au.makeRotMat(fwd_t, up_t)

    # Now: epair_world = target_origin + T^T @ (M @ (-fw_m * 0.5))
    # M @ fw_m = [1,0,0], so M @ (-fw_m * 0.5) = [-0.5, 0, 0]
    # T^T @ [-0.5, 0, 0] = -0.5 * T^T @ [1,0,0] = -0.5 * fwd_t = -0.5 * [0,0,1] = [0,0,-0.5]
    # epair_world = target_origin + [0, 0, -0.5]
    # We want epair at target_pos + [0, 0, dist] (above metal by dist)
    # target_origin = target_pos + [0, 0, dist + 0.5]

    target_origin = target_pos + np.array([0.0, 0.0, dist + 0.5])
    mol_ps2 = ge._transform_positions(mol_ps, origin_m, M_rows, T_rows, target_origin)

    # Combine
    combined_syms = list(slab_syms) + list(mol_es)
    combined_ps = np.vstack([slab_ps, mol_ps2])
    mol_host_idx = len(slab_syms) + list(mol_es).index(host_element)  # first occurrence in kept list

    return combined_syms, combined_ps, mol_host_idx


def write_contcar(path, syms, ps, cell):
    """Write VASP CONTCAR/POSCAR format."""
    from collections import Counter
    # Group by element preserving order
    elements = []
    counts = []
    for s in syms:
        if s not in elements:
            elements.append(s)
            counts.append(1)
        else:
            counts[elements.index(s)] += 1
    with open(path, 'w') as f:
        f.write("generated by generate_molecule_on_surface.py\n")
        f.write(f"  {1.0:.16f}\n")
        for row in cell:
            f.write(f"  {row[0]:.16f}  {row[1]:.16f}  {row[2]:.16f}\n")
        f.write("  " + "  ".join(elements) + "\n")
        f.write("  " + "  ".join(str(c) for c in counts) + "\n")
        f.write("Cartesian\n")
        for p in ps:
            f.write(f"  {p[0]:.16f}  {p[1]:.16f}  {p[2]:.16f}\n")


def write_xyz(path, syms, ps, cell=None):
    """Write extended XYZ with lattice."""
    with open(path, 'w') as f:
        f.write(f"{len(syms)}\n")
        if cell is not None:
            lvs = f"LVS=\"{cell[0,0]:.6f} {cell[0,1]:.6f} {cell[0,2]:.6f} {cell[1,0]:.6f} {cell[1,1]:.6f} {cell[1,2]:.6f} {cell[2,0]:.6f} {cell[2,1]:.6f} {cell[2,2]:.6f}\""
            f.write(f"{lvs}\n")
        else:
            f.write("\n")
        for s, p in zip(syms, ps):
            f.write(f"{s}  {p[0]:.6f}  {p[1]:.6f}  {p[2]:.6f}\n")


def read_relaxed_xyz(path):
    """Read extended XYZ (ASE format) with lattice. Returns (symbols, positions, cell)."""
    with open(path) as f:
        lines = f.readlines()
    n = int(lines[0].strip())
    comment = lines[1]
    # Parse Lattice from comment line
    import re
    lat_match = re.search(r'Lattice="([^"]+)"', comment)
    if lat_match:
        lat_vals = [float(x) for x in lat_match.group(1).split()]
        cell = np.array(lat_vals).reshape(3, 3)
    else:
        cell = np.eye(3) * 10.0
    syms = []; ps = []
    for i in range(n):
        parts = lines[2 + i].split()
        syms.append(parts[0])
        ps.append([float(parts[1]), float(parts[2]), float(parts[3])])
    return syms, np.array(ps), cell

def main():
    parser = argparse.ArgumentParser(description="Generate molecule-on-surface geometries")
    parser.add_argument('--metals', nargs='+', default=['Cu', 'Ag', 'Au'])
    parser.add_argument('--variants', nargs='+', default=['bare', 'adatom'])
    parser.add_argument('--molecules', nargs='+', default=MOLECULES)
    parser.add_argument('--dist', type=float, default=2.4, help="Epair-to-metal distance (Å)")
    parser.add_argument('--systems-dir', default=None, help="Path to systems/ output directory")
    parser.add_argument('--relaxed-dir', default=RELAXED_DIR, help='Path to relaxed slab results (jobs_coinage)')
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    systems_dir = args.systems_dir or os.path.join(base_dir, 'systems')

    for metal in args.metals:
        for variant in args.variants:
            # Read RELAXED slab geometry from previous optimization
            relaxed_xyz = os.path.join(args.relaxed_dir, f'results_{metal}_{variant}_111_3x3x3', 'relaxed.xyz')
            if not os.path.exists(relaxed_xyz):
                print(f"SKIP {metal}/{variant}: no relaxed geometry at {relaxed_xyz}")
                continue

            slab_syms, slab_ps, cell = read_relaxed_xyz(relaxed_xyz)

            # Find target atom: adatom if variant has one, else top surface atom
            if variant == 'adatom':
                target_idx = find_adatom(slab_syms, slab_ps)
            else:
                target_idx = find_top_atom(slab_ps)

            print(f"\n{metal}/{variant} (relaxed): target atom #{target_idx} at z={slab_ps[target_idx, 2]:.3f}")

            for mol_name in args.molecules:
                # Get molecule geometry: hydrides from make_hydride, others from XYZ
                if mol_name in HYDRIDE_PARAMS:
                    p = HYDRIDE_PARAMS[mol_name]
                    mol_syms, mol_ps = make_hydride(p['el'], p['nH'], p['r'], p['angle'])
                elif mol_name in NON_HYDRIDE_XYZ:
                    mol_xyz = NON_HYDRIDE_XYZ[mol_name]
                    if not os.path.exists(mol_xyz):
                        print(f"  SKIP {mol_name}: no XYZ file at {mol_xyz}")
                        continue
                    mol = AtomicSystem(fname=mol_xyz)
                    mol_syms = list(mol.enames)
                    mol_ps = mol.apos.copy()
                else:
                    print(f"  SKIP {mol_name}: unknown molecule")
                    continue

                try:
                    combined_syms, combined_ps, mol_host_idx = place_molecule_on_surface(
                        slab_syms, slab_ps, cell, mol_syms, mol_ps, target_idx, dist=args.dist)
                except Exception as e:
                    print(f"  SKIP {mol_name}: {e}")
                    continue

                # Output directory
                out_name = f"{variant}_{mol_name}"
                out_dir = os.path.join(systems_dir, metal, f"{out_name}_111_3x3x3", 'input')
                os.makedirs(out_dir, exist_ok=True)

                # Fix cell z-height to 22 Å for consistent vacuum across all molecules
                cell_fixed = cell.copy()
                cell_fixed[2, 2] = 22.0

                write_contcar(os.path.join(out_dir, 'CONTCAR'), combined_syms, combined_ps, cell_fixed)
                write_xyz(os.path.join(out_dir, 'start.xyz'), combined_syms, combined_ps, cell_fixed)

                # Verify distance
                d = np.linalg.norm(combined_ps[len(slab_syms) + mol_host_idx - len(slab_syms)] - slab_ps[target_idx])
                print(f"  {mol_name}: {len(combined_syms)} atoms, host-metal dist={d:.3f} Å → {out_dir}/CONTCAR")

    print("\nDone.")


if __name__ == '__main__':
    main()
