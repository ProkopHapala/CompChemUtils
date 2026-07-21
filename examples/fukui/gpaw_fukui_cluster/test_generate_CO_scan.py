#!/usr/bin/env python3
"""Smoketest for generate_CO_scan_jobs.py — runs the full generator pipeline to disk,
validates generated scripts, and produces .xyz movie files showing CO scanning over
each target atom. No QM backend required.

Usage:
    python test_generate_CO_scan.py
"""
import os, sys, re, ast, shutil, numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from generate_CO_scan_jobs import (
    read_xyz, make_scan_grid, box_molecule, box_positions,
    bake_scan_script, bake_pbs, bake_pyscf_scan_script, bake_pyscf_pbs,
    bake_submit_all, MOLECULES, MOLECULES_PYSCF, R_CO, HEAVY_ELEMS,
    find_symmetry_ops, find_equiv_classes, select_heavy_atoms,
)

GEOM_DIR = os.path.join(SCRIPT_DIR, 'geometries')
SMOKETEST_DIR = os.path.join(SCRIPT_DIR, 'smoketest_output')
MOVIES_DIR = os.path.join(SMOKETEST_DIR, 'xyz_movies')

PASS = 0
FAIL = 0

def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS: {name}")
    else:
        FAIL += 1
        print(f"  FAIL: {name}  {detail}")

def extract_python_list(text, var_name):
    m = re.search(rf'{var_name} = ', text)
    if not m:
        return None
    start = m.end()
    depth = 0
    for i in range(start, len(text)):
        if text[i] == '[':
            depth += 1
        elif text[i] == ']':
            depth -= 1
            if depth == 0:
                return ast.literal_eval(text[start:i+1])
    return None

def extract_python_str(text, var_name):
    m = re.search(rf'{var_name} = "(.+?)"', text)
    if not m:
        return None
    return m.group(1)


def write_xyz_movie(fname, mol_syms, mol_ps, co_atoms_per_r, r_grid):
    """Write a multi-frame XYZ file showing molecule + CO at each scan distance.
    CO atoms_per_r: list of (c_pos, o_pos) tuples. O-apex: O closer to molecule."""
    n_mol = len(mol_syms)
    all_syms = mol_syms + ['C', 'O']
    with open(fname, 'w') as f:
        for ir, r in enumerate(r_grid):
            c_pos, o_pos = co_atoms_per_r[ir]
            all_ps = list(mol_ps) + [c_pos, o_pos]
            f.write(f"{len(all_syms)}\n")
            f.write(f"r={r:.4f} O_apex_over_atom (frame {ir}/{len(r_grid)-1})\n")
            for s, p in zip(all_syms, all_ps):
                f.write(f"{s:2s} {p[0]:12.6f} {p[1]:12.6f} {p[2]:12.6f}\n")

def write_xyz_movie_gpaw(fname, mol_syms, mol_boxed, boxed_per_r, r_grid, atom_idx):
    """Write XYZ movie from GPAW boxed positions (already shifted into cell)."""
    n_mol = len(mol_syms)
    all_syms = mol_syms + ['C', 'O']
    with open(fname, 'w') as f:
        for ir, r in enumerate(r_grid):
            frame = boxed_per_r[ir]
            f.write(f"{len(all_syms)}\n")
            f.write(f"r={r:.4f} GPAW_boxed O_apex frame {ir}/{len(r_grid)-1}\n")
            for i, (s, p) in enumerate(zip(all_syms, frame)):
                tag = " <-- TARGET" if i == atom_idx else ""
                f.write(f"{s:2s} {p[0]:12.6f} {p[1]:12.6f} {p[2]:12.6f}{tag}\n")


