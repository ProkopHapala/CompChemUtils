#!/usr/bin/python

import os
import json
import copy
from dataclasses import dataclass, field
from typing import List, Optional
import numpy as np

from . import atomicUtils as au
from .AtomicSystem import AtomicSystem


# ============================================================= #
#  Geometric Constraints — program-agnostic specification        #
#  Each backend translates these to its own constraint syntax.   #
# ============================================================= #

@dataclass
class GeomConstraint:
    """Program-agnostic geometric constraint.

    type:   'freeze_atoms'  — fix Cartesian positions of listed atoms
            'fix_distance'  — fix bond length between atoms[0] and atoms[1]
            'fix_angle'     — fix angle atoms[0]-atoms[1]-atoms[2]
            'fix_dihedral'  — fix dihedral atoms[0]-atoms[1]-atoms[2]-atoms[3]
    atoms:  list of 0-based atom indices
    value:  target value (Å for distance, degrees for angle/dihedral); None for freeze
    """
    type: str
    atoms: List[int]
    value: Optional[float] = None

def freeze_atoms(indices: List[int]) -> GeomConstraint:
    """Fix Cartesian positions of specified atoms."""
    return GeomConstraint(type='freeze_atoms', atoms=list(indices), value=None)

def fix_distance(i: int, j: int, d_angstrom: float) -> GeomConstraint:
    """Fix bond length between atoms i and j (Å)."""
    return GeomConstraint(type='fix_distance', atoms=[i, j], value=float(d_angstrom))

def fix_angle(i: int, j: int, k: int, deg: float) -> GeomConstraint:
    """Fix bond angle i-j-k (degrees)."""
    return GeomConstraint(type='fix_angle', atoms=[i, j, k], value=float(deg))

def fix_dihedral(i: int, j: int, k: int, l: int, deg: float) -> GeomConstraint:
    """Fix dihedral angle i-j-k-l (degrees)."""
    return GeomConstraint(type='fix_dihedral', atoms=[i, j, k, l], value=float(deg))


def _normalize(v):
    v = np.array(v, dtype=np.float64)
    n = np.linalg.norm(v)
    if n < 1e-12:
        raise ValueError(f"normalize(): |v| too small {v}")
    return v / n


def _resolve_point(apos, spec, _0=0):
    """Resolve a point specification into a 3D point.

    Supported:
      - int: atom index
      - list/tuple/np.ndarray of ints: average of indices
      - dict: {"type": "atom"|"average"|"cog"|"vector", ...}
    """
    if isinstance(spec, (int, np.integer)):
        return np.array(apos[int(spec) - _0], dtype=np.float64)
    if isinstance(spec, np.ndarray) and spec.dtype.kind == 'f' and spec.shape == (3,):
        return spec.astype(np.float64)   # explicit 3D coordinate
    if isinstance(spec, (list, tuple)) and len(spec) == 3 and isinstance(spec[0], float):
        return np.array(spec, dtype=np.float64)  # explicit 3D coordinate
    if isinstance(spec, (list, tuple, np.ndarray)) and (len(spec) > 0) and isinstance(spec[0] if not isinstance(spec, np.ndarray) else spec.flat[0], (int, np.integer)):
        ii = np.array(spec, dtype=int) - _0
        return np.array(apos[ii].mean(axis=0), dtype=np.float64)
    if isinstance(spec, dict):
        t = spec.get('type', None)
        if t == 'atom':
            return np.array(apos[int(spec['index']) - _0], dtype=np.float64)
        if t == 'average':
            ii = np.array(spec['indices'], dtype=int) - _0
            return np.array(apos[ii].mean(axis=0), dtype=np.float64)
        if t == 'cog':
            subset = spec.get('subset', None)
            if subset is None or subset == 'all':
                ps = apos
            else:
                ii = np.array(subset, dtype=int) - _0
                ps = apos[ii]
            return np.array(ps.mean(axis=0), dtype=np.float64)
        if t == 'vector':
            return np.array(spec['vector'], dtype=np.float64)
    raise ValueError(f"Unknown PointSpec {spec}")


def _resolve_vector(apos, spec, _0=0):
    """Resolve a vector specification into a 3D (normalized) vector.

    Supported:
      - list/tuple/np.ndarray len=3: explicit vector
      - dict:
          - {"type":"vector","vector":[...]} 
          - {"type":"bond","src":<PointSpec>,"dst":<PointSpec>}
          - {"type":"pca","subset":"all"|[...],"axis":"longest"|"middle"|"shortest"}
    """
    if isinstance(spec, (list, tuple, np.ndarray)) and (len(spec) == 3) and (not isinstance(spec[0], (int, np.integer))):
        return _normalize(spec)
    if isinstance(spec, dict):
        t = spec.get('type', None)
        if t == 'vector':
            return _normalize(spec['vector'])
        if t == 'bond':
            p0 = _resolve_point(apos, spec['src'], _0=_0)
            p1 = _resolve_point(apos, spec['dst'], _0=_0)
            return _normalize(p1 - p0)
        if t == 'pca':
            subset = spec.get('subset', 'all')
            if subset == 'all' or subset is None:
                ps = np.array(apos, dtype=np.float64)
            else:
                ii = np.array(subset, dtype=int) - _0
                ps = np.array(apos[ii], dtype=np.float64)
            vs = au.rotMatPCA(ps)  # rows ordered by eigenvalue desc => [longest,middle,shortest]
            ax = spec.get('axis', 'longest')
            if ax == 'longest':
                v = vs[0]
            elif ax == 'middle':
                v = vs[1]
            elif ax == 'shortest':
                v = vs[2]
            else:
                raise ValueError(f"Unknown PCA axis '{ax}'")
            if spec.get('sign', '+') == '-':
                v = -v
            return _normalize(v)
    raise ValueError(f"Unknown VectorSpec {spec}")


