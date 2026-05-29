#!/usr/bin/env python3
"""
setup_dftb_phonon.py
=====================
Generate DFTB+ input files and phonopy workflow for phonon calculations
of bulk Si or diamond.

This script creates:
  - dftb_in.hsd           : DFTB+ input for force calculation
  - band.conf             : phonopy band structure configuration
  - run_phonopy.sh        : Bash script to run phonopy + DFTB+ workflow

Usage:
  python setup_dftb_phonon.py --material Si --supercell 2 2 2
  python setup_dftb_phonon.py --material diamond --supercell 2 2 2
"""

import argparse
import json
import os
import sys

# Lattice constants (Angstrom) and conventional cell parameters
MATERIALS = {
    "Si": {
        "lattice": 5.431,
        "mass": 28.0855,
        "element": "Si",
        "sk_table": "Si-Si",
    },
    "diamond": {
        "lattice": 3.567,
        "mass": 12.011,
        "element": "C",
        "sk_table": "C-C",
    },
    "C": {
        "lattice": 3.567,
        "mass": 12.011,
        "element": "C",
        "sk_table": "C-C",
    }
}


def load_config(config_path: str = "phonon_config.json"):
    """Load tool and potential paths from config file."""
    default_config = {
        "tools": {
            "dftb_bin": "dftb+",
            "slakos_dir": "",
            "phonopy_bin": "phonopy",
        }
    }
    if os.path.exists(config_path):
        with open(config_path) as f:
            user_config = json.load(f)
        if "tools" in user_config:
            default_config["tools"].update(user_config["tools"])
    return default_config


def outpath(outdir: str, name: str):
    return os.path.join(outdir, name)


def write_text(path: str, text: str, executable: bool = False):
    with open(path, "w") as f:
        f.write(text)
    if executable:
        os.chmod(path, 0o755)


def diamond_fractional_positions(sc: list):
    nx, ny, nz = sc
    base = [
        (0.0, 0.0, 0.0),
        (0.5, 0.5, 0.0),
        (0.5, 0.0, 0.5),
        (0.0, 0.5, 0.5),
        (0.25, 0.25, 0.25),
        (0.75, 0.75, 0.25),
        (0.75, 0.25, 0.75),
        (0.25, 0.75, 0.75),
    ]
    pos = []
    for ix in range(nx):
        for iy in range(ny):
            for iz in range(nz):
                for fx, fy, fz in base:
                    pos.append(((fx + ix) / nx, (fy + iy) / ny, (fz + iz) / nz))
    return pos


def write_dftb_input(prefix: str, material: str, sc: list, outdir: str = ".", config: dict = None):
    """Write DFTB+ input file for force calculation."""
    if config is None:
        config = load_config()
    info = MATERIALS[material]
    elem = info["element"]
    sk_table = info["sk_table"]
    slakos_dir = config["tools"].get("slakos_dir", "")
    
    nx, ny, nz = sc
    a0 = info["lattice"]
    ax = a0 * nx
    ay = a0 * ny
    az = a0 * nz
    
    frac_pos = diamond_fractional_positions(sc)
    natoms = len(frac_pos)
    
    # DFTB+ input
    dftb_in = f"""Geometry = GenFormat {{
  {{
    FractionalCoords = Yes
    ScaledCartesianCoords = No
    Supercell = {{
      {nx} {ny} {nz}
    }}
  }}
  {{
    <{elem}
    {elem}
    {natoms}
    """
    
    for fx, fy, fz in frac_pos:
        dftb_in += f"    {fx:.10f} {fy:.10f} {fz:.10f}\n"
    
    dftb_in += f"""  >}}
}}

Hamiltonian = DFTB {{
  SCC = Yes
  SlaterKosterFiles = Type2FileNames {{
    Prefix = "{slakos_dir}/"
    Separator = "-"
    Suffix = ".skf"
    """
    
    if slakos_dir:
        dftb_in += f"    Directory = \"{slakos_dir}\"\n"
    
    dftb_in += f"""    {{
      {sk_table} = {sk_table}
    }}
  }}
  MaxAngularMomentum {{
    {elem} = p
  }}
  KPointsAndWeights {{
    0.0 0.0 0.0 1.0
  }}
}}

Options {{
  WriteResultsTag = Yes
}}

Analysis {{
  CalculateForces = Yes
}}
"""
    
    fname = outpath(outdir, "dftb_in.hsd")
    write_text(fname, dftb_in)
    print(f"[setup] Wrote DFTB+ input: {fname}")
    return fname


