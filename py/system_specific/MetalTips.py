#!/usr/bin/python
"""
MetalTips.py — ASE-dependent builders for metal surfaces and clusters.

Generalizes surface_ase.py (was Ag-only) to any supported metal.
Currently supports FCC(111) surfaces with adatoms; BCC can be added later.
"""

import numpy as np

# ---- Lattice constants at room temperature (Å) ----
# FCC lattice constants for build_fcc111_adatom().
# For stable-FCC metals these are experimental RT values.
# For non-FCC metals (Ti,V,Cr,Mn,Fe,Co,Zn,Mo,W) these are the hypothetical/HT-FCC
# values used in the systematic trend study (see doc/MetalTip_Molecule_Interaction_Study_Spec.md §3.2).
# ⚠️ These should be replaced by DFT bulk FCC EOS fits (Phase 0) before production runs.
_LATTICE_A_FCC = {
    # stable FCC at RT
    'Ni': 3.524,  'Cu': 3.615,  'Al': 4.050,
    'Pd': 3.891,  'Ag': 4.086,  'Pt': 3.924,  'Au': 4.078,
    # high-T FCC phases (experimentally characterized, extrapolated to RT)
    'Fe': 3.57,   # γ-Fe (austenite)
    'Co': 3.54,   # β-Co
    'Mn': 3.59,   # γ-Mn
    # hypothetical FCC (volume-preserving estimates from RT BCC/HCP phase)
    'Ti': 4.13,   # from HCP a=2.95,c=4.68
    'V':  3.81,   # from BCC a=3.02
    'Cr': 3.63,   # from BCC a=2.88
    'Zn': 3.93,   # from HCP a=2.66,c=4.95
    'Mo': 3.96,   # from BCC a=3.147
    'W':  3.99,   # from BCC a=3.165
}

# BCC lattice constants (RT) — kept separate for future BCC(110) builder
_LATTICE_A_BCC = {
    'V':  3.02,   'Cr': 2.88,   'Fe': 2.866,
    'Mo': 3.147,  'W':  3.165,
}

# Default table for lattice_constant() — uses FCC values (for build_fcc111_adatom)
_LATTICE_A = _LATTICE_A_FCC


def _require_ase():
    """Fail loudly if ASE is not installed."""
    try:
        from ase.build import fcc111, add_adsorbate
        return fcc111, add_adsorbate
    except ImportError as e:
        raise ImportError(
            "ASE is required for MetalTips. Install:  pip install ase"
        ) from e


def lattice_constant(metal: str) -> float:
    """Return lattice constant (Å) for a metal.
    Raises ValueError if metal is not in the database."""
    if metal not in _LATTICE_A:
        known = ', '.join(sorted(_LATTICE_A))
        raise ValueError(
            f"Unknown metal '{metal}'. Known metals: {known}\n"
            f"Add '{metal}' to _LATTICE_A in MetalTips.py if needed."
        )
    return float(_LATTICE_A[metal])


def supported_metals() -> list:
    """Return list of supported metal symbols."""
    return sorted(_LATTICE_A.keys())


# =============================================================
#  FCC(111) surface with adatoms
# =============================================================

def build_fcc111_adatom(metal='Ag', size=(2, 2, 2), a=None, vacuum=10.0, height=2.0, position='fcc', periodic=True):
    """Build FCC(111) slab with a single adatom.

    Parameters
    ----------
    metal : str
        Element symbol (e.g. 'Cu', 'Ag', 'Au'). Default 'Ag'.
    size : tuple(int,int,int)
        Surface supercell (nx, ny, nz).
    a : float or None
        Lattice constant (Å). If None, looked up from internal table.
    vacuum, height, position, periodic
        Passed to ASE builders.

    Returns
    -------
    slab : ase.Atoms
    i_ad : int
        Index of the adatom in the slab.
    """
    fcc111, add_adsorbate = _require_ase()
    a = a if a is not None else lattice_constant(metal)

    slab = fcc111(metal, size=size, a=a, vacuum=vacuum, periodic=periodic)
    add_adsorbate(slab, metal, height=height, position=position)
    slab.center(vacuum=vacuum, axis=2)

    z = slab.get_positions()[:, 2]
    i_ad = int(np.argmax(z))
    return slab, i_ad