def _project_to_perp(v, n):
    n = _normalize(n)
    v = np.array(v, dtype=np.float64)
    return v - n * np.dot(v, n)


def _safe_up_from_ref(fwd, ref_up=(1.0, 0.0, 0.0)):
    fwd = _normalize(fwd)
    ref_up = np.array(ref_up, dtype=np.float64)
    u = _project_to_perp(ref_up, fwd)
    nu = np.linalg.norm(u)
    if nu < 1e-8:
        ref_up2 = np.array((0.0, 1.0, 0.0), dtype=np.float64)
        u = _project_to_perp(ref_up2, fwd)
        nu = np.linalg.norm(u)
    if nu < 1e-8:
        raise ValueError(f"Cannot construct up vector for fwd={fwd}; ref_up colinear")
    return u / nu


def _roll_up(fwd, up0, roll_deg):
    fwd = _normalize(fwd)
    up0 = _safe_up_from_ref(fwd, up0)
    if abs(roll_deg) < 1e-12:
        return up0
    R = au.rotation_matrix(fwd, np.deg2rad(roll_deg))
    return _normalize(R @ up0)


def _transform_positions(apos, origin, M_rows, T_rows, target_origin):
    """Apply p' = T^T @ (M @ (p-origin)) + target_origin.

    M_rows, T_rows are row-basis matrices as returned by au.makeRotMat.
    """
    origin = np.array(origin, dtype=np.float64)
    target_origin = np.array(target_origin, dtype=np.float64)
    M = np.array(M_rows, dtype=np.float64)
    T = np.array(T_rows, dtype=np.float64)
    ps = np.array(apos, dtype=np.float64) - origin[None, :]
    q = (M @ ps.T).T
    ps2 = (T.T @ q.T).T + target_origin[None, :]
    return ps2


def _oxygen_down_score(mol_es, mol_ps2):
    iiO = [i for i, e in enumerate(mol_es) if e == 'O']
    if not iiO:
        return 0.0
    iiX = [i for i, e in enumerate(mol_es) if e != 'O']
    if not iiX:
        return 0.0
    zO = float(np.mean(np.array(mol_ps2, dtype=float)[iiO, 2]))
    zX = float(np.mean(np.array(mol_ps2, dtype=float)[iiX, 2]))
    return zO - zX


def auto_edge_placement(
    sub_es,
    sub_ps,
    mol_es,
    mol_ps,
    edge_p0,
    edge_p1,
    i_anchor,
    i_axis0,
    i_axis1,
    tilts_deg,
    lift0=2.0,
    origin_mode='axis_mid',
    target_up_mode='standing',
    clash_factor=0.7,
    lift_step=0.25,
    lift_max=8.0,
):
    sub_es = list(sub_es)
    mol_es = list(mol_es)
    sub_ps = np.array(sub_ps, dtype=np.float64)
    mol_ps = np.array(mol_ps, dtype=np.float64)
    p0 = np.array(edge_p0, dtype=np.float64)
    p1 = np.array(edge_p1, dtype=np.float64)

    best = None
    tried = 0

    for swap_edge in (False, True):
        pp0, pp1 = (p1, p0) if swap_edge else (p0, p1)
        for up_sign in (1.0, -1.0):
            tried += 1
            lift = float(lift0)
            while lift <= float(lift_max) + 1e-12:
                ok = True
                nshort = 0
                worst_ratio = 1e9
                for tilt in tilts_deg:
                    mol_ps2 = place_molecule_on_edge(
                        mol_es=mol_es,
                        mol_ps=mol_ps,
                        edge_p0=pp0,
                        edge_p1=pp1,
                        i_anchor=int(i_anchor),
                        i_axis0=int(i_axis0),
                        i_axis1=int(i_axis1),
                        lift=float(lift),
                        tilt_deg=float(tilt),
                        origin_mode=origin_mode,
                        target_up_mode=target_up_mode,
                        target_up_sign=float(up_sign),
                    )
                    es = sub_es + mol_es
                    ps = np.vstack([sub_ps, mol_ps2])
                    shorts = au.findShortContactsNP(ps, es, factor=float(clash_factor))
                    if shorts:
                        ok = False
                        nshort += len(shorts)
                        rbest = min(float(r) / float(rmin) for (_, _, r, rmin) in shorts)
                        worst_ratio = min(worst_ratio, rbest)
                        break
                if ok:
                    mol_ps2_0 = place_molecule_on_edge(
                        mol_es=mol_es,
                        mol_ps=mol_ps,
                        edge_p0=pp0,
                        edge_p1=pp1,
                        i_anchor=int(i_anchor),
                        i_axis0=int(i_axis0),
                        i_axis1=int(i_axis1),
                        lift=float(lift),
                        tilt_deg=0.0,
                        origin_mode=origin_mode,
                        target_up_mode=target_up_mode,
                        target_up_sign=float(up_sign),
                    )
                    oz = _oxygen_down_score(mol_es, mol_ps2_0)
                    cand = {
                        'swap_edge': bool(swap_edge),
                        'target_up_sign': float(up_sign),
                        'lift': float(lift),
                        'oxygen_dz': float(oz),
                        'nshort': 0,
                        'worst_ratio': 1.0,
                    }
                    if best is None:
                        best = cand
                    else:
                        key_best = (best['oxygen_dz'] > 0.0, best['lift'])
                        key_cand = (cand['oxygen_dz'] > 0.0, cand['lift'])
                        if key_cand < key_best:
                            best = cand
                    break
                lift += float(lift_step)

            if best is None:
                # keep track of closest (still clashing) candidate at lift0
                lift = float(lift0)
                ok = True
                nshort = 0
                worst_ratio = 1e9
                for tilt in tilts_deg:
                    mol_ps2 = place_molecule_on_edge(
                        mol_es=mol_es,
                        mol_ps=mol_ps,
                        edge_p0=pp0,
                        edge_p1=pp1,
                        i_anchor=int(i_anchor),
                        i_axis0=int(i_axis0),
                        i_axis1=int(i_axis1),
                        lift=float(lift),
                        tilt_deg=float(tilt),
                        origin_mode=origin_mode,
                        target_up_mode=target_up_mode,
                        target_up_sign=float(up_sign),
                    )
                    es = sub_es + mol_es
                    ps = np.vstack([sub_ps, mol_ps2])
                    shorts = au.findShortContactsNP(ps, es, factor=float(clash_factor))
                    if shorts:
                        ok = False
                        nshort += len(shorts)
                        rbest = min(float(r) / float(rmin) for (_, _, r, rmin) in shorts)
                        worst_ratio = min(worst_ratio, rbest)
                mol_ps2_0 = place_molecule_on_edge(
                    mol_es=mol_es,
                    mol_ps=mol_ps,
                    edge_p0=pp0,
                    edge_p1=pp1,
                    i_anchor=int(i_anchor),
                    i_axis0=int(i_axis0),
                    i_axis1=int(i_axis1),
                    lift=float(lift),
                    tilt_deg=0.0,
                    origin_mode=origin_mode,
                    target_up_mode=target_up_mode,
                    target_up_sign=float(up_sign),
                )
                oz = _oxygen_down_score(mol_es, mol_ps2_0)
                cand = {
                    'swap_edge': bool(swap_edge),
                    'target_up_sign': float(up_sign),
                    'lift': float(lift),
                    'oxygen_dz': float(oz),
                    'nshort': int(nshort),
                    'worst_ratio': float(worst_ratio),
                }
                if best is None:
                    best = cand
                else:
                    key_best = (best['nshort'], -best['worst_ratio'], best['oxygen_dz'] > 0.0)
                    key_cand = (cand['nshort'], -cand['worst_ratio'], cand['oxygen_dz'] > 0.0)
                    if key_cand < key_best:
                        best = cand

    if best is None:
        raise ValueError('auto_edge_placement(): no candidates evaluated')
    best['tried'] = int(tried)
    return best