def test_scan_grid():
    print("\n=== Test: scan grid ===")
    grid = make_scan_grid()
    check("grid starts at 1.5", abs(grid[0] - 1.5) < 1e-9, f"got {grid[0]}")
    check("grid has 0.1 step in fine region", abs(grid[1] - grid[0] - 0.1) < 1e-9, f"got {grid[1]-grid[0]}")
    check("grid includes r_inf=15", abs(grid[-1] - 15.0) < 1e-9, f"got {grid[-1]}")
    check("grid covers 1.5-6.0 range", grid[0] <= 1.5 and grid[-2] >= 6.0, f"range [{grid[0]}, {grid[-2]}]")

def test_box_molecule():
    print("\n=== Test: box_molecule (no duplicate atom) ===")
    mol_ps = np.array([[0, 0, 0], [-0.758, 0.636, 0], [0.758, 0.636, 0]])
    boxed, cell = box_molecule(mol_ps, 6.0, 30.0)
    check("boxed shape == mol shape", boxed.shape == mol_ps.shape, f"got {boxed.shape}")
    check("cell has vacuum padding in x,y", all(cell[:2] >= 12.0), f"got {cell}")
    check("cell z is fixed", abs(cell[2] - 30.0) < 1e-9, f"got {cell}")
    check("molecule centered in cell", np.allclose(boxed.mean(axis=0), cell/2, atol=0.5), f"center={boxed.mean(axis=0)}")

def test_box_positions():
    print("\n=== Test: box_positions (mol + CO) ===")
    mol_ps = np.array([[0, 0, 0], [-0.758, 0.636, 0], [0.758, 0.636, 0]])
    co_ps = np.array([[0, 0, 2.0], [0, 0, 3.128]])
    boxed, cell = box_positions(mol_ps, co_ps, 6.0, 30.0)
    check("boxed shape == mol+co shape", boxed.shape == (5, 3), f"got {boxed.shape}")


def validate_pyscf_script(script_text, mol_name, syms, ps, atom_idx, atom_label):
    """Validate a baked PySCF script and return parsed geometry data for movie writing."""
    tag = f"{mol_name}_atom{atom_idx}_{atom_label}"
    checks_tag = f"PySCF {tag}"

    try:
        compile(script_text, f"run_{tag}.py", 'exec')
        check(f"{checks_tag}: Python syntax valid", True)
    except SyntaxError as e:
        check(f"{checks_tag}: Python syntax valid", False, str(e))
        return None

    co_atoms = extract_python_list(script_text, 'CO_ATOMS_PER_R')
    mol_ps_list = extract_python_list(script_text, 'MOL_PS')
    mol_syms_list = extract_python_list(script_text, 'MOL_SYMS')
    r_grid_list = extract_python_list(script_text, 'R_GRID')

    if not (co_atoms and mol_ps_list and mol_syms_list):
        check(f"{checks_tag}: extracted geometry data", False)
        return None
    check(f"{checks_tag}: extracted geometry data", True)

    target = np.array(mol_ps_list[atom_idx])
    # First frame is farthest (r=15), last frame is closest (r=1.5)
    c_pos_close = np.array(co_atoms[-1][0])
    o_pos_close = np.array(co_atoms[-1][1])
    dist_o = np.linalg.norm(o_pos_close - target)
    dist_c = np.linalg.norm(c_pos_close - target)

    check(f"{checks_tag}: O-apex (O closer than C)", dist_o < dist_c, f"dist_O={dist_o:.3f} dist_C={dist_c:.3f}")
    check(f"{checks_tag}: O at r=1.5 from target (last frame)", abs(dist_o - 1.5) < 0.01, f"dist_O={dist_o:.3f}")
    check(f"{checks_tag}: CO xy matches target xy",
          abs(o_pos_close[0] - target[0]) < 1e-6 and abs(o_pos_close[1] - target[1]) < 1e-6,
          f"O=({o_pos_close[0]:.6f},{o_pos_close[1]:.6f}) target=({target[0]:.6f},{target[1]:.6f})")

    count = script_text.count('density_fit()')
    check(f"{checks_tag}: 3x density_fit()", count == 3, f"got {count}")
    check(f"{checks_tag}: dynamic OMP_NUM_THREADS", 'os.environ.get("OMP_NUM_THREADS"' in script_text)
    check(f"{checks_tag}: scan far->near", r_grid_list[0] > r_grid_list[-1], f"first={r_grid_list[0]} last={r_grid_list[-1]}")
    check(f"{checks_tag}: DM reuse (dm0=prev_dm)", 'dm0=prev_dm' in script_text and 'make_rdm1()' in script_text)

    return {'mol_syms': mol_syms_list, 'mol_ps': mol_ps_list,
            'co_atoms_per_r': co_atoms, 'r_grid': r_grid_list}

