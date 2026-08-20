#!/usr/bin/env python3
"""benchmark_cu_relax.py — benchmark Cu bare + adatom slab relaxation.

Phase 1 step 4 (spec §11.1): validate the relaxation infrastructure with
Cu(111) 3×3×3 bare and adatom slabs at gamma-point, PBE, dipole correction.

Measures: time, final energy, frozen-atom displacement, adatom position.
Verifies: relaxation converges, frozen atoms don't move, adatom stays on fcc hollow.

Usage:
    python benchmark_cu_relax.py                      # local GPAW
    python benchmark_cu_relax.py --mode export        # export runner scripts
    python benchmark_cu_relax.py --metals Cu Ag       # benchmark more metals
"""

import os, sys, time, argparse, json
import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from py.tasks.metal_tip import load_slab_from_job, build_relax_backend, relax_metal_system


def benchmark_one(metal, variant, systems_dir, mode='local', outdir=None,
                  ecut=400.0, kpts=(1, 1, 1), fmax=0.05, maxsteps=100):
    """Benchmark a single metal slab relaxation."""
    job_dir = os.path.join(systems_dir, metal, f'{variant}_111_3x3x3')
    if not os.path.isdir(job_dir):
        print(f"  SKIP: {job_dir} not found")
        return None

    # Load geometry
    slab, frozen, adatoms, meta = load_slab_from_job(job_dir)
    print(f"\n{'='*60}")
    print(f"Benchmark: {metal}/{variant}")
    print(f"  Atoms: {len(slab)}, Frozen: {len(frozen)}, Adatoms: {adatoms}")
    print(f"  Cell z: {slab.cell[2,2]:.2f} Å")

    # Build backend
    backend = build_relax_backend(xc='PBE', ecut=ecut, kpts=kpts, dipole='z')
    print(f"  Backend: {backend.name}, ecut={ecut}, kpts={kpts}, dipole={backend.dipole}")

    # Output directory
    if outdir is None:
        outdir = os.path.join(os.path.dirname(__file__), 'benchmark', f'{metal}_{variant}')
    os.makedirs(outdir, exist_ok=True)

    # Record initial adatom position
    ps_init = np.array(slab.get_positions())
    adatom_init = None
    if adatoms:
        adatom_init = ps_init[adatoms[0]].copy()

    # Run relaxation
    label = f'{metal}_{variant}_111_3x3x3'
    t0 = time.time()
    result = relax_metal_system(slab, backend, frozen, mode=mode, outdir=outdir,
                                fmax=fmax, maxsteps=maxsteps, label=label,
                                extra_meta={'variant': variant, 'metal': metal})
    t1 = time.time()

    if mode == 'local':
        # Verify: frozen atoms didn't move
        ps_final = np.array(result.geom.apos)
        frozen_disp = np.max(np.linalg.norm(
            ps_final[frozen] - ps_init[frozen], axis=1))

        # Verify: adatom position
        adatom_displacement = None
        if adatom_init is not None and adatoms:
            adatom_final = ps_final[adatoms[0]]
            adatom_displacement = float(np.linalg.norm(adatom_final - adatom_init))

        # Get energy
        E = result.energies[-1] if result.energies else None

        elapsed = t1 - t0
        print(f"\n  RESULTS:")
        print(f"    Energy: {E:.6f} eV" if E is not None else "    Energy: N/A")
        print(f"    Time: {elapsed:.1f}s")
        print(f"    Max frozen displacement: {frozen_disp:.2e} Å (should be ~0)")
        if adatom_displacement is not None:
            print(f"    Adatom displacement: {adatom_displacement:.3f} Å")
        print(f"    Converged: {result.converged}")

        # Sanity checks
        checks = []
        if frozen_disp < 1e-4:
            checks.append("PASS: frozen atoms did not move")
        else:
            checks.append(f"FAIL: frozen atoms moved {frozen_disp:.2e} Å")
        if E is not None and not np.isnan(E):
            checks.append("PASS: energy is finite")
        else:
            checks.append("FAIL: energy is NaN")
        if adatom_displacement is not None and adatom_displacement < 1.0:
            checks.append(f"PASS: adatom stayed near fcc hollow (disp={adatom_displacement:.3f} Å)")
        elif adatom_displacement is not None:
            checks.append(f"WARN: adatom moved {adatom_displacement:.3f} Å — check for reconstruction")

        print(f"\n  CHECKS:")
        for c in checks:
            print(f"    {c}")

        return {
            'metal': metal, 'variant': variant, 'energy_eV': E,
            'elapsed_s': elapsed, 'frozen_disp_A': float(frozen_disp),
            'adatom_disp_A': adatom_displacement, 'converged': result.converged,
            'checks': checks,
        }
    else:
        print(f"  Exported to: {outdir}")
        return {'metal': metal, 'variant': variant, 'mode': 'export', 'outdir': outdir}


