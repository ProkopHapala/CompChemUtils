#!/usr/bin/env python3
"""Generate baked GPAW CO rigid-scan scripts for all non-equivalent heavy atoms.

Programmatically detects symmetry-equivalent atoms using C2(z), σ(xz), σ(yz)
operations (molecules are planar in xy-plane, aligned wrt xyz axes).
For each non-equivalent heavy atom (C, N, O), bakes out:
  - A standalone Python scan script (no external deps beyond GPAW/ASE/NumPy)
  - A PBS submission script

Also generates plots showing selected atoms per molecule.

Usage:
    python generate_CO_scan_jobs.py                          # default: ecut=500, vacuum=12
    python generate_CO_scan_jobs.py --ecut 200 --vacuum 8    # quick test
"""
import os, argparse, shutil, numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GEOM_DIR = os.path.join(SCRIPT_DIR, 'geometries')
JOBS_DIR = os.path.join(SCRIPT_DIR, 'jobs_CO_scan')
PLOT_DIR = os.path.join(SCRIPT_DIR, 'plots_CO_scan')

R_CO = 1.128  # CO bond length (Å)

MOLECULES = {
    'H2O':       {'ncpus': 4,  'mem': '16gb',  'walltime': '02:00:00'},
    'CH2O':      {'ncpus': 4,  'mem': '16gb',  'walltime': '02:00:00'},
    'CH2NH':     {'ncpus': 4,  'mem': '16gb',  'walltime': '02:00:00'},
    'C2H4':      {'ncpus': 4,  'mem': '16gb',  'walltime': '02:00:00'},
    'pyrrol':    {'ncpus': 8,  'mem': '24gb',  'walltime': '04:00:00'},
    'pyridine':  {'ncpus': 8,  'mem': '24gb',  'walltime': '04:00:00'},
    'pentacene': {'ncpus': 16, 'mem': '48gb',  'walltime': '12:00:00'},
    'PTCDA':     {'ncpus': 16, 'mem': '48gb',  'walltime': '12:00:00'},
}

HEAVY_ELEMS = {'C', 'N', 'O'}

# PySCF resources (generally lighter than GPAW PW for small molecules)
MOLECULES_PYSCF = {
    'H2O':       {'ncpus': 4,  'mem': '4gb',   'walltime': '01:00:00'},
    'CH2O':      {'ncpus': 4,  'mem': '4gb',   'walltime': '01:00:00'},
    'CH2NH':     {'ncpus': 4,  'mem': '4gb',   'walltime': '01:00:00'},
    'C2H4':      {'ncpus': 4,  'mem': '4gb',   'walltime': '01:00:00'},
    'pyrrol':    {'ncpus': 4,  'mem': '8gb',   'walltime': '02:00:00'},
    'pyridine':  {'ncpus': 4,  'mem': '8gb',   'walltime': '02:00:00'},
    'pentacene': {'ncpus': 8,  'mem': '16gb',  'walltime': '06:00:00'},
    'PTCDA':     {'ncpus': 8,  'mem': '16gb',  'walltime': '06:00:00'},
}


# ==================================================================
# XYZ reading (handles extended format with lattice vectors on line 2)
# ==================================================================

def read_xyz(fname):
    with open(fname) as f:
        lines = f.readlines()
    natm = int(lines[0].strip())
    syms, ps = [], []
    for i in range(2, 2 + natm):
        parts = lines[i].split()
        syms.append(parts[0])
        ps.append([float(parts[1]), float(parts[2]), float(parts[3])])
    return syms, np.array(ps)


# ==================================================================
# Symmetry detection for planar molecules aligned wrt xyz axes
# ==================================================================

def check_symmetry_op(syms, ps, transform, tol=0.05):
    """Check if transform maps molecule onto itself.
    transform: function (3,) -> (3,) that maps positions."""
    n = len(syms)
    used = [False] * n
    for i in range(n):
        mapped = transform(ps[i])
        found = False
        for j in range(n):
            if used[j] or syms[j] != syms[i]:
                continue
            if np.allclose(mapped, ps[j], atol=tol):
                used[j] = True
                found = True
                break
        if not found:
            return False
    return True


