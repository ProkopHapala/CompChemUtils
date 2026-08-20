#!/usr/bin/env python3
"""Generate XYZ files for binary hydrides using geom_engine.make_hydride().
Usage: python make_hydrides.py [--outdir data/xyz] [--names H2O NH3 CH4 ...]
"""
import os, sys, argparse
import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)
from py.geom_engine import make_hydride, HYDRIDE_PARAMS

def write_xyz(path, syms, ps):
    with open(path, 'w') as f:
        f.write(f"{len(syms)}\n\n")
        for s, p in zip(syms, ps):
            f.write(f"{s:2s}  {p[0]:.6f}  {p[1]:.6f}  {p[2]:.6f}\n")

def main():
    parser = argparse.ArgumentParser(description="Generate binary hydride XYZ files")
    parser.add_argument('--outdir', default=os.path.join(REPO, 'data', 'xyz'))
    parser.add_argument('--names', nargs='+', default=list(HYDRIDE_PARAMS.keys()))
    args = parser.parse_args()
    os.makedirs(args.outdir, exist_ok=True)
    for name in args.names:
        p = HYDRIDE_PARAMS[name]
        syms, ps = make_hydride(p['el'], p['nH'], p['r'], p['angle'])
        path = os.path.join(args.outdir, f"{name}.xyz")
        write_xyz(path, syms, ps)
        # Verify bond lengths and angles
        r_actual = np.linalg.norm(ps[1] - ps[0])
        if p['nH'] >= 2:
            v1 = ps[1] - ps[0]; v2 = ps[2] - ps[0]
            ang = np.degrees(np.arccos(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))))
        else:
            ang = 0
        print(f"  {name:6s}: r={r_actual:.4f} Å, angle={ang:.2f}° → {path}")

if __name__ == '__main__':
    main()
