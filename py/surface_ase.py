#!/usr/bin/python

import numpy as np


def build_ag111_adatom(size=(2, 2, 2), a=4.086, vacuum=10.0, height=2.0, position='fcc', periodic=True):
    try:
        from ase.build import fcc111, add_adsorbate
    except Exception as e:
        raise ImportError("ASE is required for build_ag111_adatom(); install ase") from e

    slab = fcc111('Ag', size=size, a=a, vacuum=vacuum, periodic=periodic)
    add_adsorbate(slab, 'Ag', height=height, position=position)
    slab.center(vacuum=vacuum, axis=2)

    z = slab.get_positions()[:, 2]
    i_ad = int(np.argmax(z))
    return slab, i_ad


def build_ag111_adatom_pair(size=(2, 2, 2), a=4.086, vacuum=10.0, height=2.0, position0='fcc', shift_frac=(0.5, 0.0), periodic=True):
    try:
        from ase.build import fcc111, add_adsorbate
    except Exception as e:
        raise ImportError("ASE is required for build_ag111_adatom_pair(); install ase") from e

    slab = fcc111('Ag', size=size, a=a, vacuum=vacuum, periodic=periodic)
    add_adsorbate(slab, 'Ag', height=height, position=position0)

    ps = slab.get_positions()
    z = ps[:, 2]
    i_ad0 = int(np.argmax(z))
    r0 = ps[i_ad0].copy()

    cell = np.array(slab.get_cell(), dtype=float)
    a0 = cell[0].copy(); a1 = cell[1].copy()
    dxy = float(shift_frac[0]) * a0[:2] + float(shift_frac[1]) * a1[:2]
    r1xy = (r0[:2] + dxy)

    add_adsorbate(slab, 'Ag', height=height, position=(float(r1xy[0]), float(r1xy[1])))
    slab.center(vacuum=vacuum, axis=2)

    z2 = slab.get_positions()[:, 2]
    order = np.argsort(z2)[::-1]
    top2 = [int(order[0]), int(order[1])]
    return slab, top2[0], top2[1]


def pick_fcc_hollow_base3(slab, i_adatom, z_tol=0.35):
    ps = slab.get_positions()
    z = ps[:, 2]
    z_ad = float(z[i_adatom])

    mask = z < (z_ad - 0.5)
    if not np.any(mask):
        raise ValueError("pick_fcc_hollow_base3(): cannot determine surface top layer (no atoms below adatom)")
    z_surf = float(np.max(z[mask]))

    top_inds = np.where(np.abs(z - z_surf) < z_tol)[0]
    top_inds = [int(i) for i in top_inds if int(i) != int(i_adatom)]
    if len(top_inds) < 3:
        raise ValueError(f"pick_fcc_hollow_base3(): found only {len(top_inds)} top-layer atoms (need >=3)")

    dxy = []
    pA = ps[i_adatom]
    for i in top_inds:
        dp = ps[i] - pA
        dxy.append((dp[0] * dp[0] + dp[1] * dp[1], i))
    dxy.sort(key=lambda x: x[0])

    base3 = [dxy[0][1], dxy[1][1], dxy[2][1]]

    bb = ps[base3]
    ix = int(np.argmax(bb[:, 0]))
    i0 = base3[ix]
    other = [base3[i] for i in range(3) if i != ix]
    return (i0, other[0], other[1])


def slab_to_arrays(slab):
    ps = np.array(slab.get_positions(), dtype=float)
    es = list(slab.get_chemical_symbols())
    lvec = np.array(slab.get_cell(), dtype=float)
    pbc = tuple(bool(x) for x in slab.pbc)
    return es, ps, lvec, pbc
