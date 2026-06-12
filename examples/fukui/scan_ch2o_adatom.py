#!/usr/bin/env python3
"""
Molecule-to-Surface Scan Generator

This script orients a molecule and generates an XYZ movie scanning its distance
above various Ag surface models (single adatom, clusters, or periodic surfaces).

Features:
- Molecule orientation via electron pairs (E-pairs) or PCA
- Multiple Ag surface models: single adatom, Ag4 tetrahedron, Ag7 bipyramid, Ag(111) slab
- Configurable adatom arrangements: symmetric (opposite) or asymmetric (neighboring)
- Consistent z-coordinate convention: adatoms at z=0, molecule scanned above
- Robust error handling for molecules without E-pair support

Surface Models:
1. Single adatom: One Ag atom at origin
2. Ag4 tetrahedron: 3 base atoms + 1 apex (surface model)
3. Ag7 bipyramid: 5 base atoms + 2 adatoms on fcc(111) geometry
   - symmetric: Two up-facing hollows sharing central atom (opposite corners)
   - asymmetric: Close-packed strip with neighboring hollows (olympic-style)
4. Ag(111) surface: Periodic slab with adatom(s) at fcc hollow sites
   - single: 1 adatom
   - symmetric: 2 adatoms at opposite hollows (max distance)
   - asymmetric: 2 adatoms at neighboring hollows (min distance)

Orientation Methods:
- E-pair mode (default): Places host atom at origin, aligns E-pair bond with -z
  - Use for molecules with lone pairs (H2O, CH2O, NH3, etc.)
  - Specify host element with --host (default: O)
- PCA mode: Principal component analysis for planar molecules
  - Longest axis -> x, shortest -> z, oxygens point down
  - Automatically used if E-pair addition fails
  - Can be forced with --pca flag

Distance Reference:
- E-pair mode: Distance measured from host atom (e.g., O) to Ag apex
- PCA mode: Distance measured from bottom-most atom to Ag apex

Output:
- XYZ movie file with multiple frames at different distances
- Scan range: 2.0-3.0 Å (step 0.1), then 3.2-6.0 Å (step 0.2)
- Ag atoms listed first, followed by molecule atoms
- Frame comment indicates distance and reference point

Usage Examples:

# Single adatom with E-pair orientation
python scan_ch2o_adatom.py --mol data/xyz/CH2O.xyz --host O --remove-epairs

# Ag4 tetrahedral cluster
python scan_ch2o_adatom.py --mol data/xyz/H2O.xyz --cluster --remove-epairs

# Ag7 bipyramid (symmetric)
python scan_ch2o_adatom.py --mol data/xyz/H2O.xyz --bipyramid symmetric --remove-epairs

# Ag7 bipyramid (asymmetric)
python scan_ch2o_adatom.py --mol data/xyz/H2O.xyz --bipyramid asymmetric --remove-epairs

# Planar molecule with PCA orientation
python scan_ch2o_adatom.py --mol data/xyz/maleic_anhydride.xyz --pca --bipyramid symmetric --remove-epairs

# Ag(111) surface with single adatom
python scan_ch2o_adatom.py --mol data/xyz/CH2O.xyz --surface single --remove-epairs

# Ag(111) surface with two neighboring adatoms (asymmetric)
python scan_ch2o_adatom.py --mol data/xyz/maleic_anhydride.xyz --pca --surface asymmetric --remove-epairs

# Ag(111) surface with two opposite adatoms (symmetric)
python scan_ch2o_adatom.py --mol data/xyz/H2O.xyz --surface symmetric --remove-epairs

# Custom surface size (3x3x2)
python scan_ch2o_adatom.py --mol ... --surface symmetric --surface-size 3 3 2

# Custom Ag-Ag bond length
python scan_ch2o_adatom.py --mol ... --bipyramid symmetric --bond 2.95

Requirements:
- pyBall (from this repo)
- numpy
- ASE (only for --surface mode): pip install ase
"""

import os
import sys
import argparse
import numpy as np

