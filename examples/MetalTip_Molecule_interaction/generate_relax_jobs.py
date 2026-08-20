#!/usr/bin/env python3
"""generate_relax_jobs.py — bake self-contained GPAW relax scripts + PBS for metal slabs and molecule-on-surface.

Two modes:
  1. Slab-only (default): reads systems/<Metal>/<variant>_111_3x3x3/ (from generate_metal_geometries.py)
  2. Molecule-on-surface (--molecules): reads systems/<Metal>/<variant>_<molecule>_111_3x3x3/
     (from generate_molecule_on_surface.py). Frozen indices fixed to bottom 18 atoms.

Each job:
  - Loads the geometry (CONTCAR) with cell + positions
  - Freezes bottom 2 layers (FixAtoms)
  - Runs GPAW PBE PW(400eV) gamma-point with FermiDirac(0.05) smearing + dipole correction
  - Saves relaxed.xyz, final.traj, density/potential cubes, planar averages, and ChemBook metadata

Output structure:
  jobs/  (or jobs_mol_on_surf/)
    run_<Metal>_<variant>.py          # slab-only runner
    run_<Metal>_<variant>_<mol>.py    # molecule-on-surface runner
    submit_<Metal>_<variant>.pbs      # PBS wrapper
    submit_all.sh                     # qsub all jobs

Usage:
    python generate_relax_jobs.py                           # all 16 metals, bare+adatom
    python generate_relax_jobs.py --metals Cu Ag Au --variants bare adatom \
        --molecules H2O H2S NH3 PH3 HCN CH2O CH2NH --outdir jobs_mol_on_surf
    python generate_relax_jobs.py --scf-only                # fast SCF test mode
"""

import os, sys, json, argparse, secrets
import numpy as np
from collections import Counter

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

# Metacentrum-specific settings (from doc/EVIROMENTS_AND_MACHINES/Prokop_Metacentrum.exploration.md)
GPAW_MODULE = 'py-gpaw/24.1.0-gcc-10.2.1-fojjhkw'
GPAW_SETUP_PATH = '/storage/praha1/home/prokop/gpaw-setups-24.1.0/gpaw-setups-24.1.0'
QUEUE = 'luna'

# Study metals (spec §3.2)
STUDY_METALS = ['Ti', 'V', 'Cr', 'Mn', 'Fe', 'Co', 'Ni', 'Cu',
                 'Zn', 'Mo', 'W', 'Al', 'Pd', 'Ag', 'Pt', 'Au']

# PBS resource estimates per metal group (spec §7.2)
# 3d metals: lighter, 4d/5d: ~1.5-2x more expensive
PBS_RESOURCES = {
    '3d':   {'ncpus': 8, 'mem': '32gb', 'walltime': '23:00:00', 'scratch_gb': 20},
    '4d5d': {'ncpus': 8, 'mem': '32gb', 'walltime': '23:00:00', 'scratch_gb': 20},
    'sp':   {'ncpus': 8, 'mem': '32gb', 'walltime': '23:00:00', 'scratch_gb': 20},
}

def metal_group(metal):
    if metal in ('Ti', 'V', 'Cr', 'Mn', 'Fe', 'Co', 'Ni', 'Cu', 'Zn'):
        return '3d'
    if metal in ('Mo', 'W', 'Pd', 'Ag', 'Pt', 'Au'):
        return '4d5d'
    return 'sp'

VARIANTS = ['bare', 'adatom']
COINAGE_VARIANTS = ['bare', 'adatom', 'dimer', 'trimer', 'row']
MOLECULES = ['H2O', 'H2S', 'NH3', 'PH3', 'HCN', 'CH2O', 'CH2NH']
N_FROZEN_3X3X3 = 18  # bottom 2 layers of 3x3x3 FCC(111) slab


