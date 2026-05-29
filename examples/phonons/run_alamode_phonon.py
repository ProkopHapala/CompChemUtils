#!/usr/bin/env python3
"""
run_alamode_phonon.py
=====================
End-to-end ALAMODE + LAMMPS phonon workflow for bulk Si and diamond.
Follows the official ALAMODE Si_LAMMPS tutorial.

Usage:
  python run_alamode_phonon.py --material Si --potential sw --supercell 2 2 2
  python run_alamode_phonon.py --material diamond --potential tersoff --supercell 2 2 2
"""

import argparse
import json
import os
import subprocess
import sys

# Lattice constants (Angstrom) for conventional cubic cell
MATERIALS = {
    "Si": {"lattice": 5.431, "mass": 28.0855, "element": "Si", "type_id": 1},
    "diamond": {"lattice": 3.567, "mass": 12.011, "element": "C", "type_id": 1},
    "C": {"lattice": 3.567, "mass": 12.011, "element": "C", "type_id": 1},
}

POTENTIAL_MAP = {
    ("Si", "sw"): "Si.sw",
    ("Si", "tersoff"): "Si.tersoff",
    ("C", "tersoff"): "SiC.tersoff",
}


def load_config(path="phonon_config.json"):
    default = {
        "tools": {
            "lammps_bin": "lmp_serial",
            "alamode_alm": "alm",
            "alamode_anphon": "anphon",
        },
        "potentials": {
            "si_sw": "Si.sw",
            "si_tersoff": "Si.tersoff",
            "c_tersoff": "SiC.tersoff",
        },
    }
    if os.path.exists(path):
        with open(path) as f:
            user = json.load(f)
        for k in ["tools", "potentials"]:
            if k in user:
                default[k].update(user[k])
    return default


def diamond_frac_positions(sc):
    nx, ny, nz = sc
    base = [
        (0.0, 0.0, 0.0), (0.5, 0.5, 0.0), (0.5, 0.0, 0.5), (0.0, 0.5, 0.5),
        (0.25, 0.25, 0.25), (0.75, 0.75, 0.25), (0.75, 0.25, 0.75), (0.25, 0.75, 0.75),
    ]
    pos = []
    for ix in range(nx):
        for iy in range(ny):
            for iz in range(nz):
                for fx, fy, fz in base:
                    pos.append(((fx + ix) / nx, (fy + iy) / ny, (fz + iz) / nz))
    return pos


def write_lammps_data(prefix, mat_info, sc, outdir):
    a0 = mat_info["lattice"]
    nx, ny, nz = sc
    ax, ay, az = a0 * nx, a0 * ny, a0 * nz
    frac = diamond_frac_positions(sc)
    nat = len(frac)
    lines = [
        f"# {mat_info['element']} supercell {nx}x{ny}x{nz}",
        f"{nat} atoms",
        "1 atom types",
        f"0.0 {ax:.6f} xlo xhi",
        f"0.0 {ay:.6f} ylo yhi",
        f"0.0 {az:.6f} zlo zhi",
        "0.0 0.0 0.0 xy xz yz",
        "",
        "Masses",
        "",
        f"1 {mat_info['mass']:.4f}",
        "",
        "Atoms",
        "",
    ]
    for i, (fx, fy, fz) in enumerate(frac, 1):
        lines.append(f"{i} 1 {fx * ax:.6f} {fy * ay:.6f} {fz * az:.6f}")
    path = os.path.join(outdir, f"{prefix}.lammps")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"[setup] Wrote {path} ({nat} atoms)")
    return path


def write_lammps_input(prefix, pot_file, outdir):
    """Write LAMMPS input that outputs XFSET for ALAMODE extract.py."""
    lines = [
        "units           metal",
        "atom_style      atomic",
        "boundary        p p p",
        "",
        "read_data       tmp.lammps",
        "",
        "pair_style      sw" if pot_file.endswith(".sw") else "pair_style      tersoff",
        f"pair_coeff      * * {pot_file} Si" if pot_file.endswith(".sw") else f"pair_coeff      * * {pot_file} Si",
        "",
        'dump            1 all custom 1 XFSET id xu yu zu fx fy fz',
        'dump_modify     1 format float "%20.15f"',
        "run             0",
        "",
    ]
    # Fix pair_coeff for C (diamond)
    if "SiC" in pot_file or "C.tersoff" in pot_file:
        lines[7] = f"pair_coeff      * * {pot_file} C"
    path = os.path.join(outdir, "in.force")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"[setup] Wrote {path}")
    return path


