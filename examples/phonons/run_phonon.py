#!/usr/bin/env python3
"""
run_phonon.py
=============
Modular phonon band-structure runner.

Reads arbitrary unit cells (.cif, .xyz with lvs), computes force constants
with any backend (DFTB+, LAMMPS, MMFF), caches results, and evaluates
phonon bands at arbitrary q-points (from file or generated from segments).

Usage:
  # DFTB+ on primitive cell with reference q-path
  python run_phonon.py --structure ../../data/crystals/Si_primitive.cif \
      --method dftb --supercell 2 2 2 --q-path-file Si_qpath_ref.dat \
      --outdir phonon_results/Si_primitive_dftb

  # LAMMPS / Tersoff with auto-generated q-path
  python run_phonon.py --structure ../../data/crystals/diamond_primitive.cif \
      --method tersoff --supercell 3 3 3 --q-path-auto fcc_mp \
      --outdir phonon_results/diamond_primitive_tersoff

  # Force recompute (invalidate cache)
  python run_phonon.py ... --force-recompute

  # MMFF (FireCore) — auto-sets LD_PRELOAD for ASAN; compile lib in Build-opt first
  python run_phonon.py --structure ../../data/crystals/diamond_primitive.cif \
      --method mmff --supercell 3 3 3 --q-path-auto diamond_standard \
      --outdir phonon_results/diamond_primitive_mmff --band-solver unified

  # Parity: phonopy vs unified band solver on same DFTB/LAMMPS force constants
  # (requires phonopy — use ML venv: venvML)
  python run_phonon.py --structure ../../data/crystals/diamond_primitive.cif \
      --method tersoff --supercell 3 3 3 --q-path-file plots/diamond_qpath_280.dat \
      --outdir test_primitive --parity-check --band-solver phonopy
"""

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

from phonon_utils import read_structure, QPath, PhononCalculator, get_standard_qpath
from phonon_backends import make_backend, BaseBackend, ensure_mmff_runtime, resolve_mmff_structure, BOHR_TO_ANG


