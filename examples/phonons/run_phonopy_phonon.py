#!/usr/bin/env python3
"""
run_phonopy_phonon.py
=====================
Compute phonon band structures for bulk Si and diamond using phonopy
with DFTB+ or LAMMPS as the force calculator.

Usage:
  python run_phonopy_phonon.py --material Si --calculator dftb+ --supercell 2 2 2
  python run_phonopy_phonon.py --material Si --calculator lammps --potential sw --supercell 2 2 2
  python run_phonopy_phonon.py --material diamond --calculator lammps --potential tersoff --supercell 2 2 2
"""

import argparse
import json
import os
import re
import subprocess
import sys

import numpy as np

# Try to import phonopy
try:
    from phonopy import Phonopy
    from phonopy.structure.atoms import PhonopyAtoms
    from phonopy.interface.calculator import get_default_displacement_distance, write_crystal_structure
except ImportError:
    print("ERROR: phonopy not installed. Run: pip install phonopy")
    sys.exit(1)

# ------------------------------------------------------------------
# Material data (conventional cubic cells)
# ------------------------------------------------------------------
MATERIALS = {
    "Si": {
        "symbol": "Si",
        "mass": 28.0855,
        "lattice": 5.431,  # cubic diamond, conventional
        "cell": [
            [5.431, 0.0, 0.0],
            [0.0, 5.431, 0.0],
            [0.0, 0.0, 5.431],
        ],
        "scaled_positions": [
            [0.0, 0.0, 0.0],
            [0.5, 0.5, 0.0],
            [0.5, 0.0, 0.5],
            [0.0, 0.5, 0.5],
            [0.25, 0.25, 0.25],
            [0.75, 0.75, 0.25],
            [0.75, 0.25, 0.75],
            [0.25, 0.75, 0.75],
        ],
    },
    "diamond": {
        "symbol": "C",
        "mass": 12.011,
        "lattice": 3.567,
        "cell": [
            [3.567, 0.0, 0.0],
            [0.0, 3.567, 0.0],
            [0.0, 0.0, 3.567],
        ],
        "scaled_positions": [
            [0.0, 0.0, 0.0],
            [0.5, 0.5, 0.0],
            [0.5, 0.0, 0.5],
            [0.0, 0.5, 0.5],
            [0.25, 0.25, 0.25],
            [0.75, 0.75, 0.25],
            [0.75, 0.25, 0.75],
            [0.25, 0.75, 0.75],
        ],
    },
}

# MEAM library element names in standard LAMMPS library.meam
MEAM_LIB_NAMES = {"Si": "SiS", "C": None}


def load_config(config_path: str = "phonon_config.json"):
    default = {
        "tools": {
            "lammps_bin": "lmp_serial",
            "dftb_bin": "dftb+",
            "slakos_dir": "",
        },
        "potentials": {},
    }
    if os.path.exists(config_path):
        with open(config_path) as f:
            user = json.load(f)
        for key in ["tools", "potentials"]:
            if key in user:
                default[key].update(user[key])
    return default


# ------------------------------------------------------------------
# Structure helpers
# ------------------------------------------------------------------
def make_conventional_atoms(material: str, lattice: float = None):
    info = MATERIALS[material]
    cell = info["cell"]
    if lattice is not None:
        # Scale conventional cubic cell to new lattice constant
        a0 = info["lattice"]
        scale = lattice / a0
        cell = [[v * scale for v in row] for row in cell]
    return PhonopyAtoms(
        symbols=[info["symbol"]] * len(info["scaled_positions"]),
        cell=cell,
        scaled_positions=info["scaled_positions"],
        masses=[info["mass"]] * len(info["scaled_positions"]),
    )


