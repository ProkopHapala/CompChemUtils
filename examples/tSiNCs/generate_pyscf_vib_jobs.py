#!/usr/bin/env python3
"""Generate baked PySCF relax + vibration jobs for OUT_small_nc nanocrystals.

Reads init.xyz geometries from FireCore OUT_small_nc, writes standalone cluster
scripts (numpy + scipy + pyscf only) and PBS submit files.

Usage:
    python generate_pyscf_vib_jobs.py
    python generate_pyscf_vib_jobs.py --geom-root /path/to/OUT_small_nc --out-dir jobs_vib
    python generate_pyscf_vib_jobs.py --cases Si_R3p8 SiH4
"""

import os, sys, argparse, shutil

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, REPO)

from py.tasks.bake_jobs import discover_init_xyz_cases, bake_vibration_jobs

DEFAULT_GEOM_ROOT = '/home/prokop/git/FireCore/tests/tSiNCs/OUT_small_nc'
DEFAULT_OUT_DIR = os.path.join(os.path.dirname(__file__), 'jobs_pyscf_vib_OUT_small_nc')
README_TEMPLATE = os.path.join(os.path.dirname(__file__), 'pyscf_vib_jobs.README.md')


def bake_pyscf_vib_script(case_id, syms, ps, spec, params):
    """Standalone relax + Hessian + modes. Deps: numpy, scipy, pyscf."""
    xc = params.get('xc', 'pbe')
    basis = params.get('basis', 'def2svp')
    auxbasis = params.get('auxbasis', 'def2-universal-jfit')
    grid_level = params.get('grid_level', 1)
    ecp_elements = params.get('ecp_elements', ('Si', 'C'))
    fmax = params.get('fmax', 0.01)

    geom_lines = []
    for s, p in zip(syms, ps):
        geom_lines.append(f'    ("{s}", np.array([{p[0]:.8f}, {p[1]:.8f}, {p[2]:.8f}])),')
    geom_block = '\n'.join(geom_lines)
    ecp_tuple = ', '.join(f'"{e}"' for e in ecp_elements)

    return f'''#!/usr/bin/env python3
"""{case_id} — PySCF {xc}/{basis} relax + Hessian + vibrations. Auto-generated.
Deps: numpy, scipy, pyscf (pip install pyscf).
"""
import os, json, time
import numpy as np
from scipy.optimize import minimize
from pyscf import gto, dft
from pyscf.hessian import thermo

CASE = "{case_id}"
XC = "{xc}"
BASIS = "{basis}"
AUXBASIS = "{auxbasis}"
GRID_LEVEL = {grid_level}
ECP_ELEMENTS = ({ecp_tuple})
FMAX = {fmax}

INIT_GEOM = [
{geom_block}
]

OUTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", CASE)
os.makedirs(OUTDIR, exist_ok=True)


def basis_dict(syms):
    return {{s: BASIS for s in set(syms)}}


def ecp_dict(syms):
    d = {{}}
    for s in set(syms):
        if s in ECP_ELEMENTS:
            d[s] = 'ccecp'
    return d or None


def atom_str(syms, pos):
    return '; '.join(f'{{s}} {{x:.8f}} {{y:.8f}} {{z:.8f}}' for s, (x, y, z) in zip(syms, pos))


def make_mf(syms, pos):
    kwargs = dict(atom=atom_str(syms, pos), basis=basis_dict(syms), charge=0, spin=0, verbose=0)
    ecp = ecp_dict(syms)
    if ecp:
        kwargs['ecp'] = ecp
    mol = gto.M(**kwargs)
    mf = dft.RKS(mol)
    mf.xc = XC
    mf = mf.density_fit(auxbasis=AUXBASIS)
    mf.grids.level = GRID_LEVEL
    mf.conv_tol = 1e-8
    mf.conv_tol_grad = 1e-6
    return mol, mf


def write_xyz(path, syms, pos, comment='relaxed'):
    with open(path, 'w') as f:
        f.write(f'{{len(syms)}}\\n{{comment}}\\n')
        for s, (x, y, z) in zip(syms, pos):
            f.write(f'{{s:2s}} {{x:12.6f}} {{y:12.6f}} {{z:12.6f}}\\n')


def relax(syms, pos0):
    natm = len(syms)
    x0 = pos0.ravel()

    def objective(x):
        pos = x.reshape(natm, 3)
        _, mf = make_mf(syms, pos)
        e = mf.kernel()
        g = mf.nuc_grad_method().kernel().ravel()
        return e, g

    def fun(x):
        e, g = objective(x)
        return e, g

    res = minimize(fun, x0, method='L-BFGS-B', jac=True,
                   options={{'maxiter': 200, 'gtol': FMAX}})
    if not res.success:
        print(f"  [warn] relax: {{res.message}}")
    return res.x.reshape(natm, 3), float(res.fun)


def main():
    t0 = time.time()
    syms = [s for s, _ in INIT_GEOM]
    pos0 = np.array([p for _, p in INIT_GEOM])
    print(f"[{{CASE}}] natoms={{len(syms)}} xc={{XC}} basis={{BASIS}} grid={{GRID_LEVEL}}")

    print("  [relax] L-BFGS-B + PySCF gradients...")
    pos, e_relax = relax(syms, pos0)
    write_xyz(os.path.join(OUTDIR, 'relaxed.xyz'), syms, pos, f'relaxed {{XC}}/{{BASIS}}')
    print(f"  [relax] E={{e_relax:.8f}} Ha")

    print("  [hess] SCF + analytical Hessian...")
    mol, mf = make_mf(syms, pos)
    mf.kernel()
    hess = mf.Hessian().kernel()
    np.save(os.path.join(OUTDIR, 'hessian.npy'), hess)

    thermo_out = thermo.harmonic_analysis(mol, hess)
    freqs = thermo_out['freq_wavenumber']
    modes = thermo_out['norm_mode']
    masses = np.array(mol.atom_mass_list())
    np.save(os.path.join(OUTDIR, 'frequencies_cm1.npy'), freqs)
    np.save(os.path.join(OUTDIR, 'modes.npy'), modes)
    np.save(os.path.join(OUTDIR, 'masses.npy'), masses)

    freqs_real = freqs.real if np.iscomplexobj(freqs) else freqs
    status = {{
        'case': CASE, 'xc': XC, 'basis': BASIS, 'grid_level': GRID_LEVEL,
        'natoms': len(syms), 'nmodes': int(len(freqs)),
        'energy_Ha': float(mf.e_tot), 'elapsed_s': round(time.time() - t0, 1),
        'freqs_cm1': [float(f) for f in freqs_real],
        'status': 'ok',
    }}
    with open(os.path.join(OUTDIR, 'status.json'), 'w') as f:
        json.dump(status, f, indent=2)

    vibr = [f for f in freqs_real if f > 10]
    print(f"  [done] {{len(vibr)}} modes > 10 cm-1, elapsed={{status['elapsed_s']}}s")
    print(f"  -> {{OUTDIR}}")


if __name__ == '__main__':
    main()
'''


