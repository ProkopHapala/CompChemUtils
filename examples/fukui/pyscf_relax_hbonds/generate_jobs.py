#!/usr/bin/env python3
"""Generate baked PySCF geometry optimization scripts for H-bonded dimers.

Uses PBE/def2-SVP. Geometries are pre-flattened (z=0).
Outputs optimized XYZ + chembook.json per job.

Usage:
    python generate_jobs.py                              # default: def2-SVP, PBE
    python generate_jobs.py --basis def2-TZVP --xc PBE   # triple-zeta
"""

import os, sys, argparse
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))

from py.tasks.bake_jobs import bake_relax_jobs, bake_chembook_init_code, bake_chembook_done_code

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GEOM_DIR = os.path.join(SCRIPT_DIR, 'geometries')
JOBS_DIR = os.path.join(SCRIPT_DIR, 'jobs')

MOLECULES = {
    'adenine-uracil':      {'natoms': 27, 'nelec': 128, 'ncpus': 8, 'mem': '16gb', 'walltime': '08:00:00', 'scratch_gb': 20},
    'adenine-uracil-iso':  {'natoms': 27, 'nelec': 128, 'ncpus': 8, 'mem': '16gb', 'walltime': '08:00:00', 'scratch_gb': 20},
    'azaindol_dimer':      {'natoms': 30, 'nelec': 123, 'ncpus': 8, 'mem': '16gb', 'walltime': '08:00:00', 'scratch_gb': 20},
    'azaindol_isodimer':   {'natoms': 30, 'nelec': 123, 'ncpus': 8, 'mem': '16gb', 'walltime': '08:00:00', 'scratch_gb': 20},
}


def bake_pyscf_relax_script(mol, syms, ps, spec, params):
    """PySCF geometry optimization script template (PBE/def2-SVP)."""
    basis = params['basis']; xc = params['xc']
    outdir = f"results/{mol}_{xc}_{basis}"

    geom_lines = []
    for s, p in zip(syms, ps):
        geom_lines.append(f'    "{s} {p[0]:.6f} {p[1]:.6f} {p[2]:.6f}"')
    geom_str = ',\n'.join(geom_lines)

    chembook_id = params.get('chembook_id')
    if chembook_id:
        elements = dict(Counter(syms))
        cb_init = bake_chembook_init_code(chembook_id, spec['natoms'], elements, 'pyscf', 'relax', basis, xc)
        cb_done = bake_chembook_done_code(energy_expr='E_opt', energy_unit='Ha')
    else:
        cb_init = ''; cb_done = ''

    result = f'''#!/usr/bin/env python3
"""{mol} — PySCF geometry optimization {xc}/{basis}
Auto-generated. Uses scipy L-BFGS-B with PySCF analytical gradients.
Saves optimized geometry as XYZ.
"""
import os, numpy as np
from scipy.optimize import minimize
from pyscf import gto, dft

MOL = "{mol}"; TAG = "relax"; CHARGE = 0; SPIN = 0
BASIS = "{basis}"; XC = "{xc}"
FMAX = 0.01  # eV/A ~ 0.00038 Ha/Bohr

OUTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "{outdir}")
os.makedirs(OUTDIR, exist_ok=True)
@@CHEMBOOK_INIT@@

SYMS = {syms!r}
POS0 = np.array({ps.tolist()!r})

def make_mf(syms, pos):
    atom_str = '; '.join(f"{{s}} {{p[0]:.8f}} {{p[1]:.8f}} {{p[2]:.8f}}" for s, p in zip(syms, pos))
    mol = gto.M(atom=atom_str, basis=BASIS, charge=CHARGE, spin=SPIN, unit='Angstrom', verbose=0)
    mf = dft.RKS(mol); mf.xc = XC; mf.verbose = 0
    return mol, mf

def relax(syms, pos0):
    natm = len(syms)
    x0 = pos0.ravel()
    def fun(x):
        pos = x.reshape(natm, 3)
        _, mf = make_mf(syms, pos)
        e = mf.kernel()
        g = mf.nuc_grad_method().kernel().ravel()
        return e, g
    res = minimize(fun, x0, method='L-BFGS-B', jac=True,
                   options={{'maxiter': 200, 'gtol': FMAX}})
    if not res.success:
        print(f"  [warn] relax: {{res.message}}")
    return res.x.reshape(natm, 3), float(res.fun)

print(f"[{{MOL}}] Starting geometry optimization {{XC}}/{{BASIS}}...")
pos_opt, E_opt = relax(SYMS, POS0)
print(f"[{{MOL}}] Optimized E = {{E_opt:.6f}} Ha")

# Save optimized geometry as XYZ
xyz_path = os.path.join(OUTDIR, f'{{MOL}}_opt.xyz')
with open(xyz_path, 'w') as f:
    f.write(f"{{len(SYMS)}}\\n")
    f.write(f"{{MOL}} optimized {{XC}}/{{BASIS}} E={{E_opt:.6f}} Ha\\n")
    for s, (x, y, z) in zip(SYMS, pos_opt):
        f.write(f"{{s:2s}} {{x:12.6f}} {{y:12.6f}} {{z:12.6f}}\\n")
print(f"  Saved: {{xyz_path}}")
@@CHEMBOOK_DONE@@
'''
    return result.replace('@@CHEMBOOK_INIT@@', cb_init).replace('@@CHEMBOOK_DONE@@', cb_done)


def main():
    parser = argparse.ArgumentParser(description='Generate baked PySCF geometry optimization scripts')
    parser.add_argument('--basis', type=str, default='def2-SVP', help='Basis set (default: def2-SVP)')
    parser.add_argument('--xc', type=str, default='PBE', help='XC functional (default: PBE)')
    args = parser.parse_args()

    params = dict(basis=args.basis, xc=args.xc)
    print(f"Generating geometry optimization jobs: basis={args.basis} xc={args.xc}")
    print(f"Output: {JOBS_DIR}/\n")

    bake_relax_jobs(
        molecules=MOLECULES,
        geom_dir=GEOM_DIR,
        out_dir=JOBS_DIR,
        bake_run_fn=bake_pyscf_relax_script,
        job_prefix='pyscf_relax',
        module_name='mambaforge',
        omp_threads='$PBS_NUM_PPN',
        params=params,
    )


if __name__ == '__main__':
    main()