# ------------------------------------------------------------------
# DFTB+ force calculation
# ------------------------------------------------------------------
def run_dftb_forces(positions, cell, symbols, outdir, config):
    """Run DFTB+ single point and return forces (eV/Angstrom)."""
    dftb_bin = config["tools"].get("dftb_bin", "dftb+")
    slakos_dir = config["tools"].get("slakos_dir", "")

    os.makedirs(outdir, exist_ok=True)

    # Determine SK table
    elem = symbols[0]
    sk_table = f"{elem}-{elem}"

    # Write dftb_in.hsd
    natoms = len(positions)
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
    hsd += "    0.0 0.0 0.0 1.0\n"
    hsd += "  }\n"
    hsd += "}\n\n"
    hsd += "Options {\n"
    hsd += "  WriteResultsTag = Yes\n"
    hsd += "}\n\n"
    hsd += "Analysis {\n"
    hsd += "  CalculateForces = Yes\n"
    hsd += "}\n"

    with open(os.path.join(outdir, "dftb_in.hsd"), "w") as f:
        f.write(hsd)

    # Write geometry.gen (DFTB+ generic format)
    # S = supercell with cartesian coordinates (Angstrom)
    # First line: natoms, mode
    # Second line: element symbols (space separated, each gets a type number)
    # Then: index type x y z
    # Finally: origin (0 0 0) and 3 cell vectors
    gen_lines = [f"{natoms} S"]
    gen_lines.append(elem)
    for i, (x, y, z) in enumerate(positions, 1):
        gen_lines.append(f"{i:4d} 1 {x:18.10f} {y:18.10f} {z:18.10f}")
    # Origin and cell vectors
    gen_lines.append("0.0000000000 0.0000000000 0.0000000000")
    for i in range(3):
        gen_lines.append(f"{cell[i][0]:18.10f} {cell[i][1]:18.10f} {cell[i][2]:18.10f}")

    with open(os.path.join(outdir, "geometry.gen"), "w") as f:
        f.write("\n".join(gen_lines) + "\n")

    # Run DFTB+
    try:
        result = subprocess.run(
            [dftb_bin],
            cwd=outdir,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except FileNotFoundError:
        print(f"ERROR: DFTB+ binary not found: {dftb_bin}")
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print(f"ERROR: DFTB+ timed out in {outdir}")
        sys.exit(1)

    if result.returncode != 0:
        print(f"ERROR: DFTB+ failed in {outdir}")
        print(result.stderr[:500])
        sys.exit(1)

    # Parse forces from results.tag
    results_path = os.path.join(outdir, "results.tag")
    if not os.path.exists(results_path):
        print(f"ERROR: results.tag not found in {outdir}")
        sys.exit(1)

    forces = parse_dftb_results_tag(results_path, natoms)
    # DFTB+ results.tag forces are in Hartree/Bohr; convert to eV/Angstrom
    # 1 Hartree = 27.211386245988 eV, 1 Bohr = 0.529177210903 Angstrom
    hartree_to_ev = 27.211386245988
    bohr_to_angstrom = 0.529177210903
    forces *= hartree_to_ev / bohr_to_angstrom  # = 51.422 eV/Ang per Hartree/Bohr
    return forces


def parse_dftb_results_tag(path, natoms):
    """Parse forces array from DFTB+ results.tag file."""
    with open(path) as f:
        text = f.read()

    # Find forces block: "forces              :real:2:3,<natoms>"
    match = re.search(r'forces\s+:real:2:3,(\d+)\n', text)
    if not match:
        print(f"ERROR: forces block not found in {path}")
        sys.exit(1)

    n = int(match.group(1))
    if n != natoms:
        print(f"WARNING: forces natoms mismatch: {n} vs {natoms}")

    # Find position right after the forces header
    start = match.end()
    lines = text[start:].strip().split('\n')

    forces = []
    for i in range(natoms):
        parts = lines[i].strip().split()
        if len(parts) < 3:
            print(f"ERROR: force line {i} malformed in {path}")
            sys.exit(1)
        forces.append([float(parts[0]), float(parts[1]), float(parts[2])])

    return np.array(forces, dtype=float)


# ------------------------------------------------------------------
# LAMMPS force calculation
# ------------------------------------------------------------------
def run_lammps_forces(positions, cell, symbols, outdir, config, potential, mtp_file=None):
    """Run LAMMPS single point and return forces (eV/Angstrom)."""
    lammps_bin = config["tools"].get("lammps_bin", "lmp_serial")
    pot_paths = config["potentials"]
    elem = symbols[0]

    os.makedirs(outdir, exist_ok=True)
    natoms = len(positions)
    ax, ay, az = np.linalg.norm(cell[0]), np.linalg.norm(cell[1]), np.linalg.norm(cell[2])

    # Write LAMMPS data file
    data_lines = [f"LAMMPS data for {elem} phonon displacement"]
    data_lines.append("")
    data_lines.append(f"{natoms} atoms")
    data_lines.append("1 atom types")
    data_lines.append("")
    data_lines.append(f"0.0 {ax:.6f} xlo xhi")
    data_lines.append(f"0.0 {ay:.6f} ylo yhi")
    data_lines.append(f"0.0 {az:.6f} zlo zhi")
    data_lines.append("")
    # Get mass from material database
    mat_info = MATERIALS.get(elem if elem in MATERIALS else "diamond")
    mass = mat_info["mass"] if mat_info else 1.0
    data_lines.append("Masses")
    data_lines.append("")
    data_lines.append(f"1 {mass:.4f}")
    data_lines.append("")
    data_lines.append("Atoms")
    data_lines.append("")
    for i, (x, y, z) in enumerate(positions, 1):
        data_lines.append(f"{i} 1 {x:.6f} {y:.6f} {z:.6f}")

    data_path = os.path.join(outdir, "structure.lammps")
    with open(data_path, "w") as f:
        f.write("\n".join(data_lines) + "\n")

    # Write LAMMPS input script (paths relative to outdir since LAMMPS cwd=outdir)
    in_lines = []
    in_lines.append("# LAMMPS force calculation")
    in_lines.append("units           metal")
    in_lines.append("atom_style      atomic")
    in_lines.append("read_data       structure.lammps")
    in_lines.append("")

    if potential == "sw":
        pot_file = pot_paths.get("si_sw", "Si.sw")
        in_lines.append("pair_style      sw")
        in_lines.append(f"pair_coeff      * * {pot_file} {elem}")
    elif potential == "tersoff":
        in_lines.append("pair_style      tersoff")
        if elem == "Si":
            pot_file = pot_paths.get("si_tersoff", "Si.tersoff")
            in_lines.append(f"pair_coeff      * * {pot_file} Si")
        elif elem == "C":
            pot_file = pot_paths.get("c_tersoff", "SiC.tersoff")
            in_lines.append(f"pair_coeff      * * {pot_file} C")
    elif potential == "meam":
        lib_name = MEAM_LIB_NAMES.get(elem)
        if not lib_name:
            print(f"ERROR: MEAM not configured for {elem}")
            sys.exit(1)
        meam_lib = pot_paths.get("meam_library", "library.meam")
        in_lines.append("pair_style      meam")
        in_lines.append(f"pair_coeff      * * {meam_lib} {lib_name} NULL {lib_name}")
    elif potential == "mtp":
        if not mtp_file:
            print("ERROR: --mtp-file required for MTP")
            sys.exit(1)
        in_lines.append("pair_style      mlip mlip.ini")
        in_lines.append(f"pair_coeff      * * {mtp_file}")
    else:
        print(f"ERROR: Unknown potential {potential}")
        sys.exit(1)

    in_lines.append("")
    in_lines.append("neighbor        0.3 bin")
    in_lines.append("neigh_modify    delay 0")
    in_lines.append("")
    in_lines.append("timestep        0.001")
    in_lines.append("run             0")
    in_lines.append("")
    in_lines.append("# Dump forces")
    in_lines.append("dump            1 all custom 1 dump.force id type fx fy fz")
    in_lines.append('dump_modify     1 format line "%d %d %.10f %.10f %.10f"')
    in_lines.append("run             0")

    in_path = os.path.join(outdir, "force.in")
    with open(in_path, "w") as f:
        f.write("\n".join(in_lines) + "\n")

    # Run LAMMPS (use relative filename since cwd=outdir)
    log_path = os.path.join(outdir, "log.lammps")
    try:
        with open(log_path, "w") as logf:
            result = subprocess.run(
                [lammps_bin, "-in", "force.in"],
                cwd=outdir,
                stdout=logf,
                stderr=subprocess.STDOUT,
                timeout=60,
            )
    except FileNotFoundError:
        print(f"ERROR: LAMMPS binary not found: {lammps_bin}")
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print(f"ERROR: LAMMPS timed out in {outdir}")
        sys.exit(1)

    if result.returncode != 0:
        print(f"ERROR: LAMMPS failed in {outdir}")
        sys.exit(1)

    # Parse forces from dump file
    dump_path = os.path.join(outdir, "dump.force")
    if not os.path.exists(dump_path):
        print(f"ERROR: dump.force not found in {outdir}")
        sys.exit(1)

    forces = parse_lammps_dump_forces(dump_path, natoms)
    return forces


def parse_lammps_dump_forces(path, natoms):
    """Parse last frame forces from LAMMPS custom dump file."""
    with open(path) as f:
        lines = f.readlines()

    # Find the last "ITEM: TIMESTEP" and read the frame after it
    # Format:
    # ITEM: TIMESTEP
    # 0
    # ITEM: NUMBER OF ATOMS
    # N
    # ITEM: BOX BOUNDS ...
    # ...
    # ITEM: ATOMS id type fx fy fz
    # 1 1 fx fy fz
    # ...

    # Find last occurrence of "ITEM: ATOMS"
    atom_start = -1
    for i, line in enumerate(lines):
        if line.startswith("ITEM: ATOMS"):
            atom_start = i

    if atom_start < 0:
        print(f"ERROR: No ATOMS section found in {path}")
        sys.exit(1)

    forces = [None] * natoms
    for i in range(atom_start + 1, len(lines)):
        parts = lines[i].strip().split()
        if len(parts) < 5:
            continue
        atom_id = int(parts[0]) - 1  # 0-based index
        fx, fy, fz = float(parts[2]), float(parts[3]), float(parts[4])
        forces[atom_id] = [fx, fy, fz]

    if None in forces:
        print(f"ERROR: Missing forces for some atoms in {path}")
        sys.exit(1)

    return np.array(forces, dtype=float)


# ------------------------------------------------------------------
# Main workflow
# ------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Compute phonon bands with phonopy")
    parser.add_argument("--material", choices=["Si", "diamond", "C"], default="Si")
    parser.add_argument("--calculator", choices=["dftb+", "lammps"], required=True)
    parser.add_argument("--potential", choices=["sw", "tersoff", "meam", "mtp"], default=None,
                        help="LAMMPS potential (required for --calculator lammps)")
    parser.add_argument("--mtp-file", default=None)
    parser.add_argument("--supercell", nargs=3, type=int, default=[2, 2, 2])
    parser.add_argument("--outdir", default=".")
    parser.add_argument("--config", default="phonon_config.json")
    parser.add_argument("--distance", type=float, default=None,
                        help="Displacement distance (Angstrom). Default: phonopy default")
    parser.add_argument("--lattice", type=float, default=None,
                        help="Override lattice constant (Angstrom). Useful for DFTB+ after relaxation")
    args = parser.parse_args()

    config = load_config(args.config)
    mat_name = args.material
    if mat_name == "C":
        mat_name = "diamond"
    sc = args.supercell
    calculator = args.calculator

    if calculator == "lammps" and not args.potential:
        print("ERROR: --potential required for LAMMPS calculator")
        sys.exit(1)

    # Output prefix
    if calculator == "lammps":
        prefix = f"{mat_name}_{args.potential}_{sc[0]}x{sc[1]}x{sc[2]}"
    else:
        prefix = f"{mat_name}_dftb_{sc[0]}x{sc[1]}x{sc[2]}"

    outdir = os.path.join(args.outdir, prefix)
    os.makedirs(outdir, exist_ok=True)

    print(f"\n[phonon] Computing phonon bands for {mat_name}")
    print(f"[phonon] Calculator: {calculator}")
    if calculator == "lammps":
        print(f"[phonon] Potential: {args.potential}")
    print(f"[phonon] Supercell: {sc[0]}x{sc[1]}x{sc[2]}")
    print(f"[phonon] Output: {outdir}\n")

    # 1. Build conventional cubic cell
    if args.lattice:
        print(f"[phonon] Using custom lattice constant: {args.lattice:.4f} Ang")
        prefix += f"_a{args.lattice:.3f}"
        outdir = os.path.join(args.outdir, prefix)
        os.makedirs(outdir, exist_ok=True)
    prim = make_conventional_atoms(mat_name, lattice=args.lattice)
    print(f"[phonon] Conventional cell: {len(prim)} atoms")

    # 2. Initialize Phonopy
    phonon = Phonopy(prim, supercell_matrix=sc, primitive_matrix="auto")
    distance = args.distance if args.distance else get_default_displacement_distance("vasp")
    phonon.generate_displacements(distance=distance)
    displacements = phonon.displacements
    print(f"[phonon] Generated {len(displacements)} displacement structures (distance={distance})")

    # 3. Compute forces for each displacement
    force_sets = []
    for i, disp in enumerate(displacements):
        disp_dir = os.path.join(outdir, f"disp-{i+1:03d}")
        print(f"[phonon] Displacement {i+1}/{len(displacements)} -> {disp_dir}")

        # Build supercell with displacement applied
        # disp is [atom_index, dx, dy, dz]
        supercell = phonon.supercell.copy()
        pos = supercell.positions.copy()

        # Apply displacement
        atom_idx = int(disp[0])
        disp_vec = np.array(disp[1:4], dtype=float)
        pos[atom_idx] += disp_vec
        supercell.positions = pos

        symbols = [s for s in supercell.symbols]

        if calculator == "dftb+":
            forces = run_dftb_forces(
                supercell.positions,
                supercell.cell,
                symbols,
                disp_dir,
                config,
            )
        else:  # lammps
            forces = run_lammps_forces(
                supercell.positions,
                supercell.cell,
                symbols,
                disp_dir,
                config,
                args.potential,
                args.mtp_file,
            )

        force_sets.append(forces)
        print(f"[phonon]   Forces computed, max |F| = {np.max(np.abs(forces)):.4f} eV/Ang")

    # 4. Produce force constants
    phonon.forces = force_sets
    phonon.produce_force_constants()
    print(f"[phonon] Force constants produced")

    # 5. Band structure
    phonon.auto_band_structure(plot=False)
    bands = phonon.get_band_structure_dict()
    print(f"[phonon] Band structure computed")

    # 6. Write band structure to file (phonopy YAML format)
    band_yaml = os.path.join(outdir, "band.yaml")
    phonon.write_yaml_band_structure(filename=band_yaml)
    print(f"[phonon] Saved band structure to {band_yaml}")

    # Also write simple text format for easy plotting
    band_dat = os.path.join(outdir, "band.dat")
    write_band_dat(bands, band_dat)
    print(f"[phonon] Saved band data to {band_dat}")

    # 7. Plot if matplotlib available
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        plot_band = os.path.join(outdir, "band.png")
        phonon.auto_band_structure(plot=True)
        plt.savefig(plot_band, dpi=200)
        plt.close()
        print(f"[phonon] Saved band plot to {plot_band}")
    except Exception as e:
        print(f"[phonon] Plotting skipped: {e}")

    print(f"\n[phonon] Done. Results in {outdir}\n")


def write_band_dat(bands, path):
    """Write phonon band data in simple text format."""
    distances = bands["distances"]       # list of 1D arrays, one per segment
    frequencies = bands["frequencies"] # list of 2D arrays (nqpoints, nbands)

    with open(path, "w") as f:
        f.write("# Phonon band structure\n")
        f.write("# Each segment separated by blank line\n")
        f.write("# q_distance  frequencies (THz)\n")
        for q_seg, freq_seg in zip(distances, frequencies):
            for q, freqs in zip(q_seg, freq_seg):
                f.write(f"{q:.6f}")
                for fr in freqs:
                    f.write(f"  {fr:.6f}")
                f.write("\n")
            f.write("\n")


if __name__ == "__main__":
    main()