def _find_host_atom(mol, preferred=('O', 'N')):
    for e in preferred:
        for i, ee in enumerate(mol.enames):
            if ee == e:
                return i, e
    raise ValueError(f"No host atom found (tried {preferred}); enames={set(mol.enames)}")


def _mol_frame_from_epairs(mol, i_host, host_element=None):
    """Return (origin, fw, up, mask_keep) for molecule orientation.

    fw is defined such that host->E points opposite to fw (so E points toward -fw).
    """
    if mol.ngs is None:
        mol.neighs(bBond=True)
    mol.add_electron_pairs()

    # gather electron-pair neighbors
    ng = mol.ngs[i_host]
    e_neighs = [j for j in ng.keys() if mol.enames[j] == 'E']

    if e_neighs:
        iE0 = e_neighs[0]
        fw = mol.apos[i_host] - mol.apos[iE0]  # (E -> host)
        if len(e_neighs) >= 2:
            iU = e_neighs[1]
            up = mol.apos[iU] - mol.apos[i_host]
        else:
            # use a real neighbor (any non-E)
            cand = [j for j in ng.keys() if mol.enames[j] != 'E']
            if not cand:
                raise ValueError(f"Host atom {i_host} has E but no non-E neighbor for up")
            iU = cand[0]
            up = mol.apos[iU] - mol.apos[i_host]
    else:
        # fallback: lone pair direction opposite to nearest neighbor bond
        cand = [j for j in ng.keys() if mol.enames[j] != 'E']
        if not cand:
            raise ValueError(f"Host atom {i_host} has no neighbors; cannot define lone-pair direction")
        # prefer heavy atom neighbor if present
        heavy = [j for j in cand if mol.enames[j] != 'H']
        j0 = heavy[0] if heavy else cand[0]
        fw = mol.apos[i_host] - mol.apos[j0]
        # up: try another neighbor if possible
        j1 = None
        for j in cand:
            if j != j0:
                j1 = j
                break
        if j1 is None:
            up = np.array((0.0, 1.0, 0.0))
        else:
            up = mol.apos[j1] - mol.apos[i_host]

    fw = _normalize(fw)
    up = _project_to_perp(up, fw)
    if np.linalg.norm(up) < 1e-8:
        up = _safe_up_from_ref(fw, (1.0, 0.0, 0.0))
    else:
        up = _normalize(up)

    # Keep mask (remove E by default in downstream)
    mask_keep = np.array([e != 'E' for e in mol.enames], dtype=bool)
    return mol.apos[i_host].copy(), fw, up, mask_keep


def _pick_farthest_pair(ii, ps):
    ii = [int(i) for i in ii]
    if len(ii) < 2:
        raise ValueError(f"_pick_farthest_pair(): need >=2 indices, got {ii}")
    ps = np.array(ps, dtype=np.float64)
    best = (ii[0], ii[1])
    d2best = -1.0
    for a in range(len(ii)):
        ia = ii[a]
        pa = ps[ia]
        for b in range(a + 1, len(ii)):
            ib = ii[b]
            dp = ps[ib] - pa
            d2 = float(np.dot(dp, dp))
            if d2 > d2best:
                d2best = d2
                best = (ia, ib)
    return best