# Add repo root to path for pyBall imports
repo_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, repo_dir)

from pyBall import atomicUtils as au
from pyBall.AtomicSystem import AtomicSystem


def set_pose(apos, origin_atom, fwd_atom, up_atom, target_origin=(0,0,0), reverse_fwd=False):
    """Rigid-body transform: place origin_atom at target_origin,
    align origin_atom->fwd_atom along +z (or reversed), and keep
    origin_atom->up_atom in the +y half-plane.
    """
    p0 = apos[origin_atom]
    if reverse_fwd:
        fw = apos[origin_atom] - apos[fwd_atom]
    else:
        fw = apos[fwd_atom] - apos[origin_atom]
    up = apos[up_atom] - apos[origin_atom]
    au.orient_vs(p0, fw, up, apos)
    apos[:, :] += np.array(target_origin)
    return apos


def make_ag_tetrahedron(L=2.89):
    """Build a regular tetrahedral Ag4 cluster (3 base + 1 apex).
    
    Apex is placed at origin, base atoms form an equilateral triangle
    in the z = -h plane.
    
    Parameters
    ----------
    L : float
        Edge length (Å). Default 2.89 Å (Ag fcc nearest-neighbour distance).
    
    Returns
    -------
    apos : ndarray (4,3)
        Positions of 4 Ag atoms.
    """
    r = L / np.sqrt(3.0)          # centroid-to-vertex in base triangle
    h = L * np.sqrt(2.0 / 3.0)    # tetrahedron height
    
    apex = np.array([0.0, 0.0, 0.0])
    base = np.array([
        [0.0,           r,                   -h],
        [ r * np.sqrt(3) * 0.5, -r * 0.5,    -h],
        [-r * np.sqrt(3) * 0.5, -r * 0.5,    -h],
    ])
    
    return np.vstack([apex, base])


def make_ag_bipyramid(config='symmetric', L=2.89):
    """Build a 7-atom Ag cluster: 5 base atoms + 2 adatoms on fcc(111) geometry.

    Config 'symmetric':
        Two up-facing fcc hollows sharing one central base atom (shared vertex).
        Base atoms form a "diamond" of 5 atoms. Both adatoms are mirror-symmetric
        around the central atom.

    Config 'asymmetric':
        5 base atoms in a close-packed strip (3 bottom + 2 top offset).
        Adatoms sit above the two outer up-facing triangles; the middle
        down-facing triangle between them is left empty.

    Parameters
    ----------
    config : str
        'symmetric' or 'asymmetric'
    L : float
        Ag-Ag nearest-neighbour distance (Å). Default 2.89 Å.

    Returns
    -------
    apos : ndarray (7,3)
    """
    h = L * np.sqrt(2.0 / 3.0)   # adatom height above base plane

    # 6 hexagon vertices at angles 0, 60, 120, 180, 240, 300 degrees
    # (pointy-top orientation: vertex at top = 90 deg)
    # Use flat-top: vertex[0] at angle=0 (right), going CCW
    hex_v = np.array([[L * np.cos(np.radians(30 + 60*k)),
                       L * np.sin(np.radians(30 + 60*k))] for k in range(6)])
    # hex_v[0]=top-right, [1]=top, [2]=top-left, [3]=bot-left, [4]=bot, [5]=bot-right
    # Center C at (0,0)
    C = np.zeros(2)

    def p3xy(xy): return np.array([xy[0], xy[1], 0.0])
    def adatom_above(p0, p1, p2):
        c = (p0 + p1 + p2) / 3.0
        return np.array([c[0], c[1], h])

    if config == 'symmetric':
        # Two triangles on OPPOSITE sides of the hexagon (left / right),
        # sharing center C. Adatoms end up along x-axis.
        #   triangle A (left):   C, v[2], v[3]   (top-left + bot-left)
        #   triangle B (right):  C, v[0], v[5]   (top-right + bot-right)
        # 5 base atoms: C, v[0], v[2], v[3], v[5]
        b = [p3xy(C), p3xy(hex_v[0]), p3xy(hex_v[2]), p3xy(hex_v[3]), p3xy(hex_v[5])]
        ad0 = adatom_above(C, hex_v[2], hex_v[3])
        ad1 = adatom_above(C, hex_v[0], hex_v[5])
    elif config == 'asymmetric':
        # Close-packed strip: 3 bottom + 2 top (like olympic rings / lower half of hexagon)
        #   bottom row: (0,0), (1,0), (2,0)
        #   top row:    (0,1), (1,1)   [offset by hex lattice a2]
        # Up-facing hollows: left=(0,0),(1,0),(0,1)  right=(1,0),(2,0),(1,1)
        # Down-facing hollow in middle: (1,0),(0,1),(1,1) -> empty
        a1 = np.array([L, 0.0])
        a2 = np.array([L * 0.5, L * np.sqrt(3.0) / 2.0])
        def lp(i, j): return i * a1 + j * a2   # 2D lattice position
        b = [p3xy(lp(0,0)), p3xy(lp(1,0)), p3xy(lp(2,0)), p3xy(lp(0,1)), p3xy(lp(1,1))]
        ad0 = adatom_above(lp(0,0), lp(1,0), lp(0,1))
        ad1 = adatom_above(lp(1,0), lp(2,0), lp(1,1))
        # Center at xy centroid of base atoms
        base_xy = np.mean([bb[:2] for bb in b], axis=0)
        b = [np.array([bb[0]-base_xy[0], bb[1]-base_xy[1], 0.0]) for bb in b]
        ad0[:2] -= base_xy
        ad1[:2] -= base_xy
    else:
        raise ValueError(f"Unknown config '{config}': use 'symmetric' or 'asymmetric'")

    apos = np.array(b + [ad0, ad1])
    # Shift so adatoms (top) are at z=0, base below at z=-h
    apos[:, 2] -= h
    return apos


