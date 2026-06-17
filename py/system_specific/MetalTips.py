#!/usr/bin/python
"""
MetalTips.py — ASE-dependent builders for metal surfaces and clusters.

Generalizes surface_ase.py (was Ag-only) to any supported metal.
Currently supports FCC(111) surfaces with adatoms; BCC can be added later.
"""

import numpy as np

# ---- Lattice constants at room temperature (Å) ----
# Add new metals here as needed.
_LATTICE_A = {
    'Cu': 3.615,  'Ag': 4.086,  'Au': 4.078,
    'Pt': 3.924,  'Pd': 3.891,  'Ni': 3.524,
    'Al': 4.050,
    # BCC (future expansion)
    'Fe': 2.866,  'W' : 3.165,  'Mo': 3.147,
}


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
