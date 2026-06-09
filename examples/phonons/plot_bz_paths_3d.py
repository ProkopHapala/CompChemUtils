#!/usr/bin/env python3
"""
plot_bz_paths_3d.py
===================
Visualize k-point paths in the 3D Brillouin zone using matplotlib.

Compares multiple q-path definitions on the same BZ to understand differences.

Usage:
    python plot_bz_paths_3d.py \
        --cell diamond_primitive.cif \
        --path diamond_fcc_path.dat --name "FCC standard" \
        --path mp_diamond_phonon_bands.dat --name "MP reference" \
        --output plots/bz_paths_diamond.png
"""

import argparse
import os
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa


def read_path_dat(path):
    """Read q-points from a .dat file."""
    qpts, labels = [], []
    with open(path) as f:
        next(f)  # skip header
        for line in f:
            parts = line.strip().split()
            if len(parts) < 3:
                continue
            qpts.append([float(parts[0]), float(parts[1]), float(parts[2])])
            labels.append(parts[-1] if len(parts) > 4 and not parts[-1].replace('.','').replace('-','').isdigit() else "")
    return np.array(qpts), labels


def get_reciprocal_lattice(cell):
    """Compute reciprocal lattice vectors (in units of 2pi/Ang)."""
    vol = np.dot(cell[0], np.cross(cell[1], cell[2]))
    recip = np.zeros((3, 3))
    recip[0] = np.cross(cell[1], cell[2]) / vol
    recip[1] = np.cross(cell[2], cell[0]) / vol
    recip[2] = np.cross(cell[0], cell[1]) / vol
    return recip


def qpt_to_cartesian(q_frac, recip):
    """Convert fractional reciprocal coords to Cartesian (1/Ang)."""
    return q_frac[0] * recip[0] + q_frac[1] * recip[1] + q_frac[2] * recip[2]


def get_bz_faces(recip, nmax=1):
    """Get Brillouin zone boundary faces as a list of (vertices, normal)."""
    # Generate reciprocal lattice points
    gpts = []
    for i in range(-nmax, nmax+1):
        for j in range(-nmax, nmax+1):
            for k in range(-nmax, nmax+1):
                if i == 0 and j == 0 and k == 0:
                    continue
                g = i*recip[0] + j*recip[1] + k*recip[2]
                gpts.append(g)
    
    # Find shortest G vectors (first Brillouin zone boundaries)
    glens = [np.linalg.norm(g) for g in gpts]
    gmin = min(glens)
    
    # Bisecting planes for shortest G vectors
    faces = []
    for g, glen in zip(gpts, glens):
        if abs(glen - gmin) < 1e-6:
            # Plane: k · g = |g|^2 / 2
            # Normal = g, point on plane = g/2
            normal = g / np.linalg.norm(g)
            mid = g / 2.0
            faces.append((normal, mid))
    
    return faces


def sample_bz_surface(faces, recip, gmin, n_samples=4000):
    """Sample points on the BZ boundary surface."""
    pts = []
    max_r = 1.5 * np.linalg.norm(recip[0])
    for _ in range(n_samples * 3):
        r = np.random.uniform(-max_r, max_r, 3)
        inside = True
        dists = []
        for normal, mid in faces:
            d = np.dot(r, normal) - np.dot(mid, normal)
            dists.append(abs(d))
            if d > 1e-6:
                inside = False
                break
        if inside and min(dists) < 0.3 * gmin:
            pts.append(r)
    return np.array(pts) if pts else np.zeros((0, 3))