def orient_pca(apos, enames, oxy_down=True):
    """Orient molecule using principal component analysis.

    Aligns longest principal axis with x, shortest with z.
    If oxy_down=True, flips so average z of oxygen atoms is negative.
    Returns apos centered at origin.
    """
    # Center at origin
    apos[:, :] -= apos.mean(axis=0)
    # PCA via SVD of covariance matrix
    _, _, vt = np.linalg.svd(apos)
    rot = vt.T  # columns are principal axes
    # Ensure right-handed: if det(rot) < 0, flip last axis
    if np.linalg.det(rot) < 0:
        rot[:, 2] *= -1
    # Rotate: longest axis -> x, shortest -> z
    # vt is ordered by descending singular values, so:
    #   vt[0] = longest axis, vt[1] = middle, vt[2] = shortest
    # We want: x=longest, y=middle, z=shortest
    # rot currently maps original coords to PCA coords (longest=y? no...)
    # Actually: apos @ rot gives coords in principal axis basis
    # Let's construct explicit mapping: new_x = longest, new_y = middle, new_z = shortest
    # rot = [axis1, axis2, axis3] where axis1=longest direction in original space
    # So: new_coord = np.dot(apos, rot)
    # We want new_coord[0]=longest, new_coord[1]=middle, new_coord[2]=shortest
    # That IS what np.dot(apos, rot) gives, since rot[:,0]=axis1 (longest)
    # Wait, np.linalg.svd returns V^T where rows are principal components.
    # So vt[0] is the direction of the first principal component (longest).
    # rot = vt.T, so rot[:,0] = vt[0] = longest axis direction.
    # np.dot(apos, rot) gives coords where x=longest, y=middle, z=shortest. Good.
    apos[:, :] = np.dot(apos, rot)
    # For planar molecules (all z ~ 0), rotate 90° around x to stand molecule up,
    # then ensure oxygens point toward -z
    if oxy_down:
        oxy_indices = [i for i, e in enumerate(enames) if e == 'O']
        max_z = np.max(np.abs(apos[:, 2]))
        if oxy_indices and max_z < 0.3:
            # Molecule is planar in xy — rotate 90° around x: (x,y,z)->(x,-z,y)
            apos[:, :] = apos[:, [0, 2, 1]]
            apos[:, 2] *= -1
            # Now oxygens should be at negative z; if not, flip 180° around x
            if apos[oxy_indices, 2].mean() > 0:
                apos[:, 1:] *= -1
        elif oxy_indices:
            # Non-planar: just flip if oxygens are at +z
            if apos[oxy_indices, 2].mean() > 0:
                apos[:, 1:] *= -1
    return apos