def _find_bridge_atom(mol, element='O', neigh_element='C', min_neigh=2):
    if mol.ngs is None:
        mol.neighs(bBond=True)
    out = []
    for i, e in enumerate(mol.enames):
        if e != element:
            continue
        ng = mol.ngs[i]
        n = 0
        for j in ng.keys():
            if mol.enames[j] == neigh_element:
                n += 1
        if n >= int(min_neigh):
            out.append(int(i))
    return out


def _mol_frame_from_anchor_and_axis(mol_ps, i_anchor, i0_axis, i1_axis, fallback_pca_subset=None):
    ps = np.array(mol_ps, dtype=np.float64)
    pA = ps[int(i_anchor)]
    fw = ps[int(i1_axis)] - ps[int(i0_axis)]
    fw = _normalize(fw)
    v0 = ps[int(i0_axis)] - pA
    v1 = ps[int(i1_axis)] - pA
    up = np.cross(v0, v1)
    if np.linalg.norm(up) < 1e-10:
        if fallback_pca_subset is None:
            subset = ps
        else:
            subset = ps[np.array(fallback_pca_subset, dtype=int)]
        vs = au.rotMatPCA(subset)
        up = vs[2]
    up = _project_to_perp(up, fw)
    if np.linalg.norm(up) < 1e-10:
        up = _safe_up_from_ref(fw, (0.0, 0.0, 1.0))
    else:
        up = _normalize(up)
    return pA.copy(), fw, up


def _find_top_pair_by_z(es, ps, element='Ag', ztol=1e-3):
    ps = np.array(ps, dtype=np.float64)
    ii = [int(i) for i, e in enumerate(es) if e == element]
    if not ii:
        raise ValueError(f"_find_top_pair_by_z(): no atoms of element '{element}'")
    z = ps[ii, 2]
    zmax = float(np.max(z))
    top = [ii[k] for k, zz in enumerate(z) if abs(float(zz) - zmax) < float(ztol)]
    if len(top) >= 2:
        return _pick_farthest_pair(top, ps)
    order = sorted(ii, key=lambda i: float(ps[i, 2]), reverse=True)
    if len(order) < 2:
        raise ValueError(f"_find_top_pair_by_z(): need >=2 '{element}' atoms")
    return int(order[0]), int(order[1])


def place_molecule_on_edge(
    mol_es,
    mol_ps,
    edge_p0,
    edge_p1,
    i_anchor,
    i_axis0,
    i_axis1,
    lift=2.0,
    tilt_deg=0.0,
    z_axis=(0.0, 0.0, 1.0),
    origin_mode='axis_mid',
    target_up_mode='standing',
    target_up_sign=1.0,
):
    ps = np.array(mol_ps, dtype=np.float64)
    p0 = np.array(edge_p0, dtype=np.float64)
    p1 = np.array(edge_p1, dtype=np.float64)
    edge_axis = _normalize(p1 - p0)
    edge_mid = 0.5 * (p0 + p1)

    origin_m, fw_m, up_m = _mol_frame_from_anchor_and_axis(ps, i_anchor, i_axis0, i_axis1)
    M_rows = au.makeRotMat(fw_m, up_m)

    z_axis = _normalize(z_axis)
    if target_up_mode == 'flat':
        up_t = _project_to_perp(z_axis, edge_axis)
        if np.linalg.norm(up_t) < 1e-10:
            up_t = _safe_up_from_ref(edge_axis, (1.0, 0.0, 0.0))
        else:
            up_t = _normalize(up_t)
    elif target_up_mode == 'standing':
        up_t = np.cross(edge_axis, z_axis)
        if np.linalg.norm(up_t) < 1e-10:
            up_t = _safe_up_from_ref(edge_axis, (1.0, 0.0, 0.0))
        else:
            up_t = _normalize(up_t)
    else:
        raise ValueError(f"Unknown target_up_mode='{target_up_mode}'")
    up_t = up_t * float(target_up_sign)
    T_rows = au.makeRotMat(edge_axis, up_t)

    if origin_mode == 'anchor':
        origin_ref = origin_m
    elif origin_mode == 'axis_mid':
        origin_ref = 0.5 * (ps[int(i_axis0)] + ps[int(i_axis1)])
    else:
        raise ValueError(f"Unknown origin_mode='{origin_mode}'")

    target_ref = edge_mid + z_axis * float(lift)
    ps2 = _transform_positions(ps, origin_ref, M_rows, T_rows, target_ref)

    if abs(float(tilt_deg)) > 1e-12:
        R = au.rotation_matrix(edge_axis, np.deg2rad(float(tilt_deg)))
        ps2 = edge_mid[None, :] + (R @ (ps2 - edge_mid[None, :]).T).T

    return ps2


def _infer_edge_anchors(mol, anchor_element=None):
    if mol.ngs is None:
        mol.neighs(bBond=True)

    if anchor_element == 'N':
        iiN = [i for i, e in enumerate(mol.enames) if e == 'N']
        if not iiN:
            raise ValueError("No N found for anchor")
        i_anchor = int(iiN[0])
    else:
        bridges = _find_bridge_atom(mol, element='O', neigh_element='C', min_neigh=2)
        if not bridges:
            raise ValueError("No bridge O found (O with >=2 C neighbors)")
        i_anchor = int(bridges[0])

    iiO = [int(i) for i, e in enumerate(mol.enames) if e == 'O' and int(i) != i_anchor]
    if len(iiO) < 2:
        raise ValueError(f"Need >=2 peripheral O atoms (excluding anchor), got {iiO}")
    i0_axis, i1_axis = _pick_farthest_pair(iiO, mol.apos)
    return i_anchor, (int(i0_axis), int(i1_axis))


