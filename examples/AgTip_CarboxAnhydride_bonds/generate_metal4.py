#!/usr/bin/env python3
"""
generate_metal4.py — generate M4 tetrahedron cluster from lattice constant.

Usage:
    python generate_metal4.py --metal Ag --output data/xyz/Ag4.xyz
    python generate_metal4.py --metal Au --output data/xyz/Au4.xyz
"""

import os
import sys
import argparse
import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from py.system_specific.MetalTips import lattice_constant


def generate_metal4_tetrahedron(metal='Ag', output=None):
    """Generate M4 tetrahedron cluster from FCC lattice constant.

    For FCC, nearest-neighbor distance = a / sqrt(2).
    Tetrahedron edge length = nearest-neighbor distance.
    """
    a = lattice_constant(metal)
    nn_dist = a / np.sqrt(2)  # nearest-neighbor distance in FCC

    # Tetrahedron geometry: one atom at origin, three forming base
    # Base is equilateral triangle with edge = nn_dist
    # Height of tetrahedron = sqrt(2/3) * edge

    edge = nn_dist
    h = np.sqrt(2.0/3.0) * edge

    # Base triangle in xy plane, centered at (0,0,-h)
    # Triangle vertices at 120° intervals
    r_base = edge / np.sqrt(3)  # distance from center to vertex in equilateral triangle

    # Atom 0: apex at (0, 0, 0)
    # Atoms 1-3: base vertices
    apos = np.array([
        [0.0, 0.0, 0.0],
        [0.0, r_base, -h],
        [r_base * np.sqrt(3)/2, -r_base/2, -h],
        [-r_base * np.sqrt(3)/2, -r_base/2, -h],
    ])

    # Write XYZ
    if output is None:
        output = f"{metal}4.xyz"
    with open(output, 'w') as f:
        f.write("4\n\n")
        for i, pos in enumerate(apos):
            f.write(f"{metal} {pos[0]:.6f} {pos[1]:.6f} {pos[2]:.6f} 0.000000\n")

    print(f"Wrote {output}  a={a:.3f} Å  nn_dist={nn_dist:.3f} Å  edge={edge:.3f} Å")
    return output


def main():
    parser = argparse.ArgumentParser(description='Generate M4 tetrahedron cluster')
    parser.add_argument('--metal', default='Ag', help='Metal symbol (Ag, Au, Cu, etc.)')
    parser.add_argument('--output', default=None, help='Output XYZ file')
    args = parser.parse_args()
    generate_metal4_tetrahedron(metal=args.metal, output=args.output)


if __name__ == '__main__':
    main()