def build_fcc111_adatom_pair(metal='Ag', size=(2, 2, 2), a=None, vacuum=10.0, height=2.0, position0='fcc', shift_frac=(0.5, 0.0), periodic=True):
    """Build FCC(111) slab with two adatoms.

    Parameters
    ----------
    metal : str
        Element symbol. Default 'Ag'.
    size : tuple(int,int,int)
        Surface supercell.
    a : float or None
        Lattice constant (Å). Looked up if None.
    shift_frac : tuple(float,float)
        Fractional shift for second adatom in the surface plane.

    Returns
    -------
    slab : ase.Atoms
    i_ad0, i_ad1 : int
        Indices of the two adatoms.
    """
    fcc111, add_adsorbate = _require_ase()
    a = a if a is not None else lattice_constant(metal)

    slab = fcc111(metal, size=size, a=a, vacuum=vacuum, periodic=periodic)
    add_adsorbate(slab, metal, height=height, position=position0)

    ps = slab.get_positions()
    z = ps[:, 2]
    i_ad0 = int(np.argmax(z))
    r0 = ps[i_ad0].copy()

    cell = np.array(slab.get_cell(), dtype=float)
    a0 = cell[0].copy()
    a1 = cell[1].copy()
    dxy = float(shift_frac[0]) * a0[:2] + float(shift_frac[1]) * a1[:2]
    r1xy = (r0[:2] + dxy)

    add_adsorbate(slab, metal, height=height, position=(float(r1xy[0]), float(r1xy[1])))
    slab.center(vacuum=vacuum, axis=2)

    z2 = slab.get_positions()[:, 2]
    order = np.argsort(z2)[::-1]
    top2 = [int(order[0]), int(order[1])]
    return slab, top2[0], top2[1]


def build_fcc111_multi_adatom(metal='Ag', size=(3, 3, 3), a=None, vacuum=10.0, height=2.0,
                               adatom_shifts=None, periodic=True):
    """Build FCC(111) slab with multiple adatoms at fcc hollow sites.

    The first adatom is placed at the 'fcc' hollow site (by ASE). Additional
    adatoms are placed at positions shifted by fractions of the supercell
    lattice vectors. For a NxN supercell, a shift of (1/N, 0) moves to the
    nearest-neighbor fcc hollow site along lattice vector a0.

    Parameters
    ----------
    adatom_shifts : list of (fx, fy) tuples, or None
        Fractional shifts (in supercell coordinates) for each additional adatom
        relative to the first. The first adatom is always at (0,0) = 'fcc'.
        For a 3x3 cell:
          dimer:        [(1/3, 0)]
          trimer:       [(1/3, 0), (0, 1/3)]   # equilateral triangle
          row of 3:     [(1/3, 0), (2/3, 0)]
        If None, places a single adatom (same as build_fcc111_adatom).

    Returns
    -------
    slab : ase.Atoms
    adatom_indices : list of int
        Indices of all adatoms (highest-z atoms).
    """
    fcc111, add_adsorbate = _require_ase()
    a = a if a is not None else lattice_constant(metal)

    slab = fcc111(metal, size=size, a=a, vacuum=vacuum, periodic=periodic)
    add_adsorbate(slab, metal, height=height, position='fcc')

    ps = slab.get_positions()
    z = ps[:, 2]
    i_ad0 = int(np.argmax(z))
    r0 = ps[i_ad0].copy()

    cell = np.array(slab.get_cell(), dtype=float)
    a0 = cell[0].copy()
    a1 = cell[1].copy()

    if adatom_shifts is None:
        adatom_shifts = []

    for fx, fy in adatom_shifts:
        dxy = float(fx) * a0[:2] + float(fy) * a1[:2]
        rxy = (r0[:2] + dxy)
        add_adsorbate(slab, metal, height=height, position=(float(rxy[0]), float(rxy[1])))

    slab.center(vacuum=vacuum, axis=2)

    # Identify all adatoms: the highest-z atoms (one per adatom)
    ps2 = slab.get_positions()
    z2 = ps2[:, 2]
    n_ad = 1 + len(adatom_shifts)
    adatom_indices = list(np.argsort(z2)[::-1][:n_ad])
    adatom_indices = sorted(int(i) for i in adatom_indices)
    return slab, adatom_indices


