#!/usr/bin/env python3
"""grid_fit_mmff_phonon.py

2D grid search fit of MMFF phonon spectra to a DFT reference.

Goals:
- Compute point-by-point, band-by-band discrepancy (RMSE) between reference (e.g. MP DFT) and MMFF.
- Scan two independent stiffness scale factors:
    scale_bond  (multiplies MMFF.bKs)
    scale_angle (multiplies MMFF.apars[:, angle_col])
- Avoid overheads during scan:
    - MMFF is initialized once (single supercell)
    - No plotting, no file I/O inside the inner loop

After the scan the script produces:
- error_heatmap.png
- comparison_best_vs_default.html

Example:
  python grid_fit_mmff_phonon.py \
    --structure /home/prokop/git/CompChemUtils/data/crystals/diamond_primitive.xyz \
    --ref mp_diamond_phonon_bands.dat \
    --supercell 3 \
    --n 10 --range-bond 0.8 1.2 --range-angle 0.8 1.2 \
    --outdir fit_grid_results
"""

import argparse
import json
from pathlib import Path

import numpy as np

from phonon_backends import ensure_mmff_runtime, make_backend, resolve_mmff_structure
from phonon_utils import QPath, read_structure, solve_bands_from_phi, _get_masses
import export_phonon_html as eph


def rmse_spectra(freqs_model, freqs_ref, sort_bands=True, band_weights=None, q_weights=None):
    """RMSE between two spectra arrays of shape (nq, nb).

    Bands are compared at each q-point. By default bands are sorted at each q-point
    to avoid sensitivity to eigenvector ordering.

    band_weights: optional (nb,) weights.
    q_weights: optional (nq,) weights.
    """
    fm = np.asarray(freqs_model, dtype=float)
    fr = np.asarray(freqs_ref, dtype=float)
    if fm.shape != fr.shape:
        raise ValueError(f"freqs_model shape {fm.shape} != freqs_ref shape {fr.shape}")
    if sort_bands:
        fm = np.sort(fm, axis=1)
        fr = np.sort(fr, axis=1)
    diff2 = (fm - fr) ** 2
    if band_weights is not None:
        w = np.asarray(band_weights, dtype=float)
        if w.shape != (fm.shape[1],):
            raise ValueError(f"band_weights shape {w.shape} != ({fm.shape[1]},)")
        diff2 = diff2 * w[None, :]
    if q_weights is not None:
        wq = np.asarray(q_weights, dtype=float)
        if wq.shape != (fm.shape[0],):
            raise ValueError(f"q_weights shape {wq.shape} != ({fm.shape[0]},)")
        diff2 = diff2 * wq[:, None]
    return float(np.sqrt(np.mean(diff2)))


def save_phonon_bands_npz(path, freqs, distances, labels):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(path, frequencies=np.asarray(freqs, float), distances=np.asarray(distances, float), labels=np.array(labels, dtype=str))


def save_heatmap_png(path, errors, bond_scales, angle_scales, best_ij=None, title=None):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    E = np.asarray(errors, float)
    if E.ndim != 2:
        raise ValueError(f"errors must be 2D, got {E.shape}")

    fig, ax = plt.subplots(figsize=(7, 5))
    im = ax.imshow(
        E,
        origin='lower',
        aspect='auto',
        extent=(float(angle_scales[0]), float(angle_scales[-1]), float(bond_scales[0]), float(bond_scales[-1])),
    )
    ax.set_xlabel('scale_angle')
    ax.set_ylabel('scale_bond')
    if title:
        ax.set_title(title)
    cb = fig.colorbar(im, ax=ax)
    cb.set_label('RMSE (THz)')

    if best_ij is not None:
        ib, ia = best_ij
        ax.plot([angle_scales[ia]], [bond_scales[ib]], 'wo', ms=7, mec='k', mew=1)

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def write_comparison_html(out_html, ref_dat, datasets, title=None):
    """Write interactive HTML comparison using the existing viewer template."""
    ref_data = eph.read_mp_dat(ref_dat)
    master_dists, master_labels = ref_data['distances'], ref_data['labels']

    tick_pos, tick_lab = eph.extract_ticks(master_dists, master_labels)
    tick_lab = [eph.normalize_label(l) for l in tick_lab]

    ds = [{"name": "REF DFT (MP)", "frequencies": ref_data['frequencies'], "visible": True}]
    for name, freqs in datasets:
        ds.append({"name": name, "frequencies": np.asarray(freqs, float).tolist(), "visible": True})

    json_data = {
        'title': title or 'MMFF grid-fit comparison',
        'distances': master_dists,
        'tick_positions': tick_pos,
        'tick_labels': tick_lab,
        'datasets': ds,
    }

    template_path = Path(__file__).parent / 'phonon_bands_viewer.html'
    html_template = template_path.read_text()
    html_output = html_template.replace('let data = /*__PHONON_DATA__*/null;', f'let data = {json.dumps(json_data)};')
    html_output = html_output.replace('<body data-file="phonon_bands.json">', '<body>')

    out_html = Path(out_html)
    out_html.parent.mkdir(parents=True, exist_ok=True)
    out_html.write_text(html_output)