def write_alm_suggest(prefix, mat_info, sc, outdir):
    nx, ny, nz = sc
    a0 = mat_info["lattice"]
    elem = mat_info["element"]
    nat = 8 * nx * ny * nz
    cell = a0 * nx
    frac = diamond_frac_positions(sc)
    pos_lines = "\n".join(f"  1 {fx:.16f} {fy:.16f} {fz:.16f}" for fx, fy, fz in frac)
    bohr = cell / 0.529177
    text = f"""&general
  PREFIX = {prefix}
  MODE = suggest
  NAT = {nat}; NKD = 1
  KD = {elem}
/

&interaction
  NORDER = 1
/

&cell
  {bohr:.4f}
  1.0 0.0 0.0
  0.0 1.0 0.0
  0.0 0.0 1.0
/

&cutoff
  {elem}-{elem} 6.0
/

&position
{pos_lines}
/

"""
    path = os.path.join(outdir, f"{prefix}_suggest.in")
    with open(path, "w") as f:
        f.write(text)
    print(f"[setup] Wrote {path}")
    return path


def write_alm_optimize(prefix, mat_info, sc, outdir):
    nx, ny, nz = sc
    a0 = mat_info["lattice"]
    elem = mat_info["element"]
    nat = 8 * nx * ny * nz
    cell = a0 * nx
    frac = diamond_frac_positions(sc)
    pos_lines = "\n".join(f"  1 {fx:.16f} {fy:.16f} {fz:.16f}" for fx, fy, fz in frac)
    bohr = cell / 0.529177
    text = f"""&general
  PREFIX = {prefix}
  MODE = optimize
  NAT = {nat}; NKD = 1
  KD = {elem}
/

&optimize
  DFSET = DFSET_harmonic
/

&interaction
  NORDER = 1
/

&cell
  {bohr:.4f}
  1.0 0.0 0.0
  0.0 1.0 0.0
  0.0 0.0 1.0
/

&cutoff
  {elem}-{elem} 6.0
/

&position
{pos_lines}
/

"""
    path = os.path.join(outdir, f"{prefix}_optimize.in")
    with open(path, "w") as f:
        f.write(text)
    print(f"[setup] Wrote {path}")
    return path


def write_anphon(prefix, mat_info, sc, outdir):
    nx, ny, nz = sc
    a0 = mat_info["lattice"]
    elem = mat_info["element"]
    mass = mat_info["mass"]
    cell = a0 * nx
    frac = diamond_frac_positions(sc)
    pos_lines = "\n".join(f"  1 {fx:.16f} {fy:.16f} {fz:.16f}" for fx, fy, fz in frac)
    bohr = cell / 0.529177
    text = f"""&general
  PREFIX = {prefix}
  MODE = phonons
  FCSXML = {prefix}.xml
  NKD = 1
  KD = {elem}
  MASS = {mass:.4f}
/

&cell
  {bohr:.4f}
  1.0 0.0 0.0
  0.0 1.0 0.0
  0.0 0.0 1.0
/

&position
{pos_lines}
/

&kpoint
  1
  G 0.0 0.0 0.0 X 0.5 0.0 0.5 101
  X 0.5 0.0 0.5 K 0.375 0.375 0.75 101
  K 0.375 0.375 0.75 G 0.0 0.0 0.0 101
  G 0.0 0.0 0.0 L 0.5 0.5 0.5 101
/
"""
    path = os.path.join(outdir, f"{prefix}_anphon.in")
    with open(path, "w") as f:
        f.write(text)
    print(f"[setup] Wrote {path}")
    return path


def run_cmd(cmd, cwd, msg):
    print(f"[run] {msg}")
    print(f"      {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ERROR: {msg} failed")
        print("STDOUT:", result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout)
        print("STDERR:", result.stderr[-2000:] if len(result.stderr) > 2000 else result.stderr)
        sys.exit(1)
    return result