def find_symmetry_ops(syms, ps, tol=0.05):
    """Find all symmetry operations for a planar molecule in xy-plane.
    Tests C2(z), σ(xz), σ(yz) through candidate centers/planes.
    Deduplicates: keeps only one operation per type.
    Returns list of (name, transform_func, desc) tuples."""
    n = len(syms)
    ops = []
    centroid = ps.mean(axis=0)

    # --- C2(z) through candidate centers ---
    candidate_centers = set()
    candidate_centers.add((round(centroid[0], 3), round(centroid[1], 3)))  # molecular centroid
    for i in range(n):
        candidate_centers.add((round(ps[i, 0], 3), round(ps[i, 1], 3)))
        for j in range(i + 1, n):
            if syms[i] == syms[j]:
                c = 0.5 * (ps[i] + ps[j])
                candidate_centers.add((round(c[0], 3), round(c[1], 3)))

    c2z_found = False
    for cx, cy in sorted(candidate_centers):
        if c2z_found:
            break
        c = np.array([cx, cy, 0.0])
        def make_c2z(c):
            def t(p):
                return np.array([2 * c[0] - p[0], 2 * c[1] - p[1], p[2]])
            return t
        op = make_c2z(c)
        if check_symmetry_op(syms, ps, op, tol):
            ops.append(('C2z', op, f'center=({cx:.3f},{cy:.3f})'))
            c2z_found = True

    # --- σ(xz) at candidate y0 values ---
    candidate_y0 = set()
    candidate_y0.add(round(centroid[1], 3))  # molecular centroid y
    for i in range(n):
        candidate_y0.add(round(ps[i, 1], 3))
        for j in range(i + 1, n):
            if syms[i] == syms[j]:
                candidate_y0.add(round(0.5 * (ps[i, 1] + ps[j, 1]), 3))

    sxz_found = False
    for y0 in sorted(candidate_y0):
        if sxz_found:
            break
        def make_sx(y0):
            def t(p):
                return np.array([p[0], 2 * y0 - p[1], p[2]])
            return t
        op = make_sx(y0)
        if check_symmetry_op(syms, ps, op, tol):
            ops.append(('sxz', op, f'y0={y0:.3f}'))
            sxz_found = True

    # --- σ(yz) at candidate x0 values ---
    candidate_x0 = set()
    candidate_x0.add(round(centroid[0], 3))  # molecular centroid x
    for i in range(n):
        candidate_x0.add(round(ps[i, 0], 3))
        for j in range(i + 1, n):
            if syms[i] == syms[j]:
                candidate_x0.add(round(0.5 * (ps[i, 0] + ps[j, 0]), 3))

    syz_found = False
    for x0 in sorted(candidate_x0):
        if syz_found:
            break
        def make_sy(x0):
            def t(p):
                return np.array([2 * x0 - p[0], p[1], p[2]])
            return t
        op = make_sy(x0)
        if check_symmetry_op(syms, ps, op, tol):
            ops.append(('syz', op, f'x0={x0:.3f}'))
            syz_found = True

    return ops


def find_equiv_classes(syms, ps, ops, tol=0.05):
    """Group atoms into equivalence classes using found symmetry operations."""
    n = len(syms)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    for i in range(n):
        for name, op, desc in ops:
            mapped = op(ps[i])
            for j in range(n):
                if i == j or syms[i] != syms[j]:
                    continue
                if np.allclose(mapped, ps[j], atol=tol):
                    union(i, j)
                    break

    classes = {}
    for i in range(n):
        r = find(i)
        classes.setdefault(r, []).append(i)
    return list(classes.values())


def select_heavy_atoms(syms, ps, classes, ops):
    """Select one representative from each class containing heavy atoms (C, N, O).
    Picks representatives in the same fundamental domain (same side of all symmetry planes).
    Returns list of (atom_index, label) tuples."""
    # Extract symmetry plane parameters from ops
    x0 = None  # σ(yz) plane x-coordinate
    y0 = None  # σ(xz) plane y-coordinate
    cx, cy = None, None  # C2z center
    for name, _, desc in ops:
        if name == 'syz':
            # desc format: "x0=0.000"
            x0 = float(desc.split('=')[1])
        elif name == 'sxz':
            y0 = float(desc.split('=')[1])
        elif name == 'C2z':
            # desc format: "center=(cx,cy)"
            import re
            m = re.findall(r'[-\d.]+', desc)
            cx, cy = float(m[0]), float(m[1])

    # If we have C2z but no mirror planes, use center as plane references
    if cx is not None and x0 is None:
        x0 = cx
    if cy is not None and y0 is None:
        y0 = cy

    selected = []
    for cls in classes:
        # Filter to heavy atoms
        heavy_cls = [idx for idx in cls if syms[idx] in HEAVY_ELEMS]
        if not heavy_cls:
            continue

        # Pick representative in the "positive" fundamental domain:
        # x >= x0 and y >= y0 (if planes known)
        best = None
        best_score = -1
        for idx in heavy_cls:
            px, py = ps[idx, 0], ps[idx, 1]
            score = 0
            if x0 is not None and px >= x0 - 1e-3:
                score += 2
            elif x0 is not None:
                score -= 2
            if y0 is not None and py >= y0 - 1e-3:
                score += 1
            elif y0 is not None:
                score -= 1
            # Tie-break: closer to the plane intersection (more central)
            if best is None or score > best_score:
                best = idx
                best_score = score
            elif score == best_score:
                # Prefer atom closer to fundamental domain corner
                dist = 0
                if x0 is not None:
                    dist += (px - x0) ** 2
                if y0 is not None:
                    dist += (py - y0) ** 2
                best_dist = 0
                if x0 is not None:
                    best_dist += (ps[best, 0] - x0) ** 2
                if y0 is not None:
                    best_dist += (ps[best, 1] - y0) ** 2
                if dist < best_dist:
                    best = idx

        label = f"{syms[best]}{best + 1}"
        selected.append((best, label))

    selected.sort(key=lambda x: x[0])
    return selected


# ==================================================================
# Plotting
# ==================================================================

ELEM_COLORS = {'H': '#cccccc', 'C': '#2b2b2b', 'N': '#3b6fdb', 'O': '#e03030'}
ELEM_SIZES  = {'H': 150, 'C': 300, 'N': 300, 'O': 300}
SELECT_COLOR = '#ffcc00'
SELECT_EDGE = '#ff0000'


