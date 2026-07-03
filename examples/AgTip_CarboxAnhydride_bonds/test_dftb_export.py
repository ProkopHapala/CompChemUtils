#!/usr/bin/env python3
"""Debug script: test DFTB+ export mode for molecule+Au4 cluster.

Exports a DFTB+ relaxation input (dftb_in.hsd) without running DFTB+,
to inspect generated input files and diagnose Slater-Koster parameter
issues. Loads H2O_ep + Au4 cluster geometry, calls DFTBPlusBackend.export_relax(),
and prints all generated files.

Usage:
    python test_dftb_export.py
"""

import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from py import atomicUtils as au
from py.AtomicSystem import AtomicSystem
from py.interfaces.dftbplus import DFTBPlusBackend

# Load H2O_ep + Au4 cluster
frames = au.load_xyz_movie('tmp/cluster_apex_au/H2O_ep_cluster_attach_orients.xyz')
es, apos, qs, Rs, comment = frames[0]

mol = AtomicSystem()
mol.apos = apos
mol.enames = list(es)
mol.qs = None
mol.Rs = None
mol.natoms = len(es)

print(f"natoms={mol.natoms}  es={set(es)}")

backend = DFTBPlusBackend(sk_path='/home/prokop/SIMULATIONS/dftbplus/slakos/auorg/auorg-1-1', method=None, temperature=300.0)

# Export instead of run
outdir = 'tmp/dftb_test_export'
os.makedirs(outdir, exist_ok=True)
files = backend.export_relax(mol, method=None, outdir=outdir)
print(f"Exported files: {files}")

# Check what was written
for f in files:
    print(f"\n=== {f} ===")
    with open(f) as fh:
        print(fh.read())
