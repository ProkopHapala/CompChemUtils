#!/usr/bin/env python3
"""Generate baked PySCF single-point scripts for Fukui density calculations.

Uses the shared bake_jobs infrastructure from py/tasks/bake_jobs.py.
Only the PySCF-specific run script template is defined here.

Usage:
    python generate_jobs.py                              # default: def2-SVP, PBE
    python generate_jobs.py --basis def2-TZVP --xc PBE   # triple-zeta
    python generate_jobs.py --basis def2-SVP --xc B3LYP  # different functional
"""

import os, sys, argparse

# Add repo root to path so we can import py.tasks.bake_jobs
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))

from py.tasks.bake_jobs import bake_fukui_jobs, spin_for_charge

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GEOM_DIR = os.path.join(SCRIPT_DIR, 'geometries')
JOBS_DIR = os.path.join(SCRIPT_DIR, 'jobs')

MOLECULES = {
    'H2O':       {'natoms': 3,  'nelec': 10,  'ncpus': 4,  'mem': '8gb',   'walltime': '01:00:00'},
    'CH2O':      {'natoms': 4,  'nelec': 12,  'ncpus': 4,  'mem': '8gb',   'walltime': '01:00:00'},
    'CH2NH':     {'natoms': 5,  'nelec': 14,  'ncpus': 4,  'mem': '8gb',   'walltime': '01:00:00'},
    'C2H4':      {'natoms': 6,  'nelec': 12,  'ncpus': 4,  'mem': '8gb',   'walltime': '01:00:00'},
    'pyrrol':    {'natoms': 10, 'nelec': 26,  'ncpus': 4,  'mem': '8gb',   'walltime': '02:00:00'},
    'pyridine':  {'natoms': 11, 'nelec': 26,  'ncpus': 4,  'mem': '8gb',   'walltime': '02:00:00'},
    'pentacene': {'natoms': 36, 'nelec': 156, 'ncpus': 8,  'mem': '16gb',  'walltime': '08:00:00'},
    'PTCDA':     {'natoms': 38, 'nelec': 188, 'ncpus': 8,  'mem': '16gb',  'walltime': '08:00:00'},
}


def bake_pyscf_run_script(mol, syms, ps, tag, charge, spec, params):
    """PySCF-specific run script template. No vacuum box needed."""
    basis = params['basis']; xc = params['xc']
    resolution = params['resolution']; margin = params['margin']
    spin = spin_for_charge(spec['nelec'], charge)
    outdir = f"results/{mol}_{xc}_{basis}"

    geom_lines = []
    for s, p in zip(syms, ps):
        geom_lines.append(f'    "{s} {p[0]:.6f} {p[1]:.6f} {p[2]:.6f}"')
    geom_str = ',\n'.join(geom_lines)

    return f'''#!/usr/bin/env python3
"""{mol} {tag} — PySCF {xc}/{basis} charge={charge} spin={spin}
Auto-generated. Saves electron density as .cube and .npy.
"""
import os, numpy as np
from pyscf import gto, dft
from pyscf.tools import cubegen

MOL = "{mol}"; TAG = "{tag}"; CHARGE = {charge}; SPIN = {spin}
BASIS = "{basis}"; XC = "{xc}"
RESOLUTION = {resolution}; MARGIN = {margin}

OUTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "{outdir}")
os.makedirs(OUTDIR, exist_ok=True)

mol = gto.Mole(
    atom=[
{geom_str}
    ],
    basis=BASIS, charge=CHARGE, spin=SPIN, unit='Angstrom',
)
mol.build()

mf = dft.RKS(mol) if SPIN == 0 else dft.UKS(mol)
mf.xc = XC
mf.kernel()
print(f"[{{MOL}}/{{TAG}}] E = {{mf.e_tot:.6f}} Ha")

# Write density cube
dm = mf.make_rdm1()
if dm.ndim == 3:  # UKS: sum alpha+beta
    dm = dm[0] + dm[1]
cube_path = os.path.join(OUTDIR, f'rho_{{TAG}}.cube')
cubegen.density(mol, cube_path, dm, resolution=RESOLUTION, margin=MARGIN)
print(f"  Cube: {{cube_path}}")

# Read cube back and save as npy
with open(cube_path, 'r') as f:
    f.readline(); f.readline()
    parts = f.readline().split(); natm = int(parts[0])
    origin = [float(parts[1]), float(parts[2]), float(parts[3])]
    nx = int(f.readline().split()[0])
    ny = int(f.readline().split()[0])
    nz = int(f.readline().split()[0])
    for _ in range(natm): f.readline()
    data = np.fromfile(f, sep=' ')
data = data.reshape(nx, ny, nz)
np.save(os.path.join(OUTDIR, f'rho_{{TAG}}.npy'), data)
print(f"  Npy:  rho_{{TAG}}.npy  shape={{data.shape}}")
'''


def results_subdir(mol, params):
    return f"{mol}_{params['xc']}_{params['basis']}"


def main():
    parser = argparse.ArgumentParser(description='Generate baked PySCF Fukui density scripts')
    parser.add_argument('--basis', type=str, default='def2-SVP', help='Basis set (default: def2-SVP)')
    parser.add_argument('--xc', type=str, default='PBE', help='XC functional (default: PBE)')
    parser.add_argument('--resolution', type=float, default=0.15, help='Cube grid resolution in Bohr (default: 0.15)')
    parser.add_argument('--margin', type=float, default=4.0, help='Cube grid margin in Bohr (default: 4.0)')
    args = parser.parse_args()

    params = dict(basis=args.basis, xc=args.xc, resolution=args.resolution, margin=args.margin)
    print(f"Generating jobs: basis={args.basis} xc={args.xc} resolution={args.resolution} margin={args.margin}")
    print(f"Output: {JOBS_DIR}/\n")

    bake_fukui_jobs(
        molecules=MOLECULES,
        geom_dir=GEOM_DIR,
        out_dir=JOBS_DIR,
        bake_run_fn=bake_pyscf_run_script,
        results_subdir_fn=results_subdir,
        job_prefix='pyscf_fukui',
        module_name='mambaforge',
        mpi=False,
        omp_threads='$PBS_NUM_PPN',
        scratch_gb=5,
        params=params,
        box_vacuum=None,
    )


if __name__ == '__main__':
    main()