def make_ag111_surface(config='single', size=(2, 2, 2), a=4.086, height=2.0):
    """Build Ag(111) surface slab with 1 or 2 adatoms at fcc hollow sites.

    Parameters
    ----------
    config : str
        'single', 'symmetric', or 'asymmetric'
    size : tuple of int
        Surface supercell (nx, ny, nz). Default (2, 2, 2).
    a : float
        Ag lattice constant (Å). Default 4.086 Å.
    height : float
        Adatom height above top surface layer (Å). Default 2.0 Å.

    Returns
    -------
    apos : ndarray (N,3)
    enames : list of str
    """
    try:
        from ase.build import fcc111, add_adsorbate
    except ImportError:
        raise ImportError("ASE is required for --surface. Install: pip install ase")

    slab = fcc111('Ag', size=size, a=a, vacuum=10.0)

    # Get primitive cell vectors for hollow-site arithmetic
    a1_full = np.array(slab.cell[0][:2])
    a2_full = np.array(slab.cell[1][:2])
    prim1 = a1_full / size[0]
    prim2 = a2_full / size[1]

    # Place first adatom at fcc hollow; record its xy position
    add_adsorbate(slab, 'Ag', height=height, position='fcc')
    pos_all = slab.get_positions()
    site0 = pos_all[-1][:2].copy()

    # Build list of all fcc hollow sites in the supercell
    sites_xy = [site0]
    for ix in range(size[0]):
        for iy in range(size[1]):
            if ix == 0 and iy == 0:
                continue
            s = site0 + ix * prim1 + iy * prim2
            # Wrap into cell using fractional coordinates
            cell_mat = np.array([a1_full, a2_full]).T
            frac = np.linalg.solve(cell_mat, s)
            frac = frac % 1.0
            s = cell_mat @ frac
            sites_xy.append(s)

    if config == 'single':
        adatom_xy = [sites_xy[0]]
    elif config == 'asymmetric':
        # Nearest-neighbor hollow sites (shortest adatom-adatom distance)
        # Pick the two sites with smallest distance from site0
        dists = [np.linalg.norm(s - site0) for s in sites_xy[1:]]
        idx = np.argmin(dists) + 1
        adatom_xy = [sites_xy[0], sites_xy[idx]]
    elif config == 'symmetric':
        # Most distant pair from the set (opposite corners)
        max_d = -1
        pair = (0, 1)
        for i in range(len(sites_xy)):
            for j in range(i + 1, len(sites_xy)):
                d = np.linalg.norm(sites_xy[i] - sites_xy[j])
                if d > max_d:
                    max_d = d
                    pair = (i, j)
        adatom_xy = [sites_xy[pair[0]], sites_xy[pair[1]]]
    else:
        raise ValueError(f"Unknown surface config '{config}': use 'single', 'symmetric', or 'asymmetric'")

    # Remove the first adatom that add_adsorbate placed, then add all adatoms manually
    symbols = list(slab.get_chemical_symbols())
    positions = list(pos_all)
    # Pop the last atom (the first adatom)
    symbols.pop()
    positions.pop()

    # Get top-layer z to place adatoms at correct height
    top_z = max(p[2] for p in positions)
    for xy in adatom_xy:
        positions.append(np.array([xy[0], xy[1], top_z + height]))
        symbols.append('Ag')

    apos = np.array(positions)
    # Shift so adatoms are at z=0 (highest z in the system)
    z_ad = max(p[2] for p in apos)
    apos[:, 2] -= z_ad
    return apos, symbols