def plot_molecule(syms, ps, selected, equiv_classes, mol_name, ops_desc, fname):
    """Plot molecule in xy-plane with selected atoms highlighted."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    sel_set = {idx for idx, _ in selected}
    # Color by equivalence class
    class_colors = plt.cm.Set1(np.linspace(0, 1, max(len(equiv_classes), 1)))

    fig, ax = plt.subplots(figsize=(10, 8))

    # Draw bonds
    for i in range(len(syms)):
        for j in range(i + 1, len(syms)):
            d = np.linalg.norm(ps[i] - ps[j])
            if d < 1.8:
                ax.plot([ps[i, 0], ps[j, 0]], [ps[i, 1], ps[j, 1]], 'k-', lw=1.5, zorder=1)

    # Draw atoms
    for i, (s, p) in enumerate(zip(syms, ps)):
        c = ELEM_COLORS.get(s, '#2b8c4e')
        sz = ELEM_SIZES.get(s, 200)
        if i in sel_set:
            ax.scatter(p[0], p[1], c=SELECT_COLOR, s=sz * 2.5, edgecolors=SELECT_EDGE,
                       linewidths=2.5, zorder=10)
            label = [lbl for idx, lbl in selected if idx == i][0]
            ax.annotate(label, (p[0], p[1]), color='black', fontsize=9, fontweight='bold',
                        ha='center', va='center', zorder=12,
                        bbox=dict(boxstyle='round,pad=0.15', fc='white', ec=SELECT_EDGE, alpha=0.85))
        else:
            # Find class index for coloring
            cls_idx = next((ci for ci, cls in enumerate(equiv_classes) if i in cls), 0)
            ax.scatter(p[0], p[1], c=c, s=sz, edgecolors='black', linewidths=0.8, zorder=5)
            ax.text(p[0], p[1], f'{s}{i+1}', color='white', fontsize=6, ha='center', va='center', zorder=6)

    # Draw CO approach arrows for selected atoms
    for idx, label in selected:
        p = ps[idx]
        ax.annotate('', xy=(p[0], p[1] + 0.3), xytext=(p[0], p[1] + 1.5),
                    arrowprops=dict(arrowstyle='->', color=SELECT_EDGE, lw=2), zorder=8)
        ax.text(p[0], p[1] + 1.7, 'CO↓', color=SELECT_EDGE, fontsize=7, ha='center', fontweight='bold')

    ax.set_aspect('equal')
    ax.set_xlabel('x (Å)')
    ax.set_ylabel('y (Å)')
    sym_str = ', '.join(ops_desc) if ops_desc else 'C1'
    ax.set_title(f'{mol_name} — selected non-equivalent heavy atoms\nSymmetry ops: {sym_str}', fontsize=11)
    ax.grid(True, alpha=0.2)

    # Legend
    from matplotlib.lines import Line2D
    handles = [Line2D([0], [0], marker='o', color='w', markerfacecolor=SELECT_COLOR,
                      markeredgecolor=SELECT_EDGE, markersize=12, label='Selected (scan target)')]
    for elem in ['C', 'N', 'O', 'H']:
        if elem in syms:
            handles.append(Line2D([0], [0], marker='o', color='w', markerfacecolor=ELEM_COLORS[elem],
                                  markeredgecolor='black', markersize=8, label=elem))
    ax.legend(handles=handles, loc='upper right', fontsize=9)

    fig.tight_layout()
    fig.savefig(fname, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"  Plot: {fname}")


def plot_overview(all_mols_data, fname):
    """Combined overview plot of all molecules."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    n = len(all_mols_data)
    ncols = 3
    nrows = (n + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(7 * ncols, 5 * nrows))
    axes_flat = axes.flatten() if hasattr(axes, 'flatten') else [axes]

    for idx, (mol_name, syms, ps, selected, equiv_classes, ops_desc) in enumerate(all_mols_data):
        ax = axes_flat[idx]
        sel_set = {i for i, _ in selected}

        for i in range(len(syms)):
            for j in range(i + 1, len(syms)):
                d = np.linalg.norm(ps[i] - ps[j])
                if d < 1.8:
                    ax.plot([ps[i, 0], ps[j, 0]], [ps[i, 1], ps[j, 1]], 'k-', lw=1, zorder=1)

        for i, (s, p) in enumerate(zip(syms, ps)):
            c = ELEM_COLORS.get(s, '#2b8c4e')
            sz = ELEM_SIZES.get(s, 200)
            if i in sel_set:
                ax.scatter(p[0], p[1], c=SELECT_COLOR, s=sz * 2, edgecolors=SELECT_EDGE,
                           linewidths=2, zorder=10)
                label = [lbl for idx2, lbl in selected if idx2 == i][0]
                ax.annotate(label, (p[0], p[1]), color='black', fontsize=8, fontweight='bold',
                            ha='center', va='center', zorder=12,
                            bbox=dict(boxstyle='round,pad=0.1', fc='white', ec=SELECT_EDGE, alpha=0.85))
            else:
                ax.scatter(p[0], p[1], c=c, s=sz, edgecolors='black', linewidths=0.5, zorder=5)
                ax.text(p[0], p[1], f'{s}{i+1}', color='white', fontsize=5, ha='center', va='center', zorder=6)

        sym_str = ', '.join(ops_desc) if ops_desc else 'C1'
        ax.set_aspect('equal')
        ax.set_title(f'{mol_name} ({sym_str})', fontsize=10)
        ax.grid(True, alpha=0.2)

    for idx in range(n, len(axes_flat)):
        axes_flat[idx].set_visible(False)

    fig.suptitle('Non-equivalent heavy atoms for CO rigid scan (programmatic symmetry detection)',
                 fontsize=14, fontweight='bold')
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(fname, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"\n  Overview: {fname}")