def plot_bz_paths(cell, paths_data, output, title="Brillouin Zone K-paths"):
    """Plot BZ with multiple k-paths overlaid.
    
    paths_data: list of dicts with 'qpts', 'labels', 'name', 'color'
    """
    recip = get_reciprocal_lattice(cell)
    
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection='3d')
    
    # Plot BZ boundary (approximate with scatter)
    faces = get_bz_faces(recip)
    gmin = min(np.linalg.norm(f[1]) for f in faces) * 2
    
    # Sample surface points
    surf_pts = sample_bz_surface(faces, recip, gmin)
    if len(surf_pts) > 0:
        ax.scatter(surf_pts[:, 0], surf_pts[:, 1], surf_pts[:, 2],
                   c='lightgray', s=1, alpha=0.3)
    
    # Plot reciprocal lattice vectors
    origin = np.zeros(3)
    for i, b in enumerate(recip):
        ax.quiver(*origin, *b, color='red', arrow_length_ratio=0.1, lw=1.5)
        ax.text(b[0]*1.1, b[1]*1.1, b[2]*1.1, f"b{i+1}", color='red', fontsize=10)
    
    # Plot each path
    for pdata in paths_data:
        qpts_frac = pdata['qpts']
        qpts_cart = np.array([qpt_to_cartesian(q, recip) for q in qpts_frac])
        color = pdata.get('color', 'blue')
        name = pdata['name']
        
        ax.plot(qpts_cart[:, 0], qpts_cart[:, 1], qpts_cart[:, 2],
                color=color, lw=2, label=name, alpha=0.8)
        
        # Mark labeled points
        labels = pdata.get('labels', [])
        seen = set()
        for q_cart, lab in zip(qpts_cart, labels):
            if lab and lab not in seen:
                ax.scatter(*q_cart, color=color, s=50, zorder=5)
                ax.text(q_cart[0]*1.05, q_cart[1]*1.05, q_cart[2]*1.05,
                        lab, color=color, fontsize=8, fontweight='bold')
                seen.add(lab)
    
    ax.set_xlabel('kx (1/Ang)')
    ax.set_ylabel('ky (1/Ang)')
    ax.set_zlabel('kz (1/Ang)')
    ax.set_title(title, fontsize=12)
    ax.legend(loc='upper left')
    
    # Equal aspect ratio
    max_range = 0.8 * np.linalg.norm(recip[0])
    ax.set_xlim(-max_range, max_range)
    ax.set_ylim(-max_range, max_range)
    ax.set_zlim(-max_range, max_range)
    
    plt.tight_layout()
    os.makedirs(os.path.dirname(output) if os.path.dirname(output) else ".", exist_ok=True)
    plt.savefig(output, dpi=300)
    print(f"[plot] Saved {output}")
    plt.close()


def main():
    parser = argparse.ArgumentParser(description="Plot k-point paths in 3D BZ")
    parser.add_argument("--cell", required=True, help="Structure file (.cif or .xyz)")
    parser.add_argument("--path", action="append", required=True, help="Q-path .dat file")
    parser.add_argument("--name", action="append", help="Label for each --path")
    parser.add_argument("--title", default=None, help="Plot title")
    parser.add_argument("--output", required=True, help="Output PNG path")
    args = parser.parse_args()
    
    # Read cell
    # Use ASE for CIF, custom for XYZ
    ext = Path(args.cell).suffix.lower()
    if ext == '.cif':
        from ase.io import read
        atoms = read(args.cell)
        cell = atoms.cell.array
    elif ext == '.xyz':
        from phonon_utils import read_structure
        positions, cell, symbols = read_structure(args.cell)
        cell = np.array(cell)
    else:
        print(f"ERROR: unsupported format {ext}")
        sys.exit(1)
    
    paths_data = []
    colors = ['tab:blue', 'tab:orange', 'tab:green', 'tab:red', 'tab:purple']
    for i, ppath in enumerate(args.path):
        if not os.path.exists(ppath):
            print(f"WARNING: {ppath} not found")
            continue
        qpts, labels = read_path_dat(ppath)
        name = args.name[i] if args.name and i < len(args.name) else Path(ppath).stem
        paths_data.append({
            'qpts': qpts,
            'labels': labels,
            'name': name,
            'color': colors[i % len(colors)],
        })
        print(f"[load] {name}: {len(qpts)} q-points")
    
    title = args.title or f"BZ K-paths: {Path(args.cell).name}"
    plot_bz_paths(cell, paths_data, args.output, title=title)


if __name__ == "__main__":
    main()