def generate_edge_attach_movie(
    mol_xyz,
    substrate_xyz,
    out_xyz,
    tilts_deg=(0.0, 15.0, 30.0),
    lift=2.0,
    substrate_edge_pair=None,
    anchor_element=None,
    anchor_index=None,
    axis_pair=None,
    origin_mode='axis_mid',
    target_up_mode='standing',
    clash_factor=0.7,
    clash_max_report=12,
    auto_fix=True,
    lift_step=0.25,
    lift_max=8.0,
):
    sub = AtomicSystem(fname=substrate_xyz)
    mol = AtomicSystem(fname=mol_xyz)
    mol.neighs(bBond=True)

    sub_es = list(sub.enames)
    sub_ps = np.array(sub.apos, dtype=np.float64)
    mol_es = list(mol.enames)
    mol_ps = np.array(mol.apos, dtype=np.float64)

    if substrate_edge_pair is None:
        iE0, iE1 = _find_top_pair_by_z(sub_es, sub_ps, element='Ag')
    else:
        iE0, iE1 = int(substrate_edge_pair[0]), int(substrate_edge_pair[1])

    if anchor_index is None or axis_pair is None:
        i_anchor2, (i0_axis, i1_axis) = _infer_edge_anchors(mol, anchor_element=anchor_element)
        if anchor_index is None:
            anchor_index = i_anchor2
        if axis_pair is None:
            axis_pair = (i0_axis, i1_axis)

    p0 = sub_ps[iE0]
    p1 = sub_ps[iE1]
    edge_mid = 0.5 * (p0 + p1)
    edge_axis = _normalize(p1 - p0)

    z_axis = np.array((0.0, 0.0, 1.0))
    if abs(np.dot(z_axis, edge_axis)) > 0.95:
        z_axis = np.array((0.0, 1.0, 0.0))

    swap_edge = False
    up_sign = 1.0
    if auto_fix:
        best = auto_edge_placement(
            sub_es=sub_es,
            sub_ps=sub_ps,
            mol_es=mol_es,
            mol_ps=mol_ps,
            edge_p0=p0,
            edge_p1=p1,
            i_anchor=int(anchor_index),
            i_axis0=int(axis_pair[0]),
            i_axis1=int(axis_pair[1]),
            tilts_deg=tuple(tilts_deg),
            lift0=float(lift),
            origin_mode=origin_mode,
            target_up_mode=target_up_mode,
            clash_factor=float(clash_factor),
            lift_step=float(lift_step),
            lift_max=float(lift_max),
        )
        swap_edge = bool(best['swap_edge'])
        up_sign = float(best['target_up_sign'])
        lift = float(best['lift'])
        if best.get('nshort', 0) > 0:
            print(f"WARNING auto_edge_placement unresolved nshort={best['nshort']} worst_ratio={best.get('worst_ratio', -1.0):.3f} out={out_xyz}")
        if best.get('oxygen_dz', 0.0) > 0.0:
            print(f"WARNING oxygen_up oxygen_dz={best['oxygen_dz']:.3f} out={out_xyz}")

    if swap_edge:
        p0, p1 = p1, p0

    with open(out_xyz, 'w') as fout:
        for it, tilt in enumerate(tilts_deg):
            mol_ps2 = place_molecule_on_edge(
                mol_es=mol_es,
                mol_ps=mol_ps,
                edge_p0=p0,
                edge_p1=p1,
                i_anchor=int(anchor_index),
                i_axis0=int(axis_pair[0]),
                i_axis1=int(axis_pair[1]),
                lift=float(lift),
                tilt_deg=float(tilt),
                z_axis=z_axis,
                origin_mode=origin_mode,
                target_up_mode=target_up_mode,
                target_up_sign=up_sign,
            )

            es = sub_es + mol_es
            ps = np.vstack([sub_ps, mol_ps2])
            shorts = au.findShortContactsNP(ps, es, factor=float(clash_factor))
            if shorts:
                shorts.sort(key=lambda x: x[2])
                print(f"WARNING short_contacts n={len(shorts)} dof={it} tilt={float(tilt):.2f} out={out_xyz}")
                for k, (i, j, r, rmin) in enumerate(shorts[:int(clash_max_report)]):
                    ei, ej = es[int(i)], es[int(j)]
                    print(f"  {k:02d} {int(i):4d}({ei}) {int(j):4d}({ej}) r={float(r):.3f}  rmin={float(rmin):.3f}")
            comment = f"dof={it} tilt={float(tilt):.2f} lift={float(lift):.3f} edge=({iE0},{iE1}) anchor={int(anchor_index)} axis=({int(axis_pair[0])},{int(axis_pair[1])})"
            au.writeToXYZ(fout, es, ps, qs=None, comment=comment, bHeader=True)

    return {'out_xyz': out_xyz, 'n_frames': len(tuple(tilts_deg)), 'edge_pair': (int(iE0), int(iE1)), 'anchor_index': int(anchor_index), 'axis_pair': (int(axis_pair[0]), int(axis_pair[1])), 'edge_mid': edge_mid}