# ==================================================================
# Scan grid
# ==================================================================

def make_scan_grid(r_start=1.5, r_fine_end=3.0, dr_fine=0.1,
                   r_coarse_end=6.0, dr_coarse=0.25, r_inf=15.0):
    r_fine   = np.arange(r_start, r_fine_end + 1e-9, dr_fine)
    r_coarse = np.arange(r_fine_end + dr_coarse, r_coarse_end + 1e-9, dr_coarse)
    return np.concatenate([r_fine, r_coarse, [r_inf]])


# ==================================================================
# Box positions (center in vacuum cell)
# ==================================================================

def box_positions(mol_ps, co_ps, vacuum_xy, z_cell):
    """Center molecule + CO in a cell with vacuum_xy padding in x,y and fixed z_cell in z.
    Returns (all_ps_shifted, cell)."""
    all_ps = np.vstack([mol_ps, co_ps])
    rmin = all_ps.min(axis=0)
    rmax = all_ps.max(axis=0)
    extent = rmax - rmin
    cell = np.array([extent[0] + 2 * vacuum_xy, extent[1] + 2 * vacuum_xy, z_cell])
    shift = 0.5 * cell - 0.5 * (rmin + rmax)
    return all_ps + shift, cell


def box_molecule(mol_ps, vacuum_xy, z_cell):
    """Center molecule alone in a cell with vacuum_xy padding in x,y and fixed z_cell in z.
    Returns (mol_ps_shifted, cell)."""
    rmin = mol_ps.min(axis=0)
    rmax = mol_ps.max(axis=0)
    extent = rmax - rmin
    cell = np.array([extent[0] + 2 * vacuum_xy, extent[1] + 2 * vacuum_xy, z_cell])
    shift = 0.5 * cell - 0.5 * (rmin + rmax)
    return mol_ps + shift, cell


# ==================================================================
# Bake standalone scan script
# ==================================================================