def pick_fcc_hollow_base3(slab, i_adatom, z_tol=0.35):
    """Pick the 3 surface atoms forming the FCC hollow under an adatom.

    Returns
    -------
    base3 : tuple(int, int, int)
        Indices of the 3 base atoms (closest-to-farthest in xy).
    """
    ps = slab.get_positions()
    z = ps[:, 2]
    z_ad = float(z[i_adatom])

    mask = z < (z_ad - 0.5)
    if not np.any(mask):
        raise ValueError(
            "pick_fcc_hollow_base3(): cannot determine surface top layer"
        )
    z_surf = float(np.max(z[mask]))

    top_inds = np.where(np.abs(z - z_surf) < z_tol)[0]
    top_inds = [int(i) for i in top_inds if int(i) != int(i_adatom)]
    if len(top_inds) < 3:
        raise ValueError(
            f"pick_fcc_hollow_base3(): found only {len(top_inds)} top-layer atoms (need >=3)"
        )

    dxy = []
    pA = ps[i_adatom]
    for i in top_inds:
        dp = ps[i] - pA
        dxy.append((dp[0] * dp[0] + dp[1] * dp[1], i))
    dxy.sort(key=lambda x: x[0])
    base3 = [dxy[0][1], dxy[1][1], dxy[2][1]]

    # Re-order so that the atom with largest x is first
    bb = ps[base3]
    ix = int(np.argmax(bb[:, 0]))
    i0 = base3[ix]
    other = [base3[i] for i in range(3) if i != ix]
    return (i0, other[0], other[1])


# =============================================================
#  ASE ↔ CompChemUtils converters
# =============================================================

def slab_to_arrays(slab):
    """Convert ASE Atoms slab to (enames, apos, lvec, pbc) tuple."""
    es = list(slab.get_chemical_symbols())
    ps = np.array(slab.get_positions(), dtype=np.float64)
    lvec = np.array(slab.get_cell(), dtype=np.float64)
    pbc = tuple(bool(b) for b in slab.get_pbc())
    return es, ps, lvec, pbc


def layer_indices(slab, z_tol=0.35):
    """Group atom indices into layers by z-coordinate clustering.

    Returns a list of lists, sorted from bottom (lowest z) to top (highest z).
    Each inner list contains atom indices belonging to that layer.
    """
    ps = np.array(slab.get_positions(), dtype=float)
    z = ps[:, 2]
    order = np.argsort(z)
    layers = []
    current_layer = [int(order[0])]
    z_ref = float(z[order[0]])
    for k in range(1, len(order)):
        idx = int(order[k])
        if abs(z[idx] - z_ref) < z_tol:
            current_layer.append(idx)
        else:
            layers.append(current_layer)
            current_layer = [idx]
            z_ref = float(z[idx])
    layers.append(current_layer)
    return layers


def bottom_layer_indices(slab, n_layers, z_tol=0.35):
    """Return atom indices belonging to the lowest n_layers layers.

    Uses z-coordinate clustering to identify layers.
    """
    layers = layer_indices(slab, z_tol=z_tol)
    if n_layers > len(layers):
        raise ValueError(f"bottom_layer_indices: slab has only {len(layers)} layers, requested {n_layers}")
    indices = []
    for k in range(n_layers):
        indices.extend(layers[k])
    return sorted(indices)