def ag4_directions(ag, i_apex=0, base=(1, 2, 3), tilt_degs=(20.0, 45.0)):
    """Return list of direction dicts (name,fwd,ref_lat,theta_deg,azim_kind).

    - straight up: +z
    - tilted: theta from +z, azimuth toward a base vertex (corner) or an edge midpoint (face)
    """
    pA = np.array(ag.apos[i_apex], dtype=np.float64)
    bps = np.array([ag.apos[i] for i in base], dtype=np.float64)

    # corner direction in xy plane = projection of apex->base[0]
    v_corner = bps[0] - pA
    v_corner[2] = 0.0
    u_corner = _normalize(v_corner)

    # face direction in xy plane = projection of apex->midpoint(base[1],base[2])
    v_face = 0.5 * (bps[1] + bps[2]) - pA
    v_face[2] = 0.0
    u_face = _normalize(v_face)

    z = np.array((0.0, 0.0, 1.0))

    out = [
        {
            'name': 'up',
            'theta_deg': 0.0,
            'azim_kind': 'none',
            'fwd': z.copy(),
            'ref_lat': u_corner.copy(),
        }
    ]

    for th in tilt_degs:
        sth = np.sin(np.deg2rad(th))
        cth = np.cos(np.deg2rad(th))
        for kind, u in (('corner', u_corner), ('face', u_face)):
            fwd = _normalize(u * sth + z * cth)
            out.append({'name': f"tilt{int(round(th))}_{kind}", 'theta_deg': float(th), 'azim_kind': kind, 'fwd': fwd, 'ref_lat': u.copy()})

    return out


def plot_directions_3d(dirs, fname, scale=2.5):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401

    fig = plt.figure(figsize=(6, 6))
    ax = fig.add_subplot(111, projection='3d')

    ax.scatter([0], [0], [0], c='k', s=40)

    for i, d in enumerate(dirs):
        v = d['fwd']
        ax.quiver(0, 0, 0, v[0], v[1], v[2], length=scale, normalize=True)
        p = v * (scale * 1.05)
        ax.text(p[0], p[1], p[2], f"{i}:{d['name']}")

    ax.set_xlabel('x')
    ax.set_ylabel('y')
    ax.set_zlabel('z')
    ax.set_title('Ag4 scan directions')

    lim = scale * 1.2
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.set_zlim(0, lim)

    plt.tight_layout()
    fig.savefig(fname, dpi=150)
    plt.close(fig)


def generate_ag4_attach_movie(
    mol_xyz,
    out_xyz,
    ag4_xyz=None,
    dist=2.0,
    tilt_degs=(20.0, 45.0),
    roll_degs=(0.0, 90.0),
    remove_epairs=True,
    plot_dirs_png=None,
):
    """Generate XYZ movie: Ag4 + molecule in multiple orientations at fixed pivot-to-pivot distance."""

    if ag4_xyz is None:
        ag4_xyz = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'xyz', 'Ag4.xyz')

    ag = AtomicSystem(fname=ag4_xyz)
    mol = AtomicSystem(fname=mol_xyz)

    # build bonding for epairs
    mol.neighs(bBond=True)

    i_host, host_element = _find_host_atom(mol)

    origin_m, fw_m, up_m, mask_keep = _mol_frame_from_epairs(mol, i_host, host_element=host_element)
    M_rows = au.makeRotMat(fw_m, up_m)

    dirs = ag4_directions(ag, i_apex=0, base=(1, 2, 3), tilt_degs=tilt_degs)
    if plot_dirs_png is not None:
        plot_directions_3d(dirs, plot_dirs_png)

    if remove_epairs:
        mol_es = [e for e, m in zip(mol.enames, mask_keep) if m]
        mol_qs = mol.qs[mask_keep] if mol.qs is not None else None
        mol_ps = mol.apos[mask_keep]
    else:
        mol_es = list(mol.enames)
        mol_qs = mol.qs
        mol_ps = mol.apos

    ag_es = list(ag.enames) if hasattr(ag.enames, '__len__') else ['Ag'] * len(ag.apos)
    ag_qs = ag.qs

    n_ag = len(ag_es)
    n_m = len(mol_es)

    with open(out_xyz, 'w') as fout:
        for idir, ddir in enumerate(dirs):
            fwd_t = ddir['fwd']
            for iroll, rdeg in enumerate(roll_degs):
                idof = idir * len(roll_degs) + iroll

                up0_t = _safe_up_from_ref(fwd_t, ddir['ref_lat'])
                up_t = _roll_up(fwd_t, up0_t, rdeg)

                T_rows = au.makeRotMat(fwd_t, up_t)

                target_origin = ag.apos[0] + fwd_t * dist
                mol_ps2 = _transform_positions(mol_ps, origin_m, M_rows, T_rows, target_origin)

                es = ag_es + mol_es
                ps = np.vstack([ag.apos, mol_ps2])

                if ag_qs is None and mol_qs is None:
                    qs = None
                else:
                    q_ag = ag_qs if ag_qs is not None else np.zeros(n_ag)
                    q_m = mol_qs if mol_qs is not None else np.zeros(n_m)
                    qs = np.concatenate([q_ag, q_m])

                comment = f"dof={idof} idir={idir} iroll={iroll} dir={ddir['name']} theta={ddir['theta_deg']:.1f} roll={rdeg:.1f} host={host_element}[{i_host}] dist={dist:.3f}"
                au.writeToXYZ(fout, es, ps, qs=qs, comment=comment, bHeader=True)

    return {
        'out_xyz': out_xyz,
        'n_frames': len(dirs) * len(roll_degs),
        'host_index': int(i_host),
        'host_element': host_element,
        'dirs': dirs,
    }


