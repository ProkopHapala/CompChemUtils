#!/usr/bin/env python3
"""
Headless test for SequencePlacer: place PTCDA and pentacene on NaCl step edge.
Produces .xyz files for verification.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from pyBall.SequencePlacer import run_headless

# Paths to trial molecules
MOL_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'cpp', 'common_resources', 'xyz')
PTCDA     = os.path.join(MOL_DIR, 'PTCDA.xyz')
PENTACENE = os.path.join(MOL_DIR, 'pentacene.xyz')

assert os.path.exists(PTCDA),     f"Not found: {PTCDA}"
assert os.path.exists(PENTACENE), f"Not found: {PENTACENE}"

OUT_DIR = os.path.join(os.path.dirname(__file__), 'out_sequence_placer')
os.makedirs(OUT_DIR, exist_ok=True)

print("=== Test 1: Row of PTCDA (AAAA) on NaCl step, row along x ===")
run_headless(
    mol_files={'A': PTCDA},
    sequence="AAAA",
    nx=20, ny=8, nz=3, nsteps=1,
    row_angle=0.0, row_spacing=14.0, mol_height=3.0,
    origin_x=5.0, origin_y=10.0,
    out_combined=os.path.join(OUT_DIR, 'test1_PTCDA_row.xyz'),
    out_mols=os.path.join(OUT_DIR, 'test1_PTCDA_mols.xyz'),
)

print("\n=== Test 2: Alternating PTCDA+pentacene (ABAB) on NaCl step, row at 45 deg ===")
run_headless(
    mol_files={'A': PTCDA, 'B': PENTACENE},
    sequence="ABAB",
    nx=20, ny=12, nz=3, nsteps=1,
    row_angle=45.0, row_spacing=15.0, mol_height=3.0,
    origin_x=5.0, origin_y=5.0,
    rx=90.0,   # tilt molecules upright
    out_combined=os.path.join(OUT_DIR, 'test2_ABAB_45deg.xyz'),
    out_mols=os.path.join(OUT_DIR, 'test2_ABAB_mols.xyz'),
)

print("\n=== Test 3: Pentacene row (BBB) on flat NaCl (no step), row along y ===")
run_headless(
    mol_files={'B': PENTACENE},
    sequence="BBB",
    nx=10, ny=15, nz=3, nsteps=1,
    row_angle=90.0, row_spacing=12.0, mol_height=2.5,
    origin_x=10.0, origin_y=2.0,
    out_combined=os.path.join(OUT_DIR, 'test3_pentacene_y.xyz'),
    out_mols=os.path.join(OUT_DIR, 'test3_pentacene_mols.xyz'),
)

print("\n=== All tests passed! Output in:", OUT_DIR, "===")
