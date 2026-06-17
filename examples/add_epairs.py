#!/usr/bin/env python3
"""
add_epairs.py — add electron-pair (E) dummy atoms to N and O atoms in an XYZ file.

Uses AtomicSystem.neighs() + AtomicSystem.add_electron_pairs().

Usage:
    python add_epairs.py input.xyz output.xyz
    python add_epairs.py data/xyz/HCN.xyz data/xyz/HCN_ep.xyz
"""

import os
import sys
import argparse

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from py.AtomicSystem import AtomicSystem


def add_epairs(infile, outfile):
    mol = AtomicSystem(fname=infile)
    mol.neighs(bBond=True)
    mol.add_electron_pairs()
    mol.qs = None
    mol.Rs = None
    mol.saveXYZ(outfile, bQs=False)
    n_ep = sum(1 for e in mol.enames if e == 'E')
    print(f"Wrote {outfile}  natoms={mol.natoms}  n_epairs={n_ep}")


def main():
    parser = argparse.ArgumentParser(description='Add electron-pair dummy atoms (E) to N/O atoms')
    parser.add_argument('input', help='Input XYZ file')
    parser.add_argument('output', help='Output XYZ file')
    args = parser.parse_args()
    add_epairs(args.input, args.output)


if __name__ == '__main__':
    main()