def read_contcar(path):
    """Read VASP CONTCAR file, return (symbols, positions, cell). No ASE dependency."""
    with open(path) as f:
        lines = f.readlines()
    # VASP format: comment, scale, 3x cell vectors, element line, count line, ...
    scale = float(lines[1].strip())
    cell = np.array([[float(x) for x in lines[i].split()] for i in (2, 3, 4)]) * scale
    elements = lines[5].split()
    counts = [int(x) for x in lines[6].split()]
    syms = []
    for el, n in zip(elements, counts):
        syms.extend([el] * n)
    # Find coordinate section (skip 'Selective dynamics' line if present)
    coord_line = 7
    if lines[coord_line].strip().lower().startswith('s'):
        coord_line = 8
    coord_type = lines[coord_line].strip().lower()[0]  # 'c' or 'd'
    n_atoms = sum(counts)
    ps = np.array([[float(x) for x in lines[coord_line + 1 + i].split()[:3]]
                   for i in range(n_atoms)])
    if coord_type == 'd':  # direct/fractional → Cartesian
        ps = ps @ cell
    return syms, ps, cell


def bake_run_script(metal, variant, syms, ps, cell, frozen_indices, adatom_idx, params):
    """Bake a self-contained GPAW runner script (relax or SCF-only)."""
    ecut = params['ecut']
    xc = params['xc']
    kpts = params['kpts']
    smearing = params['smearing']
    fmax = params['fmax']
    maxsteps = params['maxsteps']
    scf_only = params.get('scf_only', False)
    n_atoms = len(syms)
    elements = dict(Counter(syms))
    chembook_id = secrets.token_hex(6)

    frozen_list = sorted(frozen_indices)
    frozen_str = ",".join(str(int(i)) for i in frozen_list)

    # Handle adatom_idx being int, list, or None
    if adatom_idx is not None and not isinstance(adatom_idx, list):
        adatom_idx = [adatom_idx]
    adatom_idx_repr = adatom_idx if adatom_idx is not None else 'None'

    job_name = f"{metal}_{variant}_111_3x3x3"
    job_type = 'scf' if scf_only else 'relax'

    # Pre-build conditional blocks to avoid f-string triple-quote conflicts
    if scf_only:
        run_block = "E = atoms.get_potential_energy()"
        converged_expr = "True"
        converged_print = "''"
    else:
        run_block = (
            "from ase.optimize import BFGS\n"
            "opt = BFGS(atoms, maxstep=0.2, logfile='-', trajectory=os.path.join(RESULTS, 'relax.traj'))\n"
            "converged = opt.run(fmax=FMAX, steps=MAXSTEPS)\n"
            "E = atoms.get_potential_energy()\n"
            "# Convert trajectory to multi-frame XYZ for Jmol\n"
            "from ase.io import read as ase_read\n"
            "traj = ase_read(os.path.join(RESULTS, 'relax.traj'), index=':')\n"
            "write(os.path.join(RESULTS, 'relax_trajectory.xyz'), traj)"
        )
        converged_expr = "bool(converged)"
        converged_print = "'  converged = ' + str(converged)"

    return f'''#!/usr/bin/env python3
"""{metal} {variant} FCC(111) 3x3x3 slab {'SCF' if scf_only else 'relaxation'} — GPAW PBE PW({int(ecut)}eV)
Auto-generated by generate_relax_jobs.py. ChemBook provenance included.

Frozen: bottom 2 layers ({len(frozen_list)} atoms)
Dipole correction: z-direction (vacuum below slab)
"""
import os, sys, json, time, socket, atexit
import numpy as np
from datetime import datetime, timezone

os.environ.setdefault('GPAW_SETUP_PATH', '{GPAW_SETUP_PATH}')

from ase import Atoms
from ase.constraints import FixAtoms
from ase.optimize import BFGS
from ase.io import write
from gpaw import GPAW, PW, FermiDirac

METAL = "{metal}"; VARIANT = "{variant}"; JOB_NAME = "{job_name}"
ECUT = {ecut}; XC = "{xc}"; KPTS = {kpts!r}; SMEARING = {smearing}
FMAX = {fmax}; MAXSTEPS = {maxsteps}
N_ATOMS = {n_atoms}; N_FROZEN = {len(frozen_list)}
FROZEN = [{frozen_str}]
ADATOM_IDX = {adatom_idx_repr}

OUTDIR = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(OUTDIR, "results_" + JOB_NAME)
os.makedirs(RESULTS, exist_ok=True)

# --- ChemBook provenance ---
_cb_path = os.path.join(RESULTS, 'chembook.json')
_cb_node = {{
    "chembook": {{"schema": "chembook.job.v0", "id": "{chembook_id}", "created": datetime.now(timezone.utc).isoformat(timespec='microseconds'), "status": "pending"}},
    "job": {{"type": "{job_type}", "name": JOB_NAME}},
    "system": {{"n_atoms": N_ATOMS, "elements": {elements!r}, "metal": METAL, "variant": VARIANT, "surface": "FCC(111)", "supercell": [3,3,3]}},
    "method": {{"code": "gpaw", "basis": "PW({int(ecut)}eV)", "method": XC, "kpts": list(KPTS), "smearing": SMEARING, "dipole": "z", "spinpol": False}},
    "provenance": {{"command": " ".join(sys.argv), "hostname": socket.gethostname(), "cwd": os.path.dirname(os.path.abspath(__file__))}},
}}
with open(_cb_path, 'w') as _cb_f:
    json.dump(_cb_node, _cb_f, indent=2)
_cb_t0 = time.perf_counter_ns()

def _cb_on_exit():
    if _cb_node["chembook"]["status"] == "pending":
        _cb_dur = (time.perf_counter_ns() - _cb_t0) / 1e9
        _cb_node["chembook"]["status"] = "failed"
        _cb_node["provenance"]["duration_sec"] = _cb_dur
        _cb_node["provenance"]["exit_code"] = 1
        with open(_cb_path, 'w') as _cb_f:
            json.dump(_cb_node, _cb_f, indent=2)
atexit.register(_cb_on_exit)
# --- end ChemBook init ---

# --- Build atoms ---
atoms = Atoms(symbols={syms!r}, positions={ps.tolist()!r}, cell={cell.tolist()!r}, pbc=[True, True, False])
atoms.set_constraint(FixAtoms(indices=FROZEN))

# --- GPAW calculator with dipole correction (z-direction via dipolelayer='xy') ---
calc = GPAW(
    mode=PW(ECUT), xc=XC, kpts=KPTS, spinpol=False, charge=0,
    symmetry='off', maxiter=333,
    occupations=FermiDirac(SMEARING),
    convergence=dict(energy=1e-5, density=1e-5, bands='occupied'),
    poissonsolver={{'dipolelayer': 'xy'}},
    txt=os.path.join(RESULTS, 'gpaw.txt'),
)
atoms.calc = calc

# --- {job_type} ---
print(f"[{{JOB_NAME}}] Starting {job_type}: {{N_ATOMS}} atoms, {{N_FROZEN}} frozen, ecut={{ECUT}}eV, kpts={{KPTS}}")
t0 = time.time()
{run_block}
t1 = time.time()
elapsed = t1 - t0

print(f"[{{JOB_NAME}}] E = {{E:.6f}} eV  time = {{elapsed:.1f}}s{{{converged_print}}}")

# --- Verify frozen atoms didn't move ---
ps_final = atoms.get_positions()
frozen_disp = float(np.max(np.linalg.norm(ps_final[FROZEN] - np.array({ps[frozen_list].tolist()!r}), axis=1)))
print(f"[{{JOB_NAME}}] max frozen displacement = {{frozen_disp:.2e}} A")

# --- Adatom displacement ---
if ADATOM_IDX is not None:
    adatom_disps = [float(np.linalg.norm(ps_final[i] - np.array({ps[adatom_idx].tolist()!r}[j]))) for j, i in enumerate(ADATOM_IDX)]
    adatom_disp = max(adatom_disps)
    print(f"[{{JOB_NAME}}] max adatom displacement = {{adatom_disp:.3f}} A")
else:
    adatom_disp = None

# --- Save outputs ---
write(os.path.join(RESULTS, 'relaxed.xyz'), atoms)
atoms.write(os.path.join(RESULTS, 'final.traj'))
print(f"[{{JOB_NAME}}] Saved: relaxed.xyz, final.traj")

# --- Write density, potential cubes + planar averages for dipole correction analysis ---
try:
    from ase.io.cube import write_cube
    rho = calc.get_pseudo_density()
    vHt = calc.get_electrostatic_potential()
    # Electron density cube (proper Gaussian cube format for VESTA)
    with open(os.path.join(RESULTS, 'density.cube'), 'w') as f:
        write_cube(f, atoms, data=rho)
    # Electrostatic potential cube
    with open(os.path.join(RESULTS, 'potential.cube'), 'w') as f:
        write_cube(f, atoms, data=vHt)
    # Planar-averaged density and potential along z (for dipole correction diagnostics)
    rho_z = rho.mean(axis=(1, 2))
    vHt_z = vHt.mean(axis=(1, 2))
    np.savez(os.path.join(RESULTS, 'planar_avg.npz'), rho_z=rho_z, vHt_z=vHt_z,
             cell_z=atoms.cell[2, 2])
    print(f"[{{JOB_NAME}}] Saved: density.cube, potential.cube, planar_avg.npz")
except Exception as e:
    print(f"[{{JOB_NAME}}] WARNING: cube/npz output failed: {{e}}")

# --- ChemBook done ---
_cb_dur = (time.perf_counter_ns() - _cb_t0) / 1e9
_cb_node["chembook"]["status"] = "done"
_cb_node["provenance"]["duration_sec"] = _cb_dur
_cb_node["provenance"]["exit_code"] = 0
_cb_node["results"] = {{
    "energy_eV": float(E), "elapsed_s": elapsed, "converged": {converged_expr},
    "max_frozen_disp_A": frozen_disp, "adatom_disp_A": adatom_disp,
}}
with open(_cb_path, 'w') as _cb_f:
    json.dump(_cb_node, _cb_f, indent=2)
print(f"[{{JOB_NAME}}] Done. chembook.json written.")
'''