def validate_gpaw_script(script_text, mol_name, syms, ps, atom_idx, atom_label):
    """Validate a baked GPAW script and return parsed geometry data for movie writing."""
    tag = f"{mol_name}_atom{atom_idx}_{atom_label}"
    checks_tag = f"GPAW {tag}"

    try:
        compile(script_text, f"run_{tag}.py", 'exec')
        check(f"{checks_tag}: Python syntax valid", True)
    except SyntaxError as e:
        check(f"{checks_tag}: Python syntax valid", False, str(e))
        return None

    mol_syms_list = extract_python_list(script_text, 'MOL_SYMS')
    mol_boxed = extract_python_list(script_text, 'MOL_BOXED')
    boxed_per_r = extract_python_list(script_text, 'BOXED_PER_R')
    r_grid_list = extract_python_list(script_text, 'R_GRID')

    if not (mol_syms_list and mol_boxed and boxed_per_r):
        check(f"{checks_tag}: extracted geometry data", False)
        return None
    check(f"{checks_tag}: extracted geometry data", True)

    check(f"{checks_tag}: len(MOL_BOXED) == len(MOL_SYMS)", len(mol_boxed) == len(mol_syms_list),
          f"got {len(mol_boxed)} vs {len(mol_syms_list)}")

    n_mol = len(mol_boxed)
    # First frame is farthest (r=15), last frame is closest (r=1.5)
    frame_close = boxed_per_r[-1]
    co_c = np.array(frame_close[n_mol])
    co_o = np.array(frame_close[n_mol + 1])
    target_boxed = np.array(mol_boxed[atom_idx])
    dist_o = np.linalg.norm(co_o - target_boxed)
    dist_c = np.linalg.norm(co_c - target_boxed)

    check(f"{checks_tag}: O-apex (O closer than C)", dist_o < dist_c, f"dist_O={dist_o:.3f} dist_C={dist_c:.3f}")
    check(f"{checks_tag}: O at r=1.5 from target (last frame)", abs(dist_o - 1.5) < 0.5, f"dist_O={dist_o:.3f}")
    check(f"{checks_tag}: maxiter=200", 'maxiter=200' in script_text)
    check(f"{checks_tag}: CONST_CELL", 'CONST_CELL' in script_text)
    check(f"{checks_tag}: set_cell on restart", 'set_cell(CONST_CELL' in script_text)
    check(f"{checks_tag}: scan far->near", r_grid_list[0] > r_grid_list[-1], f"first={r_grid_list[0]} last={r_grid_list[-1]}")

    return {'mol_syms': mol_syms_list, 'mol_boxed': mol_boxed,
            'boxed_per_r': boxed_per_r, 'r_grid': r_grid_list}

def validate_pbs(pbs_text, backend, tag):
    """Validate PBS submission script content."""
    check(f"PBS {tag}: has -q luna", '#PBS -q luna' in pbs_text)
    if backend == 'gpaw':
        check(f"PBS {tag}: py-gpaw module", 'py-gpaw' in pbs_text)
        check(f"PBS {tag}: GPAW_SETUP_PATH", 'GPAW_SETUP_PATH' in pbs_text)
        check(f"PBS {tag}: python3 not gpaw-python", 'python3' in pbs_text and 'gpaw-python' not in pbs_text)
    elif backend == 'pyscf':
        check(f"PBS {tag}: mambaforge module", 'mambaforge' in pbs_text)
        check(f"PBS {tag}: $PBS_NUM_PPN", '$PBS_NUM_PPN' in pbs_text)