def main():
    ap = argparse.ArgumentParser(description='Bake PySCF vib jobs for OUT_small_nc crystals')
    ap.add_argument('--geom-root', default=DEFAULT_GEOM_ROOT, help='OUT_small_nc root (init.xyz tree)')
    ap.add_argument('--out-dir', default=DEFAULT_OUT_DIR, help='Output jobs directory')
    ap.add_argument('--cases', nargs='+', default=None, help='Subset of case ids (e.g. Si_R3p8 SiH4)')
    ap.add_argument('--xc', default='pbe')
    ap.add_argument('--basis', default='def2svp')
    ap.add_argument('--grid-level', type=int, default=1)
    ap.add_argument('--job-prefix', default='nc_vib')
    args = ap.parse_args()

    all_cases = discover_init_xyz_cases(args.geom_root)
    if args.cases:
        want = set(args.cases)
        all_cases = [(c, p) for c, p in all_cases if c in want]
        missing = want - {c for c, _ in all_cases}
        if missing:
            print(f"WARNING: cases not found: {missing}")

    if not all_cases:
        print(f"No init.xyz found under {args.geom_root}")
        return 1

    params = dict(xc=args.xc, basis=args.basis, grid_level=args.grid_level)
    print(f"Generating {len(all_cases)} jobs -> {args.out_dir}")
    print(f"  xc={args.xc} basis={args.basis} grid={args.grid_level}\n")

    bake_vibration_jobs(
        all_cases, args.out_dir, bake_pyscf_vib_script,
        job_prefix=args.job_prefix, params=params,
    )
    if os.path.isfile(README_TEMPLATE):
        shutil.copy2(README_TEMPLATE, os.path.join(args.out_dir, 'README.md'))
        print(f"  README -> {args.out_dir}/README.md")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