def bake_scan_script(mol, syms, mol_ps, atom_idx, atom_label, ecut, vacuum, z_cell, xc, r_grid, spec):
    """Bake a standalone GPAW scan script for one (molecule, atom) pair."""
    n_mol = len(syms)
    outdir_rel = f"results/CO_scan_{mol}_{xc}_{int(ecut)}eV"
    tag = f"{mol}_atom{atom_idx}_{atom_label}"

    # Pre-compute boxed molecule positions (for E_mol calc)
    mol_boxed, mol_cell = box_molecule(mol_ps, vacuum, z_cell)

    # Pre-compute CO positions for each r (O-apex: O closer to molecule)
    co_positions_per_r = []
    for r in r_grid:
        o_pos = mol_ps[atom_idx] + np.array([0.0, 0.0, r])
        c_pos = o_pos + np.array([0.0, 0.0, R_CO])
        co_positions_per_r.append((c_pos.tolist(), o_pos.tolist()))

    # Pre-compute boxed positions for each r
    boxed_per_r = []
    cells_per_r = []
    for c_pos, o_pos in co_positions_per_r:
        all_boxed, cell = box_positions(mol_ps, np.array([c_pos, o_pos]), vacuum, z_cell)
        boxed_per_r.append(all_boxed.tolist())
        cells_per_r.append(cell.tolist())

    # Reverse: scan from far (non-interacting) to near for better SCF convergence
    r_list = r_grid.tolist()[::-1]
    boxed_per_r = boxed_per_r[::-1]
    cells_per_r = cells_per_r[::-1]

    return f'''#!/usr/bin/env python3
"""CO rigid scan over {mol} atom {atom_idx} ({atom_label}).
GPAW {xc} PW({int(ecut)}eV) vacuum_xy={vacuum}A z_cell={z_cell}A. Independent SCF per frame (no restart).
Scan order: far -> near (for consistent reference).

E_int(r) = E_total(r) - E_mol - E_CO

Auto-generated by generate_CO_scan_jobs.py — no external dependencies.
"""
import os, numpy as np
from ase import Atoms
from gpaw import GPAW, PW, FermiDirac

MOL = "{mol}"
ATOM_IDX = {atom_idx}
ATOM_LABEL = "{atom_label}"
ECUT = {ecut}
XC = "{xc}"
VACUUM_XY = {vacuum}
Z_CELL = {z_cell}
R_CO = {R_CO}

OUTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "{outdir_rel}")
os.makedirs(OUTDIR, exist_ok=True)

TAG = "{tag}"

R_GRID = {r_list!r}
MOL_SYMS = {syms!r}
MOL_BOXED = {mol_boxed.tolist()!r}
MOL_CELL = {mol_cell.tolist()!r}
BOXED_PER_R = {boxed_per_r!r}
CELLS_PER_R = {cells_per_r!r}

ALL_SYMS = MOL_SYMS + ['C', 'O']

# --- 1. Isolated molecule ---
mol_atoms = Atoms(symbols=MOL_SYMS, positions=MOL_BOXED, cell=MOL_CELL, pbc=True)
mol_calc = GPAW(mode=PW(ECUT), xc=XC, charge=0, spinpol=False,
                occupations=FermiDirac(0.05), kpts=(1,1,1), symmetry='off',
                maxiter=200,
                convergence=dict(energy=1e-5, density=1e-5, bands='occupied'),
                txt=os.path.join(OUTDIR, TAG + '_mol.txt'))
mol_atoms.calc = mol_calc
E_mol = mol_atoms.get_potential_energy()
print(f"[{{TAG}}] E_mol = {{E_mol:.6f}} eV")

# --- 2. Isolated CO ---
co_center = 0.5 * np.array(MOL_CELL)
co_atoms = Atoms(symbols=['C', 'O'],
                 positions=[co_center - np.array([0, 0, R_CO/2]),
                            co_center + np.array([0, 0, R_CO/2])],
                 cell=MOL_CELL, pbc=True)
co_calc = GPAW(mode=PW(ECUT), xc=XC, charge=0, spinpol=False,
               occupations=FermiDirac(0.05), kpts=(1,1,1), symmetry='off',
               maxiter=200,
               convergence=dict(energy=1e-5, density=1e-5, bands='occupied'),
               txt=os.path.join(OUTDIR, TAG + '_CO.txt'))
co_atoms.calc = co_calc
E_CO = co_atoms.get_potential_energy()
print(f"[{{TAG}}] E_CO  = {{E_CO:.6f}} eV")

# --- 3. Scan (independent SCF per frame, no restart) ---
# PW restart (density on grid) is NOT useful when atoms move between frames:
# the restart density has peaks where atoms no longer are, so SCF must unrelax
# wrong density first. Starting from atomic densities is cleaner and often faster.
# Without restart, each frame can also use its own optimally-sized cell.
dat_file = os.path.join(OUTDIR, TAG + '_scan.dat')
dat_fh = open(dat_file, 'w')
dat_fh.write(f"# CO rigid scan over {{MOL}} atom {{ATOM_IDX}} ({{ATOM_LABEL}})\\n")
dat_fh.write(f"# Method: GPAW {{XC}} PW({{int(ECUT)}}eV) vacuum_xy={{VACUUM_XY}}A z_cell={{Z_CELL}}A\\n")
dat_fh.write(f"# E_mol = {{E_mol:.6f}} eV, E_CO = {{E_CO:.6f}} eV\\n")
dat_fh.write("# r(A)    E_int(eV)\\n")
dat_fh.flush()

for ir, r in enumerate(R_GRID):
    boxed = BOXED_PER_R[ir]
    cell = CELLS_PER_R[ir]

    # # Old: PW restart from previous frame's density (commented out — see justification above)
    # if ir > 0 and os.path.isfile(RESTART_FILE):
    #     prev_atoms, calc = gpaw_restart(RESTART_FILE, txt=...)
    #     prev_atoms.set_cell(CONST_CELL, scale_atoms=False)
    #     prev_atoms.positions = boxed
    #     combined = prev_atoms
    # else:
    #     combined = Atoms(symbols=ALL_SYMS, positions=boxed, cell=CONST_CELL, pbc=True)
    #     calc = GPAW(...)
    #     combined.calc = calc

    combined = Atoms(symbols=ALL_SYMS, positions=boxed, cell=cell, pbc=True)
    calc = GPAW(mode=PW(ECUT), xc=XC, charge=0, spinpol=False,
                occupations=FermiDirac(0.05), kpts=(1,1,1), symmetry='off',
                maxiter=200,
                convergence=dict(energy=1e-5, density=1e-5, bands='occupied'),
                txt=os.path.join(OUTDIR, TAG + f'_r{{r:.2f}}.txt'))
    combined.calc = calc

    E = combined.get_potential_energy()
    E_int = E - E_mol - E_CO
    dat_fh.write(f"{{r:.4f}}  {{E_int:.8f}}\\n")
    dat_fh.flush()
    print(f"[{{TAG}}] r={{r:6.2f}}  E_tot={{E:12.6f}}  E_int={{E_int:12.6f}} eV")

    # calc.write(RESTART_FILE, mode='all')  # no longer needed — independent SCF per frame

dat_fh.close()
print(f"[{{TAG}}] Saved: {{dat_file}}")

# No restart file to clean up — independent SCF per frame
'''


def bake_pbs(mol, atom_idx, atom_label, spec, ecut, vacuum, z_cell, xc):
    tag = f"{mol}_atom{atom_idx}_{atom_label}"
    return f'''#!/bin/bash
#PBS -N COscan_{tag}
#PBS -l select=1:ncpus={spec['ncpus']}:mem={spec['mem']}:scratch_local=10gb
#PBS -l walltime={spec['walltime']}
#PBS -j oe
#PBS -m bae
#PBS -q luna

# CO scan {tag} | GPAW {xc} PW({int(ecut)}eV) vacuum_xy={vacuum} z_cell={z_cell}
# {spec['ncpus']} CPUs, {spec['mem']} RAM, {spec['walltime']}

cleanup_gpaw() {{
  mkdir -p $PBS_O_WORKDIR/results
  find $SCRATCHDIR/results -name '*.dat' -exec cp --parents {{}} $PBS_O_WORKDIR/ \; 2>/dev/null
  find $SCRATCHDIR/results -name '*.txt' -exec cp --parents {{}} $PBS_O_WORKDIR/ \; 2>/dev/null
  rm -rf $SCRATCHDIR/* 2>/dev/null
}}
trap cleanup_gpaw EXIT

cd $PBS_O_WORKDIR
module purge
module add py-gpaw/24.1.0-gcc-10.2.1-fojjhkw
export GPAW_SETUP_PATH=/storage/praha1/home/prokop/gpaw-setups-24.1.0/gpaw-setups-24.1.0
export OMP_NUM_THREADS=1

echo "=== COscan_{tag} === $(date)"

cp $PBS_O_WORKDIR/run_{tag}.py $SCRATCHDIR/
cd $SCRATCHDIR
mpirun -np $PBS_NUM_PPN python3 run_{tag}.py 2>&1

echo "Finished: $(date)"
'''