def top_layer_indices(slab, exclude_adatom=True, z_tol=0.35):
    """Return atom indices of the highest layer, optionally excluding the adatom.

    If exclude_adatom=True, the single highest atom (adatom) is excluded
    and the next-highest layer is returned.
    """
    layers = layer_indices(slab, z_tol=z_tol)
    if exclude_adatom:
        # The adatom is the highest atom; the top slab layer is the second-highest layer
        if len(layers) < 2:
            raise ValueError("top_layer_indices: need at least 2 layers to exclude adatom")
        return sorted(layers[-2])
    return sorted(layers[-1])


# =============================================================
#  Metal clusters (non-ASE)
# =============================================================

def build_tetrahedron(metal='Ag', L=None):
    """Build a regular tetrahedral M4 cluster (3 base + 1 apex).

    Parameters
    ----------
    metal : str
        Element symbol. Used only for labelling; L is the key parameter.
    L : float or None
        Edge length (Å). If None, uses FCC nearest-neighbour distance
        computed from the lattice constant.

    Returns
    -------
    es : list[str]
    apos : ndarray (4,3)
    """
    a = lattice_constant(metal)
    if L is None:
        L = a / np.sqrt(2.0)  # FCC nearest-neighbour distance
    L = float(L)

    r = L / np.sqrt(3.0)
    h = L * np.sqrt(2.0 / 3.0)

    apex = np.array([0.0, 0.0, 0.0])
    base = np.array([
        [0.0,                    r,                   -h],
        [ r * np.sqrt(3.0) * 0.5, -r * 0.5,           -h],
        [-r * np.sqrt(3.0) * 0.5, -r * 0.5,           -h],
    ])
    apos = np.vstack([apex, base])
    es = [metal] * 4
    return es, apos


def build_bipyramid(metal='Ag', config='symmetric', L=None):
    """Build a 7-atom M cluster (5 base + 2 adatoms).

    Config 'symmetric':
        Two up-facing FCC hollows sharing one central base atom.
        Both adatoms are mirror-symmetric around the central atom.

    Config 'asymmetric':
        5 base atoms in a close-packed strip (3 bottom + 2 top offset).
        Adatoms sit above the two outer up-facing triangles.

    Parameters
    ----------
    metal : str
        Element symbol.
    config : str
        'symmetric' or 'asymmetric'.
    L : float or None
        Nearest-neighbour distance (Å). Uses FCC value if None.

    Returns
    -------
    es : list[str]
    apos : ndarray (7,3)
    """
    a = lattice_constant(metal)
    if L is None:
        L = a / np.sqrt(2.0)
    L = float(L)
    h = L * np.sqrt(2.0 / 3.0)

    if config == 'symmetric':
        # 5 base atoms: central + 4 around it in a diamond
        base5 = np.array([
            [0.0,          0.0,         0.0],           # central (0)
            [L,            0.0,         0.0],           # +x
            [-0.5 * L,     0.5 * L * np.sqrt(3.0),  0.0],  # upper-left
            [-0.5 * L,    -0.5 * L * np.sqrt(3.0),  0.0],  # lower-left
            [0.5 * L,      0.0,         0.0],           # inner-right
        ], dtype=float)
        ad0 = np.array([0.0,   0.5 * L / np.sqrt(3.0),  h])
        ad1 = np.array([0.0,  -0.5 * L / np.sqrt(3.0),  h])
        apos = np.vstack([base5, ad0, ad1])

    elif config == 'asymmetric':
        # 5 base atoms in a close-packed strip
        base5 = np.array([
            [0.0,          0.0,         0.0],
            [L,            0.0,         0.0],
            [2.0 * L,      0.0,         0.0],
            [0.5 * L,      0.5 * L * np.sqrt(3.0),  0.0],
            [1.5 * L,      0.5 * L * np.sqrt(3.0),  0.0],
        ], dtype=float)
        ad0 = np.array([0.5 * L,       L / np.sqrt(3.0),  h])
        ad1 = np.array([1.5 * L,       L / np.sqrt(3.0),  h])
        apos = np.vstack([base5, ad0, ad1])

    else:
        raise ValueError(f"Unknown config '{config}'. Use 'symmetric' or 'asymmetric'.")

    es = [metal] * 7
    return es, apos