def main():
    parser = argparse.ArgumentParser(description='Benchmark metal slab relaxation (spec §11.1)')
    parser.add_argument('--metals', nargs='*', default=['Cu'], help='Metals to benchmark (default: Cu)')
    parser.add_argument('--variants', nargs='*', default=['bare', 'adatom'],
                        help='Variants (default: bare adatom)')
    parser.add_argument('--mode', choices=['local', 'export'], default='local',
                        help='local: run GPAW directly; export: write runner scripts')
    parser.add_argument('--ecut', type=float, default=400.0, help='PW cutoff (eV)')
    parser.add_argument('--kpts', type=int, nargs=3, default=[1, 1, 1],
                        help='K-points (default: 1 1 1 = gamma)')
    parser.add_argument('--fmax', type=float, default=0.05, help='Force convergence (eV/Å)')
    parser.add_argument('--maxsteps', type=int, default=100, help='Max relax steps')
    parser.add_argument('--outdir', default=None, help='Output root (default: ./benchmark/)')
    args = parser.parse_args()

    project_dir = os.path.dirname(os.path.abspath(__file__))
    systems_dir = os.path.join(project_dir, 'systems')

    print("=" * 60)
    print("METAL SLAB RELAXATION BENCHMARK (spec §11.1)")
    print(f"  Metals: {args.metals}")
    print(f"  Variants: {args.variants}")
    print(f"  Mode: {args.mode}")
    print(f"  ecut={args.ecut} eV, kpts={tuple(args.kpts)}, fmax={args.fmax}")
    print("=" * 60)

    results = []
    for metal in args.metals:
        for variant in args.variants:
            r = benchmark_one(metal, variant, systems_dir, mode=args.mode,
                              outdir=args.outdir, ecut=args.ecut,
                              kpts=tuple(args.kpts), fmax=args.fmax,
                              maxsteps=args.maxsteps)
            if r is not None:
                results.append(r)

    # Summary
    print("\n" + "=" * 60)
    print("BENCHMARK SUMMARY")
    print("=" * 60)
    if args.mode == 'local':
        print(f"{'Metal':>5} {'Variant':>8} {'E (eV)':>14} {'Time (s)':>10} {'Frozen disp':>12} {'Adatom disp':>12}")
        print("-" * 60)
        for r in results:
            ad = f"{r.get('adatom_disp_A', 0):.3f}" if r.get('adatom_disp_A') else "N/A"
            print(f"{r['metal']:>5} {r['variant']:>8} {r['energy_eV']:>14.6f} {r['elapsed_s']:>10.1f} "
                  f"{r['frozen_disp_A']:>12.2e} {ad:>12}")
    else:
        for r in results:
            print(f"  {r['metal']}/{r['variant']}: exported to {r['outdir']}")

    # Save summary JSON
    summary_path = os.path.join(args.outdir or os.path.join(project_dir, 'benchmark'), 'benchmark_summary.json')
    os.makedirs(os.path.dirname(summary_path), exist_ok=True)
    with open(summary_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n  Summary saved: {summary_path}")


if __name__ == '__main__':
    main()