def bake_submit_all(job_list):
    """Generate submit_all.sh for all CO scan jobs."""
    lines = ['#!/bin/bash',
             '# ==================================================================',
             '# Submit all CO rigid-scan jobs to Metacentrum queue',
             '# Auto-generated by generate_CO_scan_jobs.py',
             '# ==================================================================',
             '',
             'cd "$(dirname "$0")"',
             '',
             'for f in submit_*.pbs; do',
             '    echo "Submitting $f ..."',
             '    qsub "$f"',
             'done',
             '',
             'echo ""',
             'echo "Check status: qstat -u $USER"',
             '']
    return '\n'.join(lines)


# ==================================================================
# PySCF scan script baking
# ==================================================================

def bake_pyscf_scan_script(mol, syms, mol_ps, atom_idx, atom_label, basis, xc, r_grid, spec):
    """Bake a standalone PySCF DFT scan script for one (molecule, atom) pair."""
    n_mol = len(syms)
    outdir_rel = f"results/CO_scan_{mol}_{xc}_{basis}"
    tag = f"{mol}_atom{atom_idx}_{atom_label}"

    # Build atom string for isolated molecule (in Å, PySCF uses Å by default)
    mol_atom_str = '; '.join(f"{s} {p[0]:.6f} {p[1]:.6f} {p[2]:.6f}"
                             for s, p in zip(syms, mol_ps))

    # Build CO positions for each r (O-apex: O closer to molecule)
    co_atoms_per_r = []
    for r in r_grid:
        o_pos = mol_ps[atom_idx] + np.array([0.0, 0.0, r])
        c_pos = o_pos + np.array([0.0, 0.0, R_CO])
        co_atoms_per_r.append((c_pos.tolist(), o_pos.tolist()))

    # Reverse: scan from far (non-interacting) to near for better SCF convergence
    r_list = r_grid.tolist()[::-1]
    co_atoms_per_r = co_atoms_per_r[::-1]

    return f'''#!/usr/bin/env python3
"""CO rigid scan over {mol} atom {atom_idx} ({atom_label}).
PySCF DFT {xc}/{basis}. No periodic cell (molecular calculation).
Scan order: far -> near (for SCF convergence). Reuses DM from previous step.

E_int(r) = E_total(r) - E_mol - E_CO

Auto-generated by generate_CO_scan_jobs.py — no external dependencies.
"""
import os, numpy as np
from pyscf import gto, dft, lib

MOL = "{mol}"
ATOM_IDX = {atom_idx}
ATOM_LABEL = "{atom_label}"
BASIS = "{basis}"
XC = "{xc}"
R_CO = {R_CO}

OUTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "{outdir_rel}")
os.makedirs(OUTDIR, exist_ok=True)

TAG = "{tag}"

R_GRID = {r_list!r}
MOL_ATOM_STR = "{mol_atom_str}"
MOL_SYMS = {syms!r}
MOL_PS = {mol_ps.tolist()!r}
CO_ATOMS_PER_R = {co_atoms_per_r!r}

lib.num_threads = int(os.environ.get("OMP_NUM_THREADS", {spec['ncpus']}))

# --- 1. Isolated molecule ---
mol_mol = gto.M(atom=MOL_ATOM_STR, basis=BASIS, unit='Angstrom',
                verbose=4, output=os.path.join(OUTDIR, TAG + '_mol.out'))
mf_mol = dft.RKS(mol_mol)
mf_mol.xc = XC
mf_mol = mf_mol.density_fit()
mf_mol.grids.level = 4
E_mol = mf_mol.kernel()
print(f"[{{TAG}}] E_mol = {{E_mol:.6f}} Ha = {{E_mol * 27.2114:.6f}} eV")

# --- 2. Isolated CO ---
co_str = f"C 0 0 0; O 0 0 {{R_CO}}"
mol_co = gto.M(atom=co_str, basis=BASIS, unit='Angstrom',
               verbose=4, output=os.path.join(OUTDIR, TAG + '_CO.out'))
mf_co = dft.RKS(mol_co)
mf_co.xc = XC
mf_co = mf_co.density_fit()
mf_co.grids.level = 4
E_CO = mf_co.kernel()
print(f"[{{TAG}}] E_CO  = {{E_CO:.6f}} Ha = {{E_CO * 27.2114:.6f}} eV")

# --- 3. Scan (far -> near, reuse DM from previous step) ---
dat_file = os.path.join(OUTDIR, TAG + '_scan.dat')
dat_fh = open(dat_file, 'w')
dat_fh.write(f"# CO rigid scan over {{MOL}} atom {{ATOM_IDX}} ({{ATOM_LABEL}})\\n")
dat_fh.write(f"# Method: PySCF DFT {{XC}}/{{BASIS}}\\n")
dat_fh.write(f"# E_mol = {{E_mol:.6f}} Ha, E_CO = {{E_CO:.6f}} Ha\\n")
dat_fh.write("# r(A)    E_int(Ha)    E_int(eV)\\n")
dat_fh.flush()

prev_dm = None
for ir, r in enumerate(R_GRID):
    c_pos, o_pos = CO_ATOMS_PER_R[ir]
    # Build combined atom string: molecule + CO
    atoms_str = MOL_ATOM_STR + f"; C {{c_pos[0]:.6f}} {{c_pos[1]:.6f}} {{c_pos[2]:.6f}}; O {{o_pos[0]:.6f}} {{o_pos[1]:.6f}} {{o_pos[2]:.6f}}"

    mol_tot = gto.M(atom=atoms_str, basis=BASIS, unit='Angstrom',
                    verbose=4, output=os.path.join(OUTDIR, TAG + f'_r{{r:.2f}}.out'))
    mf_tot = dft.RKS(mol_tot)
    mf_tot.xc = XC
    mf_tot = mf_tot.density_fit()
    mf_tot.grids.level = 4
    E_tot = mf_tot.kernel(dm0=prev_dm)
    prev_dm = mf_tot.make_rdm1()
    E_int_ha = E_tot - E_mol - E_CO
    E_int_ev = E_int_ha * 27.2114
    dat_fh.write(f"{{r:.4f}}  {{E_int_ha:.8f}}  {{E_int_ev:.8f}}\\n")
    dat_fh.flush()
    print(f"[{{TAG}}] r={{r:6.2f}}  E_tot={{E_tot:.6f}} Ha  E_int={{E_int_ha:.6f}} Ha = {{E_int_ev:.6f}} eV")

dat_fh.close()
print(f"[{{TAG}}] Saved: {{dat_file}}")
'''