def main():
    parser = argparse.ArgumentParser(description='Orient molecule with e-pairs and scan above Ag surface model')
    parser.add_argument('--mol', default='data/xyz/CH2O.xyz', help='Molecule XYZ file (default: data/xyz/CH2O.xyz)')
    parser.add_argument('--host', default='O', help='Host atom element that gets e-pairs (default: O)')
    parser.add_argument('--pca', action='store_true', help='Use PCA orientation instead of e-pair orientation')
    parser.add_argument('--cluster', action='store_true', help='Use Ag4 tetrahedral cluster instead of single adatom')
    parser.add_argument('--bipyramid', choices=['symmetric', 'asymmetric'], default=None, help='Use 7-atom Ag bipyramid cluster')
    parser.add_argument('--surface', choices=['single', 'symmetric', 'asymmetric'], default=None, help='Use Ag(111) surface slab with adatom(s)')
    parser.add_argument('--surface-size', type=int, nargs=3, default=[2, 2, 2], metavar=('NX','NY','NZ'), help='Surface supercell size (default: 2 2 2)')
    parser.add_argument('--bond', type=float, default=2.89, help='Ag-Ag bond length (default: 2.89 Å)')
    parser.add_argument('--remove-epairs', action='store_true', help='Remove dummy E-pair atoms from output')
    args = parser.parse_args()

    # --- Load molecule and add electron pairs ---
    xyz_path = os.path.join(repo_dir, args.mol)
    mol_name = os.path.splitext(os.path.basename(args.mol))[0]
    mol = AtomicSystem(fname=xyz_path)
    mol.neighs(bBond=True)
    n_orig = len(mol.apos)
    try:
        mol.add_electron_pairs()
    except Exception as e:
        print(f"Warning: add_electron_pairs() failed ({e}), stripping partial e-pairs")
        # Strip any partially-added E atoms
        mask = [e != 'E' for e in mol.enames]
        mol.enames = [e for e, m in zip(mol.enames, mask) if m]
        mol.apos = mol.apos[mask]
        if mol.qs is not None:
            mol.qs = mol.qs[mask]
        # Reset neighbor list to original state
        mol.ngs = mol.ngs[:n_orig]
        for i in range(n_orig):
            mol.ngs[i] = [j for j in mol.ngs[i] if j < n_orig]

    has_epairs = any(e == 'E' for e in mol.enames)
    if has_epairs:
        print(f"{mol_name} with electron pairs:")
    else:
        print(f"{mol_name}:")
    for i, (ename, pos) in enumerate(zip(mol.enames, mol.apos)):
        print(f"  [{i}] {ename:2s}  {pos[0]:10.5f} {pos[1]:10.5f} {pos[2]:10.5f}")

    # --- Identify host atom and neighbors ---
    if has_epairs:
        host_candidates = [i for i, e in enumerate(mol.enames) if e == args.host]
        if not host_candidates:
            raise ValueError(f"No atom with element '{args.host}' found in molecule")
        i_host = None
        for i in host_candidates:
            if any(mol.enames[j] == 'E' for j in mol.ngs[i] if j != -1):
                i_host = i
                break
        if i_host is None:
            i_host = host_candidates[0]

        e_neighbors = [j for j in mol.ngs[i_host] if j != -1 and mol.enames[j] == 'E']
        if len(e_neighbors) < 1:
            raise ValueError(f"Host atom {i_host} has no E-pair neighbors")
        iE0 = e_neighbors[0]

        if len(e_neighbors) >= 2:
            i_up = e_neighbors[1]
        else:
            for j in mol.ngs[i_host]:
                if j != -1 and mol.enames[j] != 'E':
                    i_up = j
                    break
        if i_up is None:
            raise ValueError(f"Host atom {i_host} has no up-vector candidate")

        print(f"\nHost atom: [{i_host}] {mol.enames[i_host]}")
        print(f"E-pair atom: [{iE0}] {mol.enames[iE0]}")
        print(f"Up atom: [{i_up}] {mol.enames[i_up]}")

    # --- Rigid-body orientation ---
    if args.pca or not has_epairs:
        # PCA-based: longest axis -> x, shortest -> z, oxygens down
        orient_pca(mol.apos, mol.enames, oxy_down=True)
        # Shift so bottom-most atom touches z=0
        z_bottom = mol.apos[:, 2].min()
        mol.apos[:, 2] -= z_bottom
        origin_label = 'bottom'
    else:
        # E-pair based: host at origin, E->host along +z
        set_pose(mol.apos, origin_atom=i_host, fwd_atom=iE0, up_atom=i_up, reverse_fwd=True)
        origin_label = args.host

    print("\nAfter orientation:")
    for i, (ename, pos) in enumerate(zip(mol.enames, mol.apos)):
        print(f"  [{i}] {ename:2s}  {pos[0]:10.5f} {pos[1]:10.5f} {pos[2]:10.5f}")

    # --- Optionally remove E-pair atoms from output ---
    mask = np.array([e != 'E' for e in mol.enames]) if args.remove_epairs else np.ones(len(mol.enames), dtype=bool)
    out_enames = [e for e, m in zip(mol.enames, mask) if m]
    out_pos = mol.apos[mask]
    out_qs = mol.qs[mask] if mol.qs is not None else np.zeros(len(out_enames))
    n_mol = len(out_enames)

    # --- Build Ag surface model ---
    if args.surface:
        ag_pos, ag_es = make_ag111_surface(config=args.surface, size=tuple(args.surface_size))
        n_ag = len(ag_pos)
        ag_qs = np.zeros(n_ag)
        size_str = f'{args.surface_size[0]}x{args.surface_size[1]}x{args.surface_size[2]}'
        tag = f'{mol_name}_Ag111_{size_str}_{args.surface}_scan.xyz'
    elif args.bipyramid:
        ag_pos = make_ag_bipyramid(config=args.bipyramid, L=args.bond)
        n_ag = len(ag_pos)
        ag_es = ['Ag'] * n_ag
        ag_qs = np.zeros(n_ag)
        tag = f'{mol_name}_Ag7_{args.bipyramid}_scan.xyz'
    elif args.cluster:
        ag_pos = make_ag_tetrahedron(L=args.bond)
        n_ag = len(ag_pos)
        ag_es = ['Ag'] * n_ag
        ag_qs = np.zeros(n_ag)
        tag = f'{mol_name}_Ag4_scan.xyz'
    else:
        ag_pos = np.array([[0.0, 0.0, 0.0]])
        n_ag = 1
        ag_es = ['Ag']
        ag_qs = np.array([0.0])
        tag = f'{mol_name}_adatom_scan.xyz'

    # --- Build distance scan list ---
    distances = []
    d = 2.0
    while d <= 3.0 + 1e-6:
        distances.append(round(d, 6))
        d += 0.1
    d = 3.2
    while d <= 6.0 + 1e-6:
        distances.append(round(d, 6))
        d += 0.2

    print(f"\nScanning {len(distances)} distances: {distances[0]} ... {distances[-1]} Å")

    # --- Generate XYZ movie ---
    outdir = os.path.join(os.path.dirname(__file__), 'structures')
    os.makedirs(outdir, exist_ok=True)
    movie_file = os.path.join(outdir, tag)

    # Ag first, then molecule
    es = ag_es + out_enames
    qs = np.append(ag_qs, out_qs)

    with open(movie_file, 'w') as fout:
        for i, d in enumerate(distances):
            # Host atom at (0,0,d), cluster apex at origin
            pos = np.zeros((n_ag + n_mol, 3))
            pos[:n_ag, :] = ag_pos
            pos[n_ag:, :] = out_pos + np.array([0.0, 0.0, d])

            comment = f"Distance {origin_label}-Ag_apex = {d:.2f} A"
            au.writeToXYZ(fout, es, pos, qs=qs, comment=comment, bHeader=True)

    print(f"\nMovie saved: {movie_file}")
    print(f"  Frames: {len(distances)}")


if __name__ == '__main__':
    main()