def test_site_resolution(mol_name, syms, ps, selected, r_grid):
    """Verify that different atom sites produce different CO positions (not duplicates)."""
    if len(selected) < 2:
        check(f"Site resolution {mol_name}: multiple sites (skipped, {len(selected)} atom)", True)
        return

    spec = MOLECULES_PYSCF[mol_name]
    first_r_positions = []
    for atom_idx, atom_label in selected:
        script = bake_pyscf_scan_script(mol_name, syms, ps, atom_idx, atom_label,
                                        'def2-SVP', 'PBE', r_grid, spec)
        co_atoms = extract_python_list(script, 'CO_ATOMS_PER_R')
        o_pos = co_atoms[-1][1]  # last frame = closest (r=1.5)
        first_r_positions.append(tuple(o_pos))

    unique = len(set(first_r_positions))
    check(f"Site resolution {mol_name}: {len(selected)} sites unique", unique == len(selected),
          f"got {unique} unique out of {len(selected)}")


def main():
    print("=" * 70)
    print("SMOKETEST: generate_CO_scan_jobs.py — full pipeline + XYZ movies")
    print("=" * 70)

    # Clean and create output dirs
    if os.path.exists(SMOKETEST_DIR):
        shutil.rmtree(SMOKETEST_DIR)
    os.makedirs(SMOKETEST_DIR)
    os.makedirs(MOVIES_DIR)

    gpaw_jobs_dir = os.path.join(SMOKETEST_DIR, 'jobs_CO_scan')
    pyscf_jobs_dir = os.path.join(SMOKETEST_DIR, 'jobs_CO_scan_pyscf')
    os.makedirs(gpaw_jobs_dir)
    os.makedirs(pyscf_jobs_dir)

    r_grid = make_scan_grid()
    n_gpaw = 0
    n_pyscf = 0

    # --- Unit tests ---
    test_scan_grid()
    test_box_molecule()
    test_box_positions()

    # --- Full pipeline: generate all jobs to disk + validate + write movies ---
    for mol_name in sorted(MOLECULES.keys()):
        xyz_path = os.path.join(GEOM_DIR, f'{mol_name}.xyz')
        if not os.path.isfile(xyz_path):
            print(f"\n  SKIP: {mol_name} (no geometry file)")
            continue

        syms, ps = read_xyz(xyz_path)
        ops = find_symmetry_ops(syms, ps, tol=0.1)
        classes = find_equiv_classes(syms, ps, ops, tol=0.1)
        selected = select_heavy_atoms(syms, ps, classes, ops)

        print(f"\n--- {mol_name}: {len(selected)} atoms selected ---")

        # Site resolution check
        test_site_resolution(mol_name, syms, ps, selected, r_grid)

        for atom_idx, atom_label in selected:
            tag = f"{mol_name}_atom{atom_idx}_{atom_label}"

            # --- Generate GPAW script + PBS to disk ---
            spec_gpaw = MOLECULES[mol_name]
            gpaw_script = bake_scan_script(mol_name, syms, ps, atom_idx, atom_label,
                                           500.0, 6.0, 30.0, 'PBE', r_grid, spec_gpaw)
            gpaw_path = os.path.join(gpaw_jobs_dir, f'run_{tag}.py')
            with open(gpaw_path, 'w') as f:
                f.write(gpaw_script)
            os.chmod(gpaw_path, 0o755)

            gpaw_pbs = bake_pbs(mol_name, atom_idx, atom_label, spec_gpaw, 500.0, 6.0, 30.0, 'PBE')
            with open(os.path.join(gpaw_jobs_dir, f'submit_{tag}.pbs'), 'w') as f:
                f.write(gpaw_pbs)

            # Validate GPAW script
            gpaw_data = validate_gpaw_script(gpaw_script, mol_name, syms, ps, atom_idx, atom_label)
            validate_pbs(gpaw_pbs, 'gpaw', tag)

            # Write GPAW XYZ movie (boxed positions)
            if gpaw_data:
                movie_path = os.path.join(MOVIES_DIR, f'gpaw_{tag}_movie.xyz')
                write_xyz_movie_gpaw(movie_path, gpaw_data['mol_syms'],
                                     gpaw_data['mol_boxed'], gpaw_data['boxed_per_r'],
                                     gpaw_data['r_grid'], atom_idx)
                check(f"GPAW {tag}: XYZ movie written", os.path.isfile(movie_path))

            # --- Generate PySCF script + PBS to disk ---
            spec_pyscf = MOLECULES_PYSCF[mol_name]
            pyscf_script = bake_pyscf_scan_script(mol_name, syms, ps, atom_idx, atom_label,
                                                  'def2-SVP', 'PBE', r_grid, spec_pyscf)
            pyscf_path = os.path.join(pyscf_jobs_dir, f'run_{tag}.py')
            with open(pyscf_path, 'w') as f:
                f.write(pyscf_script)
            os.chmod(pyscf_path, 0o755)

            pyscf_pbs = bake_pyscf_pbs(mol_name, atom_idx, atom_label, spec_pyscf, 'def2-SVP', 'PBE')
            with open(os.path.join(pyscf_jobs_dir, f'submit_{tag}.pbs'), 'w') as f:
                f.write(pyscf_pbs)

            # Validate PySCF script
            pyscf_data = validate_pyscf_script(pyscf_script, mol_name, syms, ps, atom_idx, atom_label)
            validate_pbs(pyscf_pbs, 'pyscf', tag)

            # Write PySCF XYZ movie (raw positions, no cell)
            if pyscf_data:
                movie_path = os.path.join(MOVIES_DIR, f'pyscf_{tag}_movie.xyz')
                write_xyz_movie(movie_path, pyscf_data['mol_syms'],
                                pyscf_data['mol_ps'], pyscf_data['co_atoms_per_r'],
                                pyscf_data['r_grid'])
                check(f"PySCF {tag}: XYZ movie written", os.path.isfile(movie_path))

            n_gpaw += 1
            n_pyscf += 1

    # Write submit_all.sh scripts
    submit_gpaw = bake_submit_all(n_gpaw)
    with open(os.path.join(gpaw_jobs_dir, 'submit_all.sh'), 'w') as f:
        f.write(submit_gpaw)
    os.chmod(os.path.join(gpaw_jobs_dir, 'submit_all.sh'), 0o755)

    submit_pyscf = bake_submit_all(n_pyscf)
    with open(os.path.join(pyscf_jobs_dir, 'submit_all.sh'), 'w') as f:
        f.write(submit_pyscf)
    os.chmod(os.path.join(pyscf_jobs_dir, 'submit_all.sh'), 0o755)

    # --- Summary ---
    print("\n" + "=" * 70)
    print(f"RESULTS: {PASS} passed, {FAIL} failed")
    print(f"GPAW scripts:  {n_gpaw}  -> {gpaw_jobs_dir}/")
    print(f"PySCF scripts: {n_pyscf}  -> {pyscf_jobs_dir}/")
    print(f"XYZ movies:    {n_gpaw + n_pyscf}  -> {MOVIES_DIR}/")
    print(f"\nOpen XYZ movies in VESTA / Ovito / ASE GUI to verify CO placement:")
    print(f"  e.g. {MOVIES_DIR}/pyscf_PTCDA_atom0_C1_movie.xyz")
    print(f"  e.g. {MOVIES_DIR}/gpaw_pentacene_atom10_C11_movie.xyz")
    print("=" * 70)
    return 1 if FAIL > 0 else 0

if __name__ == '__main__':
    sys.exit(main())