def bake_pbs_script(metal, variant, spec, script_name, scratch_gb, scf_only=False):
    """Bake a PBS submission script for Metacentrum."""
    job_type = 'scf' if scf_only else 'relax'
    job_name = f"{job_type}_{metal}_{variant}"
    walltime = '00:30:00' if scf_only else spec['walltime']
    return f'''#!/bin/bash
#PBS -N {job_name}
#PBS -l select=1:ncpus={spec['ncpus']}:mem={spec['mem']}:scratch_local={scratch_gb}gb
#PBS -l walltime={walltime}
#PBS -j oe
#PBS -q {QUEUE}
#PBS -m bae

# {metal} {variant} FCC(111) 3x3x3 slab {job_type}
# {spec['ncpus']} CPUs, {spec['mem']} RAM, {spec['walltime']}

trap 'cp -r $SCRATCHDIR/* $PBS_O_WORKDIR/ 2>/dev/null; rm -rf $SCRATCHDIR/* 2>/dev/null' EXIT

cd $PBS_O_WORKDIR
module purge
module add {GPAW_MODULE}
export GPAW_SETUP_PATH={GPAW_SETUP_PATH}
export OMP_NUM_THREADS=1
export PYTHONUNBUFFERED=1

echo "=== {job_name} === $(date)"
echo "Node: $(hostname)"
echo "CPUs: $PBS_NUM_PPN"

cp $PBS_O_WORKDIR/{script_name} $SCRATCHDIR/
cd $SCRATCHDIR
export TMPDIR=$SCRATCHDIR
export TMP=$SCRATCHDIR
export TEMP=$SCRATCHDIR

mpirun -np $PBS_NUM_PPN python3 {script_name} 2>&1

echo "Finished: $(date)"
cp -r $SCRATCHDIR/results_* $PBS_O_WORKDIR/ 2>/dev/null
'''