def run_from_json(config_path):
    with open(config_path, 'r') as f:
        cfg = json.load(f)

    mol_xyz = cfg['molecule']['file']
    out_xyz = cfg['output']['xyz_movie']
    ag4_xyz = cfg.get('substrate', {}).get('file', None)

    dist = float(cfg.get('placement', {}).get('dist', 2.0))

    tilt_degs = tuple(cfg.get('scan', {}).get('tilt_degs', [20.0, 45.0]))
    roll_degs = tuple(cfg.get('scan', {}).get('roll_degs', [0.0, 90.0]))

    remove_epairs = bool(cfg.get('molecule', {}).get('epairs', {}).get('remove_after', True))

    plot_dirs_png = cfg.get('output', {}).get('plot_dirs_png', None)

    return generate_ag4_attach_movie(
        mol_xyz=mol_xyz,
        out_xyz=out_xyz,
        ag4_xyz=ag4_xyz,
        dist=dist,
        tilt_degs=tilt_degs,
        roll_degs=roll_degs,
        remove_epairs=remove_epairs,
        plot_dirs_png=plot_dirs_png,
    )


# ============================================================= #
#  Geometry sanity validation — crash loudly on garbage         #
# ============================================================= #

def validate_geometry(geom, ref_geom=None,
                      max_bond_length=5.0, min_bond_length=0.3,
                      max_atom_displacement=None, min_atom_distance=0.05,
                      check_nan=True, check_bonds=True, check_overlap=True):
    """Validate geometry for physical reasonableness.

    Raises ValueError with a clear message on any check failure.
    Returns True if all checks pass.

    Parameters
    ----------
    geom                  : AtomicSystem or (apos, es) tuple
    ref_geom              : reference geometry for displacement check
    max_bond_length       : longest allowed bond (Å); None = skip
    min_bond_length       : shortest allowed bond (Å); None = skip
    max_atom_displacement : max allowed displacement vs ref_geom (Å); None = skip
    min_atom_distance     : minimum distance between any two atoms (Å);
                            values < 0.05 Å indicate overlap/crash
    check_nan             : fail if any coordinate is NaN or Inf
    check_bonds           : run bond-length sanity using covalent radii
    check_overlap         : run pairwise distance check for near-coincident atoms
    """
    import numpy as np
    from . import elements as el

    apos = geom.apos if hasattr(geom, 'apos') else geom[0]
    es   = geom.enames if hasattr(geom, 'enames') else geom[1]
    apos = np.asarray(apos, dtype=np.float64)
    if apos.ndim != 2 or apos.shape[1] != 3:
        raise ValueError(f"validate_geometry: apos must be (N,3), got {apos.shape}")
    n = len(apos)
    if len(es) != n:
        raise ValueError(f"validate_geometry: len(es)={len(es)} != len(apos)={n}")

    # --- 1. NaN / Inf ---
    if check_nan:
        if not np.all(np.isfinite(apos)):
            bad = np.argwhere(~np.isfinite(apos))
            msg = "; ".join(f"atom {i}({es[i]}) axis {j}" for i, j in bad)
            raise ValueError(f"Geometry contains NaN/Inf: {msg}")

    # --- 2. Pairwise overlap ---
    if check_overlap and min_atom_distance is not None:
        for i in range(n):
            for j in range(i + 1, n):
                d = np.linalg.norm(apos[i] - apos[j])
                if d < min_atom_distance:
                    raise ValueError( f"Atoms {i}({es[i]}) and {j}({es[j]}) are nearly coincident (d={d:.4f} Å, limit={min_atom_distance} Å)" )

    # --- 3. Bond-length sanity using covalent radii ---
    if check_bonds and (max_bond_length is not None or min_bond_length is not None):
        # Build covalent-radius lookup from ELEMENTS table (index_Rcov = 6)
        rcov_map = {row[el.index_symbol]: row[el.index_Rcov] for row in el.ELEMENTS}
        radii = [rcov_map.get(e, 1.5) for e in es]
        for i in range(n):
            for j in range(i + 1, n):
                d = np.linalg.norm(apos[i] - apos[j])
                r_sum = radii[i] + radii[j]
                if d < r_sum + 0.4:  # consider bonded
                    if min_bond_length is not None and d < min_bond_length:
                        raise ValueError( f"Bond {i}({es[i]})–{j}({es[j]}) too short: d={d:.3f} Å < limit={min_bond_length} Å")
                    if max_bond_length is not None and d > max_bond_length:
                        raise ValueError( f"Bond {i}({es[i]})–{j}({es[j]}) too long: d={d:.3f} Å > limit={max_bond_length} Å" )

    # --- 4. Displacement vs reference ---
    if ref_geom is not None and max_atom_displacement is not None:
        ref_pos = ref_geom.apos if hasattr(ref_geom, 'apos') else ref_geom[0]
        ref_pos = np.asarray(ref_pos, dtype=np.float64)
        if ref_pos.shape != apos.shape:
            raise ValueError( f"validate_geometry: ref_geom shape {ref_pos.shape} != geom shape {apos.shape}"  )
        displacements = np.linalg.norm(apos - ref_pos, axis=1)
        max_d = float(np.max(displacements))
        if max_d > max_atom_displacement:
            i_max = int(np.argmax(displacements))
            raise ValueError( f"Atom {i_max}({es[i_max]}) displaced by {max_d:.2f} Å > limit={max_atom_displacement} Å vs reference geometry" )

    return True


# ============================================================= #
#  H-bond dimer construction (e-pair oriented monomers)          #
# ============================================================= #

