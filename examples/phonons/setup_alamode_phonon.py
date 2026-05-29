#!/usr/bin/env python3
"""
setup_alamode_phonon.py
========================
Generate ALAMODE input files and a LAMMPS structure file for
phonon calculations of bulk Si or diamond.

This script creates:
  - <prefix>.lammps          : LAMMPS structure file (relaxed cell)
  - <prefix>.alamode.in      : ALAMODE input template for displace.py
  - run_displace.sh          : Bash script to run displace.py + LAMMPS
  - run_extract.sh           : Bash script to extract forces with ALAMODE
  - run_alamode.sh           : Master script for the full workflow

Usage:
  python setup_alamode_phonon.py --material Si --potential sw --supercell 2 2 2
  python setup_alamode_phonon.py --material diamond --potential tersoff --supercell 2 2 2
  python setup_alamode_phonon.py --material Si --potential mtp --mtp-file Si_diamond.mtp --supercell 2 2 2
"""

import argparse
import json
import os
import sys

# Lattice constants (Angstrom) and conventional cell parameters
MATERIALS = {
    "Si": {
        "lattice": 5.431,           # Cubic diamond, conventional cell
        "mass": 28.0855,
        "element": "Si",
        "type_id": 1,
    },
    "diamond": {
        "lattice": 3.567,
        "mass": 12.011,
        "element": "C",
        "type_id": 1,
    },
    "C": {
        "lattice": 3.567,
        "mass": 12.011,
        "element": "C",
        "type_id": 1,
    }
}

# LAMMPS potential file mapping (built-in or user-provided)
POTENTIALS = {
    "sw": {
        "Si": "Si.sw",
        "C": None,  # SW not available for C in standard LAMMPS
    },
    "tersoff": {
        "Si": "SiCGe.tersoff",
        "C": "C.tersoff",
    },
    "meam": {
        "Si": "Si.meam",
        "C": None,
    },
    "mtp": {
        "Si": None,  # User must provide
        "C": None,
    }
}


def load_config(config_path: str = "phonon_config.json"):
    """Load tool and potential paths from config file."""
    default_config = {
        "tools": {
            "lammps_bin": "lmp_serial",
            "dftb_bin": "dftb+",
            "slakos_dir": "",
            "phonopy_bin": "phonopy",
            "alamode_displace": "displace.py",
            "alamode_extract": "extract.py",
            "alamode_alm": "alm",
            "alamode_anphon": "anphon"
        },
        "potentials": {
            "si_sw": "Si.sw",
            "si_tersoff": "SiCGe.tersoff",
            "c_tersoff": "C.tersoff"
        }
    }
    if os.path.exists(config_path):
        with open(config_path) as f:
            user_config = json.load(f)
        for key in ["tools", "potentials"]:
            if key in user_config:
                default_config[key].update(user_config[key])
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


def write_lammps_structure(prefix: str, material: str, sc: list, outdir: str = "."):
    """Write a LAMMPS data file for a diamond-cubic supercell."""
    info = MATERIALS[material]
    a0 = info["lattice"]
    mass = info["mass"]
    elem = info["element"]
    type_id = info["type_id"]

    nx, ny, nz = sc
    # Primitive cell vectors for diamond cubic (primitive, 2 atoms)
    # Conventional cell is cubic with 8 atoms.
    # We build conventional cell and replicate.
    ax = a0 * nx
    ay = a0 * ny
    az = a0 * nz

    frac_pos = diamond_fractional_positions(sc)
    natoms = len(frac_pos)

    lines = []
    lines.append(f"# {elem} supercell {nx}x{ny}x{nz}")
    lines.append(f"{natoms} atoms")
    lines.append("1 atom types")
    lines.append(f"0.0 {ax:.6f} xlo xhi")
    lines.append(f"0.0 {ay:.6f} ylo yhi")
    lines.append(f"0.0 {az:.6f} zlo zhi")
    lines.append("")
    lines.append("Masses")
    lines.append("")
    lines.append(f"1 {mass:.4f}")
    lines.append("")
    lines.append("Atoms")
    lines.append("")

    atom_id = 1
    for fx, fy, fz in frac_pos:
        lines.append(f"{atom_id} {type_id} {fx * ax:.6f} {fy * ay:.6f} {fz * az:.6f}")
        atom_id += 1

    fname = outpath(outdir, f"{prefix}.lammps")
    write_text(fname, "\n".join(lines))
    print(f"[setup] Wrote LAMMPS structure: {fname} ({natoms} atoms)")
    return fname