def write_phonopy_band_conf(prefix: str, material: str, sc: list, outdir: str = "."):
    """Write phonopy band.conf for phonon dispersion."""
    nx, ny, nz = sc
    info = MATERIALS[material]
    elem = info["element"]
    mass = info["mass"]
    
    band_conf = f"""DIM = {nx} {ny} {nz}
ATOM_NAME = {elem}
MASS = {mass:.4f}
"""
    
    fname = outpath(outdir, "band.conf")
    write_text(fname, band_conf)
    print(f"[setup] Wrote phonopy band.conf: {fname}")
    return fname


def write_phonopy_script(prefix: str, material: str, sc: list, outdir: str = ".", config: dict = None):
    """Write bash script to run phonopy + DFTB+ workflow."""
    if config is None:
        config = load_config()
    nx, ny, nz = sc
    dftb_bin = config["tools"].get("dftb_bin", "dftb+")
    phonopy_bin = config["tools"].get("phonopy_bin", "phonopy")
    
    script = f"""#!/bin/bash
# Phonopy + DFTB+ phonon calculation workflow
# Material: {material}, Supercell: {nx}x{ny}x{nz}

set -e

DFTB_BIN={dftb_bin}
PHONOPY_BIN={phonopy_bin}

echo "=========================================="
echo "Phonopy + DFTB+ Phonon Workflow for {material}"
echo "=========================================="

# 1. Generate displaced structures with phonopy
echo "[phonopy] Generating displaced structures..."
$PHONOPY_BIN -d --dim="{nx} {ny} {nz}" --dftb+

# 2. Run DFTB+ on each displaced structure
echo "[DFTB+] Running DFTB+ on displaced structures..."
for i in disp-*/; do
  echo "Running DFTB+ in $i"
  cd "$i"
  $DFTB_BIN > dftb.log
  cd ..
done

# 3. Collect forces with phonopy
echo "[phonopy] Collecting forces..."
$PHONOPY_BIN -f disp-*/results.tag --dftb+

# 4. Compute phonon band structure
echo "[phonopy] Computing phonon band structure..."
$PHONOPY_BIN -p band.conf --dim="{nx} {ny} {nz}" --dftb+

echo "Done. Output in band.yaml and band.dat"
"""
    
    fname = outpath(outdir, "run_phonopy.sh")
    write_text(fname, script, executable=True)
    print(f"[setup] Wrote {fname}")
    return fname


def main():
    parser = argparse.ArgumentParser(
        description="Generate DFTB+ + phonopy input files for phonon calculations"
    )
    parser.add_argument("--material", choices=["Si", "diamond", "C"], default="Si",
                        help="Material to simulate")
    parser.add_argument("--supercell", nargs=3, type=int, default=[2, 2, 2],
                        help="Supercell dimensions (default: 2 2 2)")
    parser.add_argument("--prefix", default=None,
                        help="Output file prefix (default: material_sc)")
    parser.add_argument("--outdir", default=".",
                        help="Output directory (default: current directory)")
    parser.add_argument("--config", default="phonon_config.json",
                        help="Path to config file with tool paths")
    args = parser.parse_args()
    
    config = load_config(args.config)
    
    mat = args.material
    if mat == "C":
        mat = "diamond"
    sc = args.supercell
    
    if args.prefix:
        prefix = args.prefix
    else:
        prefix = f"{mat}_{sc[0]}x{sc[1]}x{sc[2]}"
    
    print(f"\n[setup] Setting up DFTB+ + phonopy files for {mat}")
    print(f"[setup] Supercell: {sc[0]}x{sc[1]}x{sc[2]}, prefix: {prefix}\n")
    
    os.makedirs(args.outdir, exist_ok=True)
    write_dftb_input(prefix, mat, sc, args.outdir, config)
    write_phonopy_band_conf(prefix, mat, sc, args.outdir)
    write_phonopy_script(prefix, mat, sc, args.outdir, config)
    
    print(f"\n[setup] All files generated.")
    print(f"[setup] Run '{os.path.join(args.outdir, 'run_phonopy.sh')}' to start the workflow.")


if __name__ == "__main__":
    main()