def strip_epairs(mol):
    """Remove dummy electron-pair (E) atoms from an AtomicSystem."""
    to_rm = [i for i, e in enumerate(mol.enames) if e == 'E']
    if to_rm:
        mol.delete_atoms(to_rm)
    return mol


def _donor_h_index(mol, i_host, toward_axis):
    """H neighbor of host whose X-H vector is most aligned with toward_axis."""
    toward = np.asarray(toward_axis, dtype=np.float64)
    toward = toward / np.linalg.norm(toward)
    best_i, best_dot = None, -1e9
    for j in mol.ngs[i_host]:
        if mol.enames[j] != 'H':
            continue
        v = mol.apos[j] - mol.apos[i_host]
        v = v / np.linalg.norm(v)
        d = float(np.dot(v, toward))
        if d > best_dot:
            best_dot, best_i = d, j
    if best_i is None:
        raise ValueError(f"No H donor bonded to host atom {i_host} ({mol.enames[i_host]})")
    return best_i


def _rotate_frame_z_to_target(mol, target_axis, up_hint):
    """Rotate coordinates in-place so +Z maps to target_axis (orthogonal matrix)."""
    z = np.array([0.0, 0.0, 1.0])
    t = np.asarray(target_axis, dtype=np.float64)
    t = t / np.linalg.norm(t)
    if np.linalg.norm(t - z) < 1e-6:
        return
    if np.linalg.norm(t + z) < 1e-6:
        R = au.makeRotMatAng(np.pi, ax=(0, 2))  # 180° about Y: +Z -> -Z
        au.mulpos(mol.apos, R)
        return
    ref = np.array([1.0, 0.0, 0.0]) if abs(t[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    R = au.makeRotMat(t, ref)
    au.mulpos(mol.apos, R)


def _align_monomer_lp(mol, i_host, lp_sign=1.0):
    """Orient monomer in-place: host lone pair along lp_sign * Z; host at origin."""
    if mol.ngs is None:
        mol.neighs(bBond=True)
    origin, fw, up, _ = _mol_frame_from_epairs(mol, i_host)
    lp = -fw
    align = lp if lp_sign > 0 else -lp
    M = au.makeRotMat(align, up)
    mol.orient_mat(M, p0=origin)
    strip_epairs(mol)
    return mol


def _align_monomer_donor_h(mol, i_host, h_axis):
    """Orient monomer in-place: donor O->H vector along h_axis (H points toward acceptor lp)."""
    if mol.ngs is None:
        mol.neighs(bBond=True)
    origin, fw, up, _ = _mol_frame_from_epairs(mol, i_host)
    strip_epairs(mol)
    mol.neighs(bBond=True)
    ax = np.asarray(h_axis, dtype=np.float64)
    ax = ax / np.linalg.norm(ax)
    i_h = _donor_h_index(mol, i_host, ax)
    v = mol.apos[i_h] - mol.apos[i_host]
    M = au.makeRotMat(v, up)
    mol.orient_mat(M, p0=origin)  # v -> +Z
    _rotate_frame_z_to_target(mol, ax, up)  # +Z -> h_axis (incl. -Z toward acceptor lp)
    return mol


def build_hbond_dimer(mol_xyz, mol2_xyz=None, host=None, separation=2.9, axis=(0.0, 0.0, 1.0), preferred=('O', 'N')) -> AtomicSystem:
    """Build an H-bonded dimer from one or two XYZ monomers using e-pair orientation.

    Monomer A (acceptor): host lone pair along +axis.
    Monomer B (donor): donor X-H bond along -axis, host translated by separation * axis.
    For homodimers pass only mol_xyz; for heterodimers pass mol2_xyz as the second monomer file.

    Parameters
    ----------
    mol_xyz    : path to first monomer XYZ (acceptor side)
    mol2_xyz   : path to second monomer XYZ; None → same as mol_xyz (homodimer)
    host       : host element for lone-pair frame ('O', 'N', ...); None → first O then N
    separation : center-to-center shift of monomer B along axis (Å)
    axis       : H-bond axis unit vector (monomer A lone pair points +axis)
    preferred  : host element search order when host is None
    """
    preferred_hosts = (host,) if host else preferred
    path_b = mol2_xyz if mol2_xyz is not None else mol_xyz

    def _prepare(path):
        m = AtomicSystem(fname=path)
        m.neighs(bBond=True)
        m.preinitialize_atomic_properties()
        i_host, _ = _find_host_atom(m, preferred=preferred_hosts)
        return m, i_host

    mol_a, i_host_a = _prepare(mol_xyz)
    mol_b, i_host_b = _prepare(path_b)

    ax = np.asarray(axis, dtype=np.float64)
    nax = np.linalg.norm(ax)
    if nax < 1e-12:
        raise ValueError(f"build_hbond_dimer(): axis vector has zero length: {axis}")
    ax = ax / nax
    z = np.array([0.0, 0.0, 1.0])

    _align_monomer_lp(mol_a, i_host_a, lp_sign=+1.0)
    _align_monomer_donor_h(mol_b, i_host_b, h_axis=-z)

    if np.linalg.norm(ax - z) > 1e-6:
        _rotate_frame_z_to_target(mol_a, ax, np.array([1.0, 0.0, 0.0]))
        _rotate_frame_z_to_target(mol_b, -ax, np.array([1.0, 0.0, 0.0]))

    mol_b.apos += ax[None, :] * float(separation)

    dimer = copy.deepcopy(mol_a)
    dimer.addSystems(mol_b)
    dimer.natoms = len(dimer.apos)
    dimer.enames = list(dimer.enames)
    dimer.qs = dimer.Rs = None
    dimer.neighs(bBond=True)
    return dimer