def write_lammps_input(prefix: str, material: str, potential: str, mtp_file: str = None, outdir: str = ".", config: dict = None):
    """Write a LAMMPS input script template for force calculation."""
    if config is None:
        config = load_config()
    info = MATERIALS[material]
    elem = info["element"]
    pot_paths = config["potentials"]

    lines = []
    lines.append("# LAMMPS input for force calculation (ALAMODE displacement)")
    lines.append("units           metal")
    lines.append("atom_style      atomic")
    lines.append(f"variable        datafile string {prefix}.lammps")
    lines.append(f"variable        case string {prefix}")
    lines.append("read_data       ${datafile}")
    lines.append("")

    if potential == "sw":
        if elem != "Si":
            print("WARNING: Stillinger-Weber is only standard for Si.")
        pot_file = pot_paths.get("si_sw", "Si.sw")
        lines.append("pair_style      sw")
        lines.append(f"pair_coeff      * * {pot_file} Si")
    elif potential == "tersoff":
        lines.append("pair_style      tersoff")
        if elem == "Si":
            pot_file = pot_paths.get("si_tersoff", "SiCGe.tersoff")
            lines.append(f"pair_coeff      * * {pot_file} Si")
        elif elem == "C":
            pot_file = pot_paths.get("c_tersoff", "C.tersoff")
            lines.append(f"pair_coeff      * * {pot_file} C")
    elif potential == "meam":
        lines.append("pair_style      meam")
        lines.append("pair_coeff      * * library.meam Si_2.meam.spline Si")
    elif potential == "mtp":
        if not mtp_file:
            print("ERROR: --mtp-file required for MTP potential")
            sys.exit(1)
        lines.append("pair_style      mlip mlip.ini")
        lines.append(f"pair_coeff      * * {mtp_file}")
    else:
        print(f"ERROR: Unknown potential {potential}")
        sys.exit(1)

    lines.append("")
    lines.append("neighbor        0.3 bin")
    lines.append("neigh_modify    delay 0")
    lines.append("")
    lines.append("timestep        0.001")
    lines.append("run             0")
    lines.append("")
    lines.append("# Dump forces in ALAMODE-compatible format")
    lines.append("dump            1 all custom 1 dump.${case}.force id type fx fy fz")
    lines.append('dump_modify     1 format line "%d %d %.10f %.10f %.10f"')
    lines.append("run             0")
    lines.append("")
    lines.append("# Alternatively, use 'fix phonon' for correlation method")
    lines.append("# fix             2 all phonon ...")

    fname = outpath(outdir, f"{prefix}_force.in")
    write_text(fname, "\n".join(lines))
    print(f"[setup] Wrote LAMMPS input: {fname}")
    return fname


