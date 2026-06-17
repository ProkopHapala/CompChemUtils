#!/usr/bin/env python3
"""
replicate_xyz.py — replicate an XYZ structure in XY using AtomicSystem.clonePBC.

Usage:
    python replicate_xyz.py input.xyz output.xyz --replicate 2 2
"""

import os
import sys
import argparse

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from py.AtomicSystem import AtomicSystem


def replicate_xyz(infile, outfile, nx=1, ny=1):
    mol = AtomicSystem(fname=infile)
    if nx > 1 or ny > 1:
        mol = mol.clonePBC(nPBC=(nx, ny, 1))
    mol.saveXYZ(outfile, comment=f"replicated_{nx}x{ny}")
    print(f"Wrote {outfile}  replicate=({nx},{ny})  natoms={mol.natoms}")


def main():
    parser = argparse.ArgumentParser(description='Replicate XYZ in XY plane')
    parser.add_argument('input', help='Input XYZ file')
    parser.add_argument('output', help='Output XYZ file')
    parser.add_argument('--replicate', type=int, nargs=2, default=[2, 2], help='nx ny replication')
    args = parser.parse_args()
    replicate_xyz(args.input, args.output, nx=args.replicate[0], ny=args.replicate[1])


if __name__ == '__main__':
    main()