def run_grid_fit(structure_path, ref_dat, super_n, outdir, config, n=10, range_bond=(0.8, 1.2), range_angle=(0.8, 1.2), disable_pi=True, quiet_mmff=True):
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    qpath = QPath.from_file(ref_dat)
    ref = eph.read_mp_dat(ref_dat)
    f_ref = np.asarray(ref['frequencies'], dtype=float)

    positions, cell, symbols, _ = read_structure(structure_path)
    masses = np.asarray(_get_masses(symbols), dtype=float)

    bond_scales = np.linspace(float(range_bond[0]), float(range_bond[1]), int(n))
    angle_scales = np.linspace(float(range_angle[0]), float(range_angle[1]), int(n))
    errors = np.zeros((len(bond_scales), len(angle_scales)))

    backend = make_backend('mmff', config=config, fc_mode='hessian', enable_angles=True)

    best = {"rmse": np.inf, "scale_bond": None, "scale_angle": None, "freqs": None, "best_ij": None}
    freqs_default = None

    with backend.make_phonon_session(positions, cell, symbols, super_n, enable_angles=True, disable_pi=disable_pi, quiet=quiet_mmff) as sess:
        i1 = int(np.argmin(np.abs(bond_scales - 1.0)))
        j1 = int(np.argmin(np.abs(angle_scales - 1.0)))
        for ib, sb in enumerate(bond_scales):
            for ia, sa in enumerate(angle_scales):
                sess.set_scales(sb, sa)
                phi = sess.compute_phi_blocks()
                f = solve_bands_from_phi(phi, cell, masses, qpath.qpts, fc_units='ev_ang2', convention='positive')
                e = rmse_spectra(f, f_ref, sort_bands=True)
                errors[ib, ia] = e
                if ib == i1 and ia == j1:
                    freqs_default = f.copy()
                if e < best["rmse"]:
                    best.update({"rmse": e, "scale_bond": float(sb), "scale_angle": float(sa), "freqs": f.copy(), "best_ij": (ib, ia)})

    if freqs_default is None:
        raise RuntimeError("Default spectrum (nearest to scale_bond=1, scale_angle=1) was not captured")

    np.savez(outdir / 'grid_errors.npz', bond_scales=bond_scales, angle_scales=angle_scales, errors=errors,
             best_scale_bond=best['scale_bond'], best_scale_angle=best['scale_angle'], best_rmse=best['rmse'])

    save_heatmap_png(outdir / 'error_heatmap.png', errors, bond_scales, angle_scales, best_ij=best.get('best_ij'),
                     title=f"RMSE grid (best={best['rmse']:.4f} THz at bond={best['scale_bond']:.3f}, angle={best['scale_angle']:.3f})")

    save_phonon_bands_npz(outdir / 'default' / 'phonon_bands.npz', freqs_default, ref['distances'], ref['labels'])
    save_phonon_bands_npz(outdir / 'best' / 'phonon_bands.npz', best['freqs'], ref['distances'], ref['labels'])

    write_comparison_html(
        outdir / 'comparison_best_vs_default.html',
        ref_dat,
        datasets=[
            ("MMFF default", freqs_default),
            (f"MMFF best (bond={best['scale_bond']:.3f}, angle={best['scale_angle']:.3f})", best['freqs']),
        ],
        title='Diamond: MMFF 2D grid fit (bonds + angles)',
    )

    return {
        'outdir': str(outdir),
        'bond_scales': bond_scales,
        'angle_scales': angle_scales,
        'errors': errors,
        'best': best,
        'freqs_default': freqs_default,
    }


def main():
    parser = argparse.ArgumentParser(description='2D grid fit of MMFF bond/angle stiffness to reference phonon bands')
    parser.add_argument('--structure', required=True)
    parser.add_argument('--ref', required=True)
    parser.add_argument('--supercell', type=int, default=3, help='cubic NxNxN supercell (must be odd)')
    parser.add_argument('--outdir', required=True)
    parser.add_argument('--n', type=int, default=10, help='grid subdivisions per axis (n x n)')
    parser.add_argument('--range-bond', type=float, nargs=2, default=(0.8, 1.2))
    parser.add_argument('--range-angle', type=float, nargs=2, default=(0.8, 1.2))
    parser.add_argument('--keep-pi', action='store_true', help='do not forcibly disable PiSigma/PiPiI in MMFF switches')
    parser.add_argument('--verbose-mmff', action='store_true', help='do not suppress libMMFF_lib.so stdout/stderr during grid scan')
    args = parser.parse_args()

    ensure_mmff_runtime()

    # Match run_phonon(): MMFF prefers FireCore crystal xyz if available
    from run_phonon import load_config
    config = load_config('phonon_config.json')
    fc_path = (config.get('tools', {}).get('firecore_path') or '')
    if not fc_path:
        import os
        fc_path = os.environ.get('FIRECORE_PATH', '')
    structure_path = resolve_mmff_structure(args.structure, fc_path)

    res = run_grid_fit(
        structure_path=structure_path,
        ref_dat=args.ref,
        super_n=args.supercell,
        outdir=args.outdir,
        config=config,
        n=args.n,
        range_bond=tuple(args.range_bond),
        range_angle=tuple(args.range_angle),
        disable_pi=(not args.keep_pi),
        quiet_mmff=(not args.verbose_mmff),
    )

    b = res['best']
    print('============================================================')
    print('[grid-fit] DONE')
    print(f"  Outdir:       {res['outdir']}")
    print(f"  Best RMSE:    {b['rmse']:.6f} THz")
    print(f"  scale_bond:   {b['scale_bond']:.6f}")
    print(f"  scale_angle:  {b['scale_angle']:.6f}")
    print(f"  Heatmap:      {Path(res['outdir'])/'error_heatmap.png'}")
    print(f"  Comparison:   {Path(res['outdir'])/'comparison_best_vs_default.html'}")


if __name__ == '__main__':
    main()