def main():
    parser = argparse.ArgumentParser(description='Bake GPAW relax jobs for metal slabs (Metacentrum)')
    parser.add_argument('--metals', nargs='*', default=STUDY_METALS, help='Metal symbols (default: all 16)')
    parser.add_argument('--variants', nargs='*', default=VARIANTS, help='Variants (default: bare adatom)')
    parser.add_argument('--molecules', nargs='*', default=None, help='Molecules to place on surface (e.g. H2O NH3). If given, generates molecule-on-surface jobs.')
    parser.add_argument('--ecut', type=float, default=400.0, help='PW cutoff in eV (default: 400)')
    parser.add_argument('--kpts', type=int, nargs=3, default=[1, 1, 1], help='K-points (default: 1 1 1 = gamma)')
    parser.add_argument('--xc', type=str, default='PBE', help='XC functional (default: PBE)')
    parser.add_argument('--smearing', type=float, default=0.05, help='Fermi-Dirac smearing in eV (default: 0.05)')
    parser.add_argument('--fmax', type=float, default=0.05, help='Force convergence in eV/A (default: 0.05)')
    parser.add_argument('--maxsteps', type=int, default=200, help='Max relax steps (default: 200)')
    parser.add_argument('--scf-only', action='store_true', help='SCF single-point only (no relaxation) — fast test mode')
    parser.add_argument('--coinage', action='store_true', help='Use all 5 coinage variants: bare adatom dimer trimer row')
    parser.add_argument('--outdir', default=None, help='Output directory (default: ./jobs)')
    args = parser.parse_args()

    project_dir = os.path.dirname(os.path.abspath(__file__))
    systems_dir = os.path.join(project_dir, 'systems')
    out_dir = args.outdir or os.path.join(project_dir, 'jobs')
    os.makedirs(out_dir, exist_ok=True)

    variants = COINAGE_VARIANTS if args.coinage else args.variants
    molecules = args.molecules
    params = dict(ecut=args.ecut, xc=args.xc, kpts=tuple(args.kpts),
                  smearing=args.smearing, fmax=args.fmax, maxsteps=args.maxsteps,
                  scf_only=args.scf_only)

    print("=" * 70)
    print("Baking GPAW relax jobs for metal slabs")
    print(f"  Metals: {args.metals}")
    print(f"  Variants: {variants}")
    if molecules:
        print(f"  Molecules: {molecules}")
    print(f"  Mode: {'SCF only' if args.scf_only else 'Relaxation'}")
    print(f"  ecut={args.ecut} eV, kpts={tuple(args.kpts)}, xc={args.xc}, smearing={args.smearing}")
    print(f"  fmax={args.fmax}, maxsteps={args.maxsteps}")
    print(f"  Systems: {systems_dir}")
    print(f"  Output: {out_dir}")
    print("=" * 70)

    pbs_paths = []
    n_baked = 0

    for metal in args.metals:
        grp = metal_group(metal)
        spec = PBS_RESOURCES[grp]
        scratch_gb = spec['scratch_gb']

        for variant in variants:
            if molecules:
                # Molecule-on-surface jobs: iterate over molecules
                for mol_name in molecules:
                    job_subdir = f'{variant}_{mol_name}_111_3x3x3'
                    job_dir = os.path.join(systems_dir, metal, job_subdir)
                    contcar = os.path.join(job_dir, 'input', 'CONTCAR')

                    if not os.path.exists(contcar):
                        print(f"  SKIP: {contcar} not found")
                        continue

                    syms, ps, cell = read_contcar(contcar)
                    frozen_indices = list(range(N_FROZEN_3X3X3))
                    # Find adatom index: highest-z metal atom
                    if variant == 'adatom':
                        metal_z = [(ps[i, 2], i) for i, s in enumerate(syms) if s == metal]
                        metal_z.sort(reverse=True)
                        adatom_idx = metal_z[0][1]
                    else:
                        adatom_idx = None

                    job_variant = f'{variant}_{mol_name}'
                    script_name = f'run_{metal}_{job_variant}.py'
                    script_path = os.path.join(out_dir, script_name)
                    script_content = bake_run_script(metal, job_variant, syms, ps, cell,
                                                     frozen_indices, adatom_idx, params)
                    with open(script_path, 'w') as f:
                        f.write(script_content)
                    os.chmod(script_path, 0o755)

                    pbs_name = f'submit_{metal}_{job_variant}.pbs'
                    pbs_path = os.path.join(out_dir, pbs_name)
                    pbs_content = bake_pbs_script(metal, job_variant, spec, script_name, scratch_gb, scf_only=args.scf_only)
                    with open(pbs_path, 'w') as f:
                        f.write(pbs_content)
                    os.chmod(pbs_path, 0o755)
                    pbs_paths.append(pbs_path)

                    n_baked += 1
                    print(f"  {metal:4s} {job_variant:15s}  atoms={len(syms):2d}  frozen={len(frozen_indices):2d}  "
                          f"cpus={spec['ncpus']:2d}  mem={spec['mem']:5s}  {spec['walltime']}")
            else:
                # Slab-only jobs (original behavior)
                job_dir = os.path.join(systems_dir, metal, f'{variant}_111_3x3x3')
                contcar = os.path.join(job_dir, 'input', 'CONTCAR')
                meta_path = os.path.join(job_dir, 'meta.json')

                if not os.path.exists(contcar):
                    print(f"  SKIP: {contcar} not found")
                    continue

                syms, ps, cell = read_contcar(contcar)

                with open(meta_path) as f:
                    meta = json.load(f)
                frozen_indices = meta['geometry']['frozen_indices']
                adatom_idx = meta['geometry'].get('adatom_index', None)

                script_name = f'run_{metal}_{variant}.py'
                script_path = os.path.join(out_dir, script_name)
                script_content = bake_run_script(metal, variant, syms, ps, cell,
                                                 frozen_indices, adatom_idx, params)
                with open(script_path, 'w') as f:
                    f.write(script_content)
                os.chmod(script_path, 0o755)

                pbs_name = f'submit_{metal}_{variant}.pbs'
                pbs_path = os.path.join(out_dir, pbs_name)
                pbs_content = bake_pbs_script(metal, variant, spec, script_name, scratch_gb, scf_only=args.scf_only)
                with open(pbs_path, 'w') as f:
                    f.write(pbs_content)
                os.chmod(pbs_path, 0o755)
                pbs_paths.append(pbs_path)

                n_baked += 1
                print(f"  {metal:4s} {variant:7s}  atoms={len(syms):2d}  frozen={len(frozen_indices):2d}  "
                      f"cpus={spec['ncpus']:2d}  mem={spec['mem']:5s}  {spec['walltime']}")

    # Write submit_all.sh
    submit_all = os.path.join(out_dir, 'submit_all.sh')
    with open(submit_all, 'w') as f:
        f.write('#!/bin/bash\n# Submit all metal slab relaxation jobs\nset -euo pipefail\n')
        for p in pbs_paths:
            f.write(f'qsub {os.path.basename(p)}\n')
    os.chmod(submit_all, 0o755)

    print(f"\nBaked {n_baked} jobs in {out_dir}")
    print(f"  Submit all:  cd {out_dir} && bash submit_all.sh")
    print(f"  Submit one:  cd {out_dir} && qsub submit_Cu_bare.pbs")
    if args.scf_only:
        print(f"  (SCF-only mode: fast test, ~2-5 min per job)")


if __name__ == '__main__':
    main()
