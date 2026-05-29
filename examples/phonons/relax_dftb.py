#!/usr/bin/env python3
"""
relax_dftb.py
===============
Find equilibrium lattice constant using DFTB+ by scanning volumes,
then write relaxed structure for phonon calculation.

Usage:
  python relax_dftb.py --material Si --config phonon_config.json
  python relax_dftb.py --material diamond --config phonon_config.json
"""

import argparse
import json
import os
import re
import subprocess
import sys

import numpy as np

MATERIALS = {
    "Si": {"symbol": "Si", "mass": 28.0855, "a0": 5.431, "elem": "Si"},
    "diamond": {"symbol": "C", "mass": 12.011, "a0": 3.567, "elem": "C"},
}


def load_config(config_path):
    default = {"tools": {"dftb_bin": "dftb+", "slakos_dir": ""}}
    if os.path.exists(config_path):
        with open(config_path) as f:
            user = json.load(f)
        if "tools" in user:
            default["tools"].update(user["tools"])
    return default


def write_dftb_input(outdir, elem, a, slakos_dir):
    """Write DFTB+ input for cubic lattice constant scan."""
    os.makedirs(outdir, exist_ok=True)

    hsd = "Geometry = GenFormat {\n"
    hsd += "  {\n"
    hsd += "    <<< 'geometry.gen'\n"
    hsd += "  }\n"
    hsd += "}\n\n"
    hsd += "Hamiltonian = DFTB {\n"
    hsd += "  SCC = Yes\n"
    if slakos_dir:
        hsd += f'  SlaterKosterFiles = Type2FileNames {{\n'
        hsd += f'    Prefix = "{slakos_dir}/"\n'
        hsd += f'    Separator = "-"\n'
        hsd += f'    Suffix = ".skf"\n'
        hsd += f'  }}\n'
    hsd += "  MaxAngularMomentum {\n"
    if elem == "Si":
        hsd += "    Si = p\n"
    elif elem == "C":
        hsd += "    C = p\n"
    hsd += "  }\n"
    hsd += "  KPointsAndWeights {\n"
    hsd += "    0.5 0.5 0.5 1.0\n"  # L-point for better convergence
    hsd += "  }\n"
    hsd += "}\n\n"
    hsd += "Options {\n"
    hsd += "  WriteResultsTag = Yes\n"
    hsd += "}\n"

    with open(os.path.join(outdir, "dftb_in.hsd"), "w") as f:
        f.write(hsd)

    # Write geometry.gen for conventional cubic cell (8 atoms diamond)
    half = a / 2
    q = a / 4
    gen_lines = ["8 S"]
    gen_lines.append(elem)
    positions = [
        [0.0, 0.0, 0.0],
        [half, half, 0.0],
        [half, 0.0, half],
        [0.0, half, half],
        [q, q, q],
        [q + half, q + half, q],
        [q + half, q, q + half],
        [q, q + half, q + half],
    ]
    for i, (x, y, z) in enumerate(positions, 1):
        gen_lines.append(f"{i:4d} 1 {x:18.10f} {y:18.10f} {z:18.10f}")
    gen_lines.append("0.0000000000 0.0000000000 0.0000000000")
    gen_lines.append(f"{a:.10f} 0.0000000000 0.0000000000")
    gen_lines.append(f"0.0000000000 {a:.10f} 0.0000000000")
    gen_lines.append(f"0.0000000000 0.0000000000 {a:.10f}")

    with open(os.path.join(outdir, "geometry.gen"), "w") as f:
        f.write("\n".join(gen_lines) + "\n")


def run_dftb(dftb_bin, outdir):
    try:
        result = subprocess.run(
            [dftb_bin],
            cwd=outdir,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except FileNotFoundError:
        print(f"ERROR: DFTB+ not found: {dftb_bin}")
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print(f"ERROR: DFTB+ timed out")
        sys.exit(1)

    if result.returncode != 0:
        print(f"WARNING: DFTB+ failed in {outdir}")
        return None

    results_path = os.path.join(outdir, "results.tag")
    if not os.path.exists(results_path):
        return None

    with open(results_path) as f:
        text = f.read()

    match = re.search(r'total_energy\s+:real:0:\n\s+([\-0-9]+\.[0-9]+E[\+\-]?[0-9]+)', text)
    if not match:
        return None

    return float(match.group(1))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--material", choices=["Si", "diamond"], required=True)
    parser.add_argument("--config", default="phonon_config.json")
    parser.add_argument("--npoints", type=int, default=11,
                        help="Number of lattice constants to scan")
    parser.add_argument("--strain", type=float, default=0.08,
                        help="Fractional strain range (e.g. 0.08 = +/-8%)")
    args = parser.parse_args()

    config = load_config(args.config)
    dftb_bin = config["tools"].get("dftb_bin", "dftb+")
    slakos_dir = config["tools"].get("slakos_dir", "")

    info = MATERIALS[args.material]
    a0 = info["a0"]
    elem = info["elem"]

    print(f"\n[relax] Scanning lattice constant for {args.material}")
    print(f"[relax] Reference a0 = {a0:.4f} Ang")
    print(f"[relax] Strain range: +/-{args.strain*100:.1f}%")
    print(f"[relax] {args.npoints} points\n")

    strains = np.linspace(-args.strain, args.strain, args.npoints)
    energies = []
    lattice_constants = []

    for i, s in enumerate(strains):
        a = a0 * (1 + s)
        outdir = f"relax_{args.material}_{i:02d}_a{a:.4f}"
        print(f"[relax] {i+1}/{args.npoints}: a = {a:.4f} Ang ...", end=" ")

        write_dftb_input(outdir, elem, a, slakos_dir)
        energy = run_dftb(dftb_bin, outdir)
        if energy is None:
            print("FAILED")
            continue
        print(f"E = {energy:.6f} Ha")
        energies.append(energy)
        lattice_constants.append(a)

    if len(energies) < 3:
        print("ERROR: Not enough successful calculations for fit")
        sys.exit(1)

    # Fit parabola to find minimum
    lattice_constants = np.array(lattice_constants)
    energies = np.array(energies)

    # Fit a*x^2 + b*x + c
    coeffs = np.polyfit(lattice_constants, energies, 2)
    a_opt = -coeffs[1] / (2 * coeffs[0])
    e_opt = np.polyval(coeffs, a_opt)

    print(f"\n[relax] Equilibrium lattice constant: a = {a_opt:.4f} Ang")
    print(f"[relax] Minimum energy: E = {e_opt:.6f} Ha")
    print(f"[relax] Shift from reference: {a_opt - a0:+.4f} Ang ({(a_opt/a0 - 1)*100:+.2f}%)\n")

    # Save results
    with open(f"relax_{args.material}_summary.dat", "w") as f:
        f.write("# a(Ang)  E(Hartree)\n")
        for a, e in zip(lattice_constants, energies):
            f.write(f"{a:.6f}  {e:.10f}\n")
        f.write(f"\n# Equilibrium: a = {a_opt:.6f} Ang, E = {e_opt:.10f} Ha\n")

    print(f"[relax] Saved summary to relax_{args.material}_summary.dat")


if __name__ == "__main__":
    main()