# ------------------------------------------------------------------
# Config helpers
# ------------------------------------------------------------------
def load_config(config_path: str = "phonon_config.json"):
    default = {
        "tools": {
            "lammps_bin": "lmp_serial",
            "dftb_bin": "dftb+",
            "slakos_dir": "",
            "firecore_path": "",
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
# Main workflow
# ------------------------------------------------------------------
def run_phonon(structure_path, method, qpath, supercell, outdir,
               config=None, force_recompute=False, mtp_file=None,
               slakos_dir=None, backend_kwargs=None,
               band_solver=None, freq_convention='positive',
               parity_check=False, parity_tol=0.01, mmff_fc_mode='hessian', hessian_pbc=True,
               mmff_enable_angles=False, mmff_use_uff=False, mmff_scale_bond=None, mmff_scale_angle=None):
    """
    structure_path: path to .cif or .xyz file
    method: 'dftb', 'tersoff', 'sw', 'meam', 'mtp', 'mmff'
    qpath: QPath object
    supercell: [nx, ny, nz] or int
    outdir: output directory
    """
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    
    # Load structure (MMFF uses FireCore crystal .xyz in Bohr, not ASE .cif)
    if method == "mmff":
        config = config or load_config("phonon_config.json")
        fc_path = (config.get("tools", {}).get("firecore_path") or os.environ.get("FIRECORE_PATH", ""))
        structure_path = resolve_mmff_structure(structure_path, fc_path)
    print(f"[struct] Loading {structure_path}")
    positions, cell, symbols, is_prim = read_structure(structure_path)
    # MMFF xyz is already in Angstrom (FireCore native units) — no conversion needed
    print(f"[struct] {len(symbols)} atoms, primitive={is_prim}")
    print(f"[struct] Cell: {cell[0,0]:.4f} x {cell[1,1]:.4f} x {cell[2,2]:.4f} Ang")
    
    # Build backend
    if config is None:
        config = load_config("phonon_config.json")
    if slakos_dir:
        config["tools"]["slakos_dir"] = slakos_dir
    
    backend_kwargs = backend_kwargs or {}
    if mtp_file:
        backend_kwargs["mtp_file"] = mtp_file
    if method == "mmff":
        backend_kwargs.setdefault("fc_mode", mmff_fc_mode)
        backend_kwargs.setdefault("hessian_pbc", hessian_pbc)
        backend_kwargs.setdefault("enable_angles", mmff_enable_angles)
        backend_kwargs.setdefault("use_uff", mmff_use_uff)
        backend_kwargs.setdefault("scale_bond", mmff_scale_bond)
        backend_kwargs.setdefault("scale_angle", mmff_scale_angle)
    
    backend = make_backend(method, config=config, **backend_kwargs)
    print(f"[backend] Using {backend.name}" + (f" fc_mode={backend.fc_mode}" if method == "mmff" else ""))
    
    # Build calculator
    if band_solver is None:
        if method == 'mmff' and getattr(backend, 'fc_mode', 'phonopy') == 'hessian':
            band_solver = 'unified'
        elif method == 'mmff':
            band_solver = 'phonopy'
        else:
            band_solver = 'phonopy'
    calc = PhononCalculator(
        positions=positions,
        cell=cell,
        symbols=symbols,
        supercell=supercell,
        backend=backend,
        outdir=outdir,
        band_solver=band_solver,
        freq_convention=freq_convention,
    )
    
    # Compute force constants (with caching)
    calc.compute_force_constants(force_recompute=force_recompute)
    
    if parity_check:
        calc.check_band_solver_parity(qpath, tol=parity_tol, freq_convention=freq_convention)
    
    # Solve bands
    print(f"[phonon] band_solver={band_solver} freq_convention={freq_convention}")
    print(f"[phonon] Evaluating bands at {len(qpath)} q-points...")
    freqs, dists, labels = calc.solve_bands(qpath)
    
    # Save band data
    n_bands = freqs.shape[1]
    band_dat = outdir / "band.dat"
    qpath.save_dat(str(band_dat), freqs=freqs)
    print(f"[phonon] Saved band.dat: {band_dat}")
    
    # Also save phonopy-compatible band.yaml
    try:
        band_yaml = outdir / "band.yaml"
        calc.save_band_yaml(str(band_yaml), qpath=qpath)
    except Exception as e:
        print(f"[phonon] band.yaml skipped: {e}")
    
    # Save raw data with metadata
    basis_name = ""
    if hasattr(backend, 'slakos_dir') and backend.slakos_dir:
        basis_name = Path(backend.slakos_dir).name
    
    np.savez(
        outdir / "phonon_bands.npz",
        qpts=qpath.qpts,
        distances=dists,
        frequencies=freqs,
        labels=np.array(labels, dtype=str),
        structure_file=str(Path(structure_path).name),
        method=str(method),
        program=str(backend.name),
        basis_set=str(basis_name),
        supercell=str("x".join(map(str, supercell))),
        band_solver=str(band_solver),
        freq_convention=str(freq_convention),
    )
    print(f"[phonon] Saved phonon_bands.npz")
    
    # Plot
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        
        fig, ax = plt.subplots(figsize=(10, 6))
        for b in range(n_bands):
            ax.plot(dists, freqs[:, b], 'b-', lw=0.8, alpha=0.7)
        
        # Tick labels at segment boundaries
        boundaries = qpath.get_segment_boundaries()
        tick_pos = [dists[i] for i in boundaries if i < len(dists)]
        tick_lab = [labels[i] if i < len(labels) else "" for i in boundaries if i < len(labels)]
        if tick_pos:
            ax.set_xticks(tick_pos)
            ax.set_xticklabels(tick_lab, fontsize=11)
            for p in tick_pos:
                ax.axvline(x=p, color='k', lw=0.5, alpha=0.3)
        
        ax.set_ylabel("Frequency (THz)", fontsize=12)
        ax.set_xlabel("Wave Vector", fontsize=12)
        ax.set_ylim(bottom=0)
        ax.grid(axis="y", alpha=0.3)
        material = Path(structure_path).stem
        ax.set_title(f"Phonon Dispersion: {material} ({backend.name})", fontsize=13)
        plt.tight_layout()
        
        plot_path = outdir / "band.png"
        plt.savefig(plot_path, dpi=300)
        print(f"[phonon] Saved plot: {plot_path}")
        plt.close()
    except Exception as e:
        print(f"[phonon] Plotting skipped: {e}")
    
    print(f"\n[done] Results in {outdir}\n")
    return freqs, dists, labels


def main():
    parser = argparse.ArgumentParser(description="Modular phonon band-structure runner")
    parser.add_argument("--structure", required=True, help="Path to .cif or .xyz file")
    parser.add_argument("--method", choices=["dftb", "tersoff", "sw", "meam", "mtp", "mmff"],
                        required=True, help="Force calculation backend")
    parser.add_argument("--supercell", nargs=3, type=int, default=[2, 2, 2],
                        help="Supercell dimensions (default: 2 2 2)")
    parser.add_argument("--outdir", default=".", help="Output directory")
    parser.add_argument("--config", default="phonon_config.json", help="Config file")
    
    # Q-path options (mutually exclusive)
    qpath_group = parser.add_mutually_exclusive_group(required=True)
    qpath_group.add_argument("--q-path-file", help="Load exact q-points from .dat file")
    qpath_group.add_argument("--q-path-auto", choices=["fcc_mp", "diamond_standard"],
                             help="Auto-generate q-path from high-symmetry points")
    
    parser.add_argument("--q-path-npts", type=int, default=40,
                        help="Points per segment for auto q-path (default: 40)")
    parser.add_argument("--force-recompute", action="store_true",
                        help="Invalidate cache and recompute force constants")
    parser.add_argument("--mtp-file", default=None, help="MTP potential file")
    parser.add_argument("--slakos-dir", default=None, help="Override SK basis set directory")
    parser.add_argument("--lattice", type=float, default=None, help="Override lattice constant")
    parser.add_argument("--band-solver", choices=["auto", "phonopy", "unified"], default="auto",
                        help="Band solver: phonopy (default DFTB/LAMMPS) or unified Phi(k) (default MMFF)")
    parser.add_argument("--freq-convention", choices=["positive", "signed"], default="positive",
                        help="Unified solver: positive=phonopy-style, signed=FireCore imaginary modes")
    parser.add_argument("--parity-check", action="store_true",
                        help="Compare phonopy vs unified solvers on same FCs (DFTB/LAMMPS only)")
    parser.add_argument("--parity-tol", type=float, default=0.01, help="Parity max|Δω| tolerance (THz)")
    parser.add_argument("--mmff-fc-mode", choices=["phonopy", "hessian"], default="hessian",
                        help="MMFF: hessian+Phi(R) (default) or phonopy displacements (experimental)")
    parser.add_argument("--hessian-pbc", action=argparse.BooleanOptionalAction, default=True,
                        help="MMFF hessian: nPBC=(1,1,1) periodic bonds (default on); --no-hessian-pbc for cluster")
    parser.add_argument("--mmff-enable-angles", action="store_true",
                        help="MMFF: enable angle forces (default: bonds only)")
    parser.add_argument("--mmff-use-uff", action="store_true",
                        help="MMFF: use UFF instead of MMFF (bMMFF=True, bUFF=True)")
    parser.add_argument("--mmff-scale-bond", type=float, default=None,
                        help="MMFF: scale bond stiffness by factor (e.g., 1.25 for +25%)")
    parser.add_argument("--mmff-scale-angle", type=float, default=None,
                        help="MMFF: scale angle stiffness by factor (e.g., 1.25 for +25%)")
    args = parser.parse_args()
    if args.method == "mmff":
        ensure_mmff_runtime()
    
    # Load config
    config = load_config(args.config)
    if args.slakos_dir:
        config["tools"]["slakos_dir"] = args.slakos_dir
    
    # Build q-path
    if args.q_path_file:
        print(f"[qpath] Loading from {args.q_path_file}")
        qpath = QPath.from_file(args.q_path_file)
    else:
        print(f"[qpath] Auto-generating {args.q_path_auto} path")
        segments = get_standard_qpath(variant=args.q_path_auto)
        qpath = QPath.from_segments(segments, npts_per_seg=args.q_path_npts)
    
    print(f"[qpath] {len(qpath)} q-points")
    
    # Build output prefix
    structure_name = Path(args.structure).stem
    prefix = f"{structure_name}_{args.method}_{args.supercell[0]}x{args.supercell[1]}x{args.supercell[2]}"
    outdir = Path(args.outdir) / prefix
    
    band_solver = None if args.band_solver == "auto" else args.band_solver
    
    # Run
    run_phonon(
        structure_path=args.structure,
        method=args.method,
        qpath=qpath,
        supercell=args.supercell,
        outdir=outdir,
        config=config,
        force_recompute=args.force_recompute,
        mtp_file=args.mtp_file,
        slakos_dir=args.slakos_dir,
        band_solver=band_solver,
        freq_convention=args.freq_convention,
        parity_check=args.parity_check,
        parity_tol=args.parity_tol,
        mmff_fc_mode=args.mmff_fc_mode,
        hessian_pbc=args.hessian_pbc,
        mmff_enable_angles=args.mmff_enable_angles,
        mmff_use_uff=args.mmff_use_uff,
        mmff_scale_bond=args.mmff_scale_bond,
        mmff_scale_angle=args.mmff_scale_angle,
    )


if __name__ == "__main__":
    main()