def write_alamode_scripts(prefix: str, material: str, potential: str, sc: list, outdir: str = ".", config: dict = None):
    """Write bash scripts to run ALAMODE workflow."""
    if config is None:
        config = load_config()
    nx, ny, nz = sc
    lammps_bin = config["tools"].get("lammps_bin", "lmp")

    # Script 1: Generate displacements
    displace_sh = f"""#!/bin/bash
# Step 1: Generate harmonic displacement patterns with ALAMODE
# Requires: ALAMODE installed and displace.py in PATH

PREFIX={prefix}
SUPERCELL="{nx} {ny} {nz}"

echo "[ALAMODE] Creating displacement patterns for {material} ..."

command -v displace.py >/dev/null
python $(which displace.py) --LAMMPS=${{PREFIX}}.lammps \
    --mag=0.01 --prefix=harm

# For anharmonic (3rd order) patterns, uncomment:
# python $(which displace.py) --LAMMPS=${{PREFIX}}.lammps \
#     --mag=0.04 --prefix=cubic

echo "[ALAMODE] Displaced structures written to harm*.xsf"
echo "Next: Convert to LAMMPS format and run force calculations."
"""
    write_text(outpath(outdir, "run_displace.sh"), displace_sh, executable=True)
    print(f"[setup] Wrote {outpath(outdir, 'run_displace.sh')}")

    lammps_sh = f"""#!/bin/bash
set -e

PREFIX={prefix}
LAMMPS_BIN=${{LAMMPS_BIN:-{lammps_bin}}}

command -v "${{LAMMPS_BIN}}" >/dev/null
shopt -s nullglob
inputs=(harm*.lammps)
if [ ${{#inputs[@]}} -eq 0 ]; then
  inputs=(harm*.LAMMPS)
fi
if [ ${{#inputs[@]}} -eq 0 ]; then
  echo "ERROR: no harm*.lammps displaced structures found. Run ./run_displace.sh first or convert ALAMODE output to LAMMPS data files."
  exit 1
fi

for data in "${{inputs[@]}}"; do
  case_name=${{data%.lammps}}
  case_name=${{case_name%.LAMMPS}}
  echo "[LAMMPS] ${{data}} -> dump.${{case_name}}.force"
  "${{LAMMPS_BIN}}" -var datafile "${{data}}" -var case "${{case_name}}" -in "${{PREFIX}}_force.in" > "log.${{case_name}}.lammps"
done
"""
    write_text(outpath(outdir, "run_lammps_forces.sh"), lammps_sh, executable=True)
    print(f"[setup] Wrote {outpath(outdir, 'run_lammps_forces.sh')}")

    extract_sh = f"""#!/bin/bash
set -e
PREFIX={prefix}

echo "[ALAMODE] Extracting displacement-force dataset ..."
command -v extract.py >/dev/null
shopt -s nullglob
forces=(dump.harm*.force)
if [ ${{#forces[@]}} -eq 0 ]; then
  echo "ERROR: no dump.harm*.force files found. Run ./run_lammps_forces.sh first."
  exit 1
fi

python $(which extract.py) --LAMMPS=${{PREFIX}}.lammps "${{forces[@]}}" > DFSET_harmonic
echo "[ALAMODE] Wrote DFSET_harmonic"
"""
    write_text(outpath(outdir, "run_extract.sh"), extract_sh, executable=True)
    print(f"[setup] Wrote {outpath(outdir, 'run_extract.sh')}")

    master_sh = f"""#!/bin/bash
# Master script for ALAMODE + LAMMPS phonon calculation
# Material: {material}, Potential: {potential}, Supercell: {nx}x{ny}x{nz}

set -e

echo "=========================================="
echo "ALAMODE Phonon Workflow for {material}"
echo "=========================================="

# 1. Generate displacements
bash run_displace.sh

# 2. Run LAMMPS on displaced structures, then extract forces
# bash run_lammps_forces.sh
# bash run_extract.sh

# 3. Compute force constants with ALM
# alm {prefix}.alamode.in > alm.log

# 4. Compute phonon dispersion with anphon
# anphon {prefix}.anphon.in > anphon.log

echo "Setup complete. Next steps:"
echo "  1. Check generated harm*.lammps files"
echo "  2. Run ./run_lammps_forces.sh"
echo "  3. Run ./run_extract.sh"
echo "  4. Run alm {prefix}.alamode.in"
echo "  5. Run anphon {prefix}.anphon.in"
"""
    write_text(outpath(outdir, "run_alamode.sh"), master_sh, executable=True)
    print(f"[setup] Wrote {outpath(outdir, 'run_alamode.sh')}")