def bake_pyscf_pbs(mol, atom_idx, atom_label, spec, basis, xc):
    tag = f"{mol}_atom{atom_idx}_{atom_label}"
    return f'''#!/bin/bash
#PBS -N COscan_pyscf_{tag}
#PBS -l select=1:ncpus={spec['ncpus']}:mem={spec['mem']}:scratch_local=10gb
#PBS -l walltime={spec['walltime']}
#PBS -j oe
#PBS -m bae
#PBS -q luna

# CO scan {tag} | PySCF DFT {xc}/{basis}
# {spec['ncpus']} CPUs, {spec['mem']} RAM, {spec['walltime']}

trap 'cp -r $SCRATCHDIR/* $PBS_O_WORKDIR/ 2>/dev/null; rm -rf $SCRATCHDIR/* 2>/dev/null' EXIT

cd $PBS_O_WORKDIR
module purge
module add mambaforge
export OMP_NUM_THREADS=$PBS_NUM_PPN

echo "=== COscan_pyscf_{tag} === $(date)"

cp $PBS_O_WORKDIR/run_{tag}.py $SCRATCHDIR/
cd $SCRATCHDIR
python3 run_{tag}.py 2>&1

echo "Finished: $(date)"
cp -r $SCRATCHDIR/results $PBS_O_WORKDIR/ 2>/dev/null
'''

# ==================================================================
# Main
# ==================================================================