def main():
    parser = argparse.ArgumentParser(description="Run full ALAMODE + LAMMPS phonon workflow")
    parser.add_argument("--material", choices=["Si", "diamond", "C"], default="Si")
    parser.add_argument("--potential", choices=["sw", "tersoff"], default="sw")
    parser.add_argument("--supercell", nargs=3, type=int, default=[2, 2, 2])
    parser.add_argument("--outdir", default="alamode_results")
    parser.add_argument("--config", default="phonon_config.json")
    parser.add_argument("--skip-lammps", action="store_true", help="Skip LAMMPS force calc (use existing XFSET files)")
    args = parser.parse_args()

    mat_name = "diamond" if args.material == "C" else args.material
    mat_info = MATERIALS[mat_name]
    sc = args.supercell
    elem = mat_info["element"]

    config = load_config(args.config)
    lammps_bin = config["tools"].get("lammps_bin", "lmp_serial")
    alm_bin = config["tools"].get("alamode_alm", "alm")
    anphon_bin = config["tools"].get("alamode_anphon", "anphon")

    # Find potential file
    pot_key = (elem, args.potential)
    if pot_key not in POTENTIAL_MAP:
        print(f"ERROR: potential {args.potential} not available for {elem}")
        sys.exit(1)
    pot_fname = POTENTIAL_MAP[pot_key]
    pot_file = config["potentials"].get(
        f"si_{args.potential}" if elem == "Si" else f"c_{args.potential}",
        pot_fname
    )
    if not os.path.exists(pot_file):
        # Try LAMMPS potentials dir
        lammps_pot_dir = os.path.dirname(lammps_bin)
        lammps_pot_dir = os.path.join(lammps_pot_dir, "..", "potentials")
        alt = os.path.join(lammps_pot_dir, pot_fname)
        if os.path.exists(alt):
            pot_file = alt
    if not os.path.exists(pot_file):
        print(f"ERROR: potential file not found: {pot_file}")
        sys.exit(1)
    print(f"[setup] Using potential: {pot_file}")

    prefix = f"{mat_name}_{args.potential}_{sc[0]}x{sc[1]}x{sc[2]}"
    outdir = os.path.join(args.outdir, prefix)
    os.makedirs(outdir, exist_ok=True)

    # 1. Generate LAMMPS structure
    write_lammps_data(prefix, mat_info, sc, outdir)

    # 2. ALM suggest
    suggest_in = write_alm_suggest(prefix, mat_info, sc, outdir)
    run_cmd([alm_bin, os.path.basename(suggest_in)], outdir, "ALM suggest (generate displacement patterns)")

    # 3. Displace.py
    lammps_data = os.path.join(outdir, f"{prefix}.lammps")
    pattern = os.path.join(outdir, f"{prefix}.pattern_HARMONIC")
    if not os.path.exists(pattern):
        print(f"ERROR: pattern file not generated: {pattern}")
        sys.exit(1)

    displace_cmd = [
        sys.executable, os.path.expanduser("~/SW/alamode/tools/displace.py"),
        "--LAMMPS", f"{prefix}.lammps",
        "--prefix", "harm",
        "--mag", "0.01",
        "-pf", f"{prefix}.pattern_HARMONIC",
    ]
    run_cmd(displace_cmd, outdir, "Generate displaced structures")

    # 4. LAMMPS force calculations
    if not args.skip_lammps:
        lammps_in = write_lammps_input(prefix, pot_file, outdir)
        # Copy potential to working dir so LAMMPS can find it
        import shutil
        shutil.copy(pot_file, outdir)

        disp_files = sorted([f for f in os.listdir(outdir) if f.startswith("harm") and f.endswith(".lammps")])
        if not disp_files:
            print("ERROR: no displaced structures found")
            sys.exit(1)

        for i, df in enumerate(disp_files, 1):
            case = df.replace(".lammps", "")
            shutil.copy(os.path.join(outdir, df), os.path.join(outdir, "tmp.lammps"))
            run_cmd([lammps_bin, "-in", "in.force"], outdir, f"LAMMPS force calc {i}/{len(disp_files)} ({case})")
            # Rename XFSET
            xfset_src = os.path.join(outdir, "XFSET")
            xfset_dst = os.path.join(outdir, f"XFSET.{case}")
            if os.path.exists(xfset_src):
                os.rename(xfset_src, xfset_dst)
            else:
                print(f"WARNING: XFSET not found for {case}")

    # 5. Extract.py
    xfset_files = sorted([f for f in os.listdir(outdir) if f.startswith("XFSET.harm")])
    if not xfset_files:
        print("ERROR: no XFSET files found")
        sys.exit(1)

    extract_cmd = [
        sys.executable, os.path.expanduser("~/SW/alamode/tools/extract.py"),
        "--LAMMPS", f"{prefix}.lammps",
    ] + xfset_files
    result = subprocess.run(extract_cmd, cwd=outdir, capture_output=True, text=True)
    if result.returncode != 0:
        print("ERROR: extract.py failed")
        print("STDERR:", result.stderr)
        sys.exit(1)
    dfset_path = os.path.join(outdir, "DFSET_harmonic")
    with open(dfset_path, "w") as f:
        f.write(result.stdout)
    print(f"[run] Wrote {dfset_path}")

    # 6. ALM optimize
    opt_in = write_alm_optimize(prefix, mat_info, sc, outdir)
    run_cmd([alm_bin, os.path.basename(opt_in)], outdir, "ALM optimize (compute force constants)")

    # 7. Anphon
    anphon_in = write_anphon(prefix, mat_info, sc, outdir)
    run_cmd([anphon_bin, os.path.basename(anphon_in)], outdir, "Anphon (compute phonon dispersion)")

    band_dat = os.path.join(outdir, f"{prefix}.band.dat")
    if os.path.exists(band_dat):
        print(f"\n[SUCCESS] Phonon bands written to {band_dat}")
    else:
        print(f"\n[WARNING] Expected {band_dat} not found")
        print("Files in outdir:", os.listdir(outdir))


if __name__ == "__main__":
    main()