def write_alamode_input(prefix: str, material: str, sc: list, outdir: str = "."):
    """Write ALAMODE input file templates for alm and anphon."""
    nx, ny, nz = sc
    info = MATERIALS[material]
    elem = info["element"]
    pos_lines = "\n".join(f"  1 {fx:.10f} {fy:.10f} {fz:.10f}" for fx, fy, fz in diamond_fractional_positions(sc))

    # ALM input (force constant solver)
    alm_in = f"""&general
  PREFIX = {prefix}
  MODE = optimize
  NAT = {8 * nx * ny * nz}
  NKD = 1
  KD = {elem}
/

&interaction
  NORDER = 1
/

&cell
  {nx * info["lattice"]:.4f} 0.0 0.0
  0.0 {ny * info["lattice"]:.4f} 0.0
  0.0 0.0 {nz * info["lattice"]:.4f}
/

&position
{pos_lines}
/

&cutoff
  {elem}-{elem} 6.0
/

&data
  DFSET = DFSET_harmonic
/
"""
    write_text(outpath(outdir, f"{prefix}.alamode.in"), alm_in)
    print(f"[setup] Wrote ALAMODE input: {outpath(outdir, f'{prefix}.alamode.in')}")

    # Anphon input (phonon calculator)
    anphon_in = f"""&general
  PREFIX = {prefix}
  MODE = phonons
  FCSXML = {prefix}.xml
  NKD = 1
  KD = {elem}
  MASS = {info["mass"]:.4f}
/

&cell
  {nx * info["lattice"]:.4f} 0.0 0.0
  0.0 {ny * info["lattice"]:.4f} 0.0
  0.0 0.0 {nz * info["lattice"]:.4f}
/

&position
{pos_lines}
/

&kpoint
  1
  G 0.0 0.0 0.0 101
  X 0.5 0.0 0.5 101
  K 0.375 0.375 0.75 101
  G 0.0 0.0 0.0 101
  L 0.5 0.5 0.5 101
/
"""
    write_text(outpath(outdir, f"{prefix}.anphon.in"), anphon_in)
    print(f"[setup] Wrote anphon input: {outpath(outdir, f'{prefix}.anphon.in')}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate ALAMODE + LAMMPS input files for phonon calculations"
    )
    parser.add_argument("--material", choices=["Si", "diamond", "C"], default="Si",
                        help="Material to simulate")
    parser.add_argument("--potential", choices=["sw", "tersoff", "meam", "mtp"],
                        default="tersoff", help="LAMMPS interatomic potential")
    parser.add_argument("--mtp-file", default=None,
                        help="Path to MTP file (required if potential=mtp)")
    parser.add_argument("--supercell", nargs=3, type=int, default=[2, 2, 2],
                        help="Supercell dimensions (default: 2 2 2)")
    parser.add_argument("--prefix", default=None,
                        help="Output file prefix (default: material_potential_sc)")
    parser.add_argument("--outdir", default=".",
                        help="Output directory (default: current directory)")
    parser.add_argument("--config", default="phonon_config.json",
                        help="Path to config file with tool paths")
    args = parser.parse_args()

    config = load_config(args.config)

    mat = args.material
    if mat == "C":
        mat = "diamond"
    pot = args.potential
    sc = args.supercell
    elem = MATERIALS[mat]["element"]

    if POTENTIALS[pot].get(elem) is None and pot != "mtp":
        print(f"ERROR: potential '{pot}' is not configured for element '{elem}'")
        sys.exit(1)
    if pot == "mtp" and not args.mtp_file:
        print("ERROR: --mtp-file required for MTP potential")
        sys.exit(1)

    if args.prefix:
        prefix = args.prefix
    else:
        prefix = f"{mat}_{pot}_{sc[0]}x{sc[1]}x{sc[2]}"

    print(f"\n[setup] Setting up ALAMODE files for {mat} with {pot} potential")
    print(f"[setup] Supercell: {sc[0]}x{sc[1]}x{sc[2]}, prefix: {prefix}\n")

    os.makedirs(args.outdir, exist_ok=True)
    write_lammps_structure(prefix, mat, sc, args.outdir)
    write_lammps_input(prefix, mat, pot, args.mtp_file, args.outdir, config)
    write_alamode_input(prefix, mat, sc, args.outdir)
    write_alamode_scripts(prefix, mat, pot, sc, args.outdir, config)

    print(f"\n[setup] All files generated with prefix '{prefix}'.")
    print(f"[setup] Run '{os.path.join(args.outdir, 'run_alamode.sh')}' to see the workflow steps.")


if __name__ == "__main__":
    main()
