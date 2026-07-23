#!/usr/bin/env python3
"""Generate baked GPAW single-point scripts for Fukui density calculations.

Uses the shared bake_jobs infrastructure from py/tasks/bake_jobs.py.
Only the GPAW-specific run script template is defined here.

Usage:
    python generate_jobs.py                          # default: ecut=500, vacuum=12
    python generate_jobs.py --ecut 500 --vacuum 12   # production
    python generate_jobs.py --ecut 200 --vacuum 8    # quick test
"""

import os, sys, argparse
import numpy as np

# Add repo root to path so we can import py.tasks.bake_jobs
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))

from py.tasks.bake_jobs import bake_fukui_jobs, read_xyz, box_positions, spin_for_charge, B2A

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GEOM_DIR = os.path.join(SCRIPT_DIR, 'geometries')
JOBS_DIR = os.path.join(SCRIPT_DIR, 'jobs')

MOLECULES = {
    'H2O':       {'natoms': 3,  'nelec': 10,  'ncpus': 4,  'mem': '8gb',   'walltime': '02:00:00'},
    'CH2O':      {'natoms': 4,  'nelec': 12,  'ncpus': 4,  'mem': '8gb',   'walltime': '02:00:00'},
    'CH2NH':     {'natoms': 5,  'nelec': 14,  'ncpus': 4,  'mem': '8gb',   'walltime': '02:00:00'},
    'C2H4':      {'natoms': 6,  'nelec': 12,  'ncpus': 4,  'mem': '8gb',   'walltime': '02:00:00'},
    'pyrrol':    {'natoms': 10, 'nelec': 26,  'ncpus': 8,  'mem': '16gb',  'walltime': '04:00:00'},
    'pyridine':  {'natoms': 11, 'nelec': 26,  'ncpus': 8,  'mem': '16gb',  'walltime': '04:00:00'},
    'pentacene': {'natoms': 36, 'nelec': 156, 'ncpus': 16, 'mem': '32gb',  'walltime': '12:00:00'},
    'PTCDA':     {'natoms': 38, 'nelec': 188, 'ncpus': 16, 'mem': '32gb',  'walltime': '12:00:00'},
}


def bake_gpaw_run_script(mol, syms, ps, tag, charge, spec, params):
    """GPAW-specific run script template. ps is already boxed with vacuum."""
    ecut = params['ecut']; xc = params['xc']; vacuum = params['vacuum']
    cell = params['cell']
    spinpol = spin_for_charge(spec['nelec'], charge) != 0
    outdir = f"results/{mol}_{xc}_{int(ecut)}eV"
    return f'''#!/usr/bin/env python3
"""{mol} {tag} — GPAW {xc} PW({int(ecut)}eV) charge={charge} spinpol={spinpol}
Auto-generated. Saves raw electron density and ESP as .npy.
"""
import os, numpy as np
os.environ.setdefault('GPAW_SETUP_PATH', '/storage/praha1/home/prokop/gpaw-setups-24.1.0/gpaw-setups-24.1.0')
from ase import Atoms
from gpaw import GPAW, PW, FermiDirac

MOL = "{mol}"; TAG = "{tag}"; CHARGE = {charge}; SPINPOL = {spinpol}
ECUT = {ecut}; XC = "{xc}"
B2A = {B2A}

OUTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "{outdir}")
os.makedirs(OUTDIR, exist_ok=True)

atoms = Atoms(symbols={syms!r}, positions={ps.tolist()!r}, cell={cell.tolist()!r}, pbc=True)
calc = GPAW(mode=PW(ECUT), xc=XC, charge=CHARGE, spinpol=SPINPOL,
            occupations=FermiDirac(0.05), kpts=(1,1,1), symmetry='off',
            convergence=dict(energy=1e-5, density=1e-5, bands='occupied'),
            txt=os.path.join(OUTDIR, TAG + '.txt'))
atoms.calc = calc
E = atoms.get_potential_energy()
print(f"[{{MOL}}/{{TAG}}] E = {{E:.6f}} eV")

# Save raw all-electron density (Å⁻³) as npy
rho = calc.get_all_electron_density()
np.save(os.path.join(OUTDIR, f'rho_{{TAG}}.npy'), rho)
print(f"  Saved rho_{{TAG}}.npy  shape={{rho.shape}}")

# Save electrostatic potential (Hartree + nuclear, in eV)
esp = calc.get_electrostatic_potential()
np.save(os.path.join(OUTDIR, f'esp_{{TAG}}.npy'), esp)
print(f"  Saved esp_{{TAG}}.npy  shape={{esp.shape}}")
'''


def results_subdir(mol, params):
    return f"{mol}_{params['xc']}_{int(params['ecut'])}eV"


def main():
    parser = argparse.ArgumentParser(description='Generate baked GPAW Fukui density scripts')
    parser.add_argument('--ecut', type=float, default=500.0)
    parser.add_argument('--vacuum', type=float, default=12.0)
    parser.add_argument('--xc', type=str, default='PBE')
    args = parser.parse_args()

    params = dict(ecut=args.ecut, vacuum=args.vacuum, xc=args.xc)
    print(f"Generating jobs: ecut={args.ecut} vacuum={args.vacuum} xc={args.xc}")
    print(f"Output: {JOBS_DIR}/\n")

    bake_fukui_jobs(
        molecules=MOLECULES,
        geom_dir=GEOM_DIR,
        out_dir=JOBS_DIR,
        bake_run_fn=bake_gpaw_run_script,
        results_subdir_fn=results_subdir,
        job_prefix='fukui',
        module_name='py-gpaw/24.1.0-gcc-10.2.1-fojjhkw',
        mpi=True,
        mpi_runner='python3',
        omp_threads='1',
        scratch_gb=10,
        params=params,
        box_vacuum=args.vacuum,
    )


if __name__ == '__main__':
    main()