def main():
    parser = argparse.ArgumentParser(description='Generate CO rigid-scan jobs with symmetry detection')
    parser.add_argument('--ecut', type=float, default=500.0, help='GPAW PW cutoff (eV)')
    parser.add_argument('--vacuum', type=float, default=6.0, help='Vacuum padding in x,y (Å) for GPAW')
    parser.add_argument('--z_cell', type=float, default=30.0, help='Fixed cell z-dimension (Å) for GPAW')
    parser.add_argument('--xc', type=str, default='PBE')
    parser.add_argument('--tol', type=float, default=0.1, help='Symmetry tolerance (Å)')
    parser.add_argument('--pyscf', action='store_true', help='Also generate PySCF DFT jobs')
    parser.add_argument('--basis', type=str, default='def2-SVP', help='PySCF basis set (double-zeta)')
    args = parser.parse_args()

    os.makedirs(JOBS_DIR, exist_ok=True)
    os.makedirs(PLOT_DIR, exist_ok=True)
    geom_dst = os.path.join(JOBS_DIR, 'geometries')
    os.makedirs(geom_dst, exist_ok=True)

    if args.pyscf:
        pyscf_jobs_dir = os.path.join(SCRIPT_DIR, 'jobs_CO_scan_pyscf')
        os.makedirs(pyscf_jobs_dir, exist_ok=True)
        geom_dst_pyscf = os.path.join(pyscf_jobs_dir, 'geometries')
        os.makedirs(geom_dst_pyscf, exist_ok=True)

    r_grid = make_scan_grid()

    print(f"Generating CO scan jobs: ecut={args.ecut} vacuum_xy={args.vacuum} z_cell={args.z_cell} xc={args.xc}")
    if args.pyscf:
        print(f"Also generating PySCF DFT jobs: basis={args.basis} xc={args.xc}")
    print(f"Scan grid: {len(r_grid)} points, r=[{r_grid[0]:.2f}..{r_grid[-1]:.2f}] Å")
    print(f"Output: {JOBS_DIR}/")
    if args.pyscf:
        print(f"PySCF output: {pyscf_jobs_dir}/")
    print()

    all_mols_data = []
    n_scripts = 0
    n_pyscf_scripts = 0

    for mol, spec in MOLECULES.items():
        xyz_path = os.path.join(GEOM_DIR, f'{mol}.xyz')
        if not os.path.isfile(xyz_path):
            print(f"  WARNING: {xyz_path} not found, skipping {mol}")
            continue
        shutil.copy2(xyz_path, geom_dst)
        if args.pyscf:
            shutil.copy2(xyz_path, geom_dst_pyscf)

        syms, ps = read_xyz(xyz_path)

        # Detect symmetry
        ops = find_symmetry_ops(syms, ps, tol=args.tol)
        ops_desc = [f"{name}({desc})" for name, _, desc in ops]
        if not ops:
            ops_desc = ['C1 (no symmetry)']

        # Find equivalence classes
        classes = find_equiv_classes(syms, ps, ops, tol=args.tol)

        # Select non-equivalent heavy atoms
        selected = select_heavy_atoms(syms, ps, classes, ops)

        print(f"  {mol:12s} sym=[{', '.join(ops_desc)}]")
        print(f"  {'':12s} {len(classes)} classes, {len(selected)} heavy atoms selected:")
        for idx, label in selected:
            cls = [c for c in classes if idx in c][0]
            equiv_str = ', '.join(f"{syms[c]}{c+1}" for c in cls)
            print(f"  {'':12s}   {label:8s} (idx={idx:2d})  equiv: [{equiv_str}]")

        # Plot
        try:
            plot_fname = os.path.join(PLOT_DIR, f'selected_{mol}.png')
            plot_molecule(syms, ps, selected, classes, mol, ops_desc, plot_fname)
        except Exception as e:
            print(f"  {'':12s} (plot skipped: {e})")

        all_mols_data.append((mol, syms, ps, selected, classes, ops_desc))

        # Bake GPAW scripts
        for atom_idx, atom_label in selected:
            py = bake_scan_script(mol, syms, ps, atom_idx, atom_label,
                                  args.ecut, args.vacuum, args.z_cell, args.xc, r_grid, spec)
            tag = f"{mol}_atom{atom_idx}_{atom_label}"
            py_path = os.path.join(JOBS_DIR, f'run_{tag}.py')
            with open(py_path, 'w') as f:
                f.write(py)
            os.chmod(py_path, 0o755)

            pbs = bake_pbs(mol, atom_idx, atom_label, spec, args.ecut, args.vacuum, args.z_cell, args.xc)
            with open(os.path.join(JOBS_DIR, f'submit_{tag}.pbs'), 'w') as f:
                f.write(pbs)

            n_scripts += 1

        # Bake PySCF scripts
        if args.pyscf:
            pyscf_spec = MOLECULES_PYSCF.get(mol, spec)
            for atom_idx, atom_label in selected:
                py = bake_pyscf_scan_script(mol, syms, ps, atom_idx, atom_label,
                                            args.basis, args.xc, r_grid, pyscf_spec)
                tag = f"{mol}_atom{atom_idx}_{atom_label}"
                py_path = os.path.join(pyscf_jobs_dir, f'run_{tag}.py')
                with open(py_path, 'w') as f:
                    f.write(py)
                os.chmod(py_path, 0o755)

                pbs = bake_pyscf_pbs(mol, atom_idx, atom_label, pyscf_spec, args.basis, args.xc)
                with open(os.path.join(pyscf_jobs_dir, f'submit_{tag}.pbs'), 'w') as f:
                    f.write(pbs)

                n_pyscf_scripts += 1

    # Overview plot
    try:
        overview_fname = os.path.join(PLOT_DIR, 'selected_overview.png')
        plot_overview(all_mols_data, overview_fname)
    except Exception as e:
        print(f"  (overview plot skipped: {e})")

    # submit_all.sh for GPAW
    submit_script = bake_submit_all(n_scripts)
    submit_path = os.path.join(JOBS_DIR, 'submit_all.sh')
    with open(submit_path, 'w') as f:
        f.write(submit_script)
    os.chmod(submit_path, 0o755)

    # submit_all.sh for PySCF
    if args.pyscf:
        submit_script_pyscf = bake_submit_all(n_pyscf_scripts)
        submit_path_pyscf = os.path.join(pyscf_jobs_dir, 'submit_all.sh')
        with open(submit_path_pyscf, 'w') as f:
            f.write(submit_script_pyscf)
        os.chmod(submit_path_pyscf, 0o755)

    # Summary
    print(f"\n{'='*70}")
    print(f"Generated {n_scripts} GPAW scan scripts + PBS files")
    print(f"Jobs:   {JOBS_DIR}/")
    print(f"Plots:  {PLOT_DIR}/")
    if args.pyscf:
        print(f"Generated {n_pyscf_scripts} PySCF scan scripts + PBS files")
        print(f"PySCF:  {pyscf_jobs_dir}/")
    print(f"{'='*70}")
    print(f"\nSubmit all GPAW:")
    print(f"  cd {JOBS_DIR} && ./submit_all.sh")
    if args.pyscf:
        print(f"\nSubmit all PySCF:")
        print(f"  cd {pyscf_jobs_dir} && ./submit_all.sh")
    print(f"\nSubmit single:")
    print(f"  cd {JOBS_DIR} && qsub submit_<mol>_atom<idx>_<label>.pbs")


if __name__ == '__main__':
    main()
