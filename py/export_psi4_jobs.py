#!/usr/bin/python

import os
import numpy as np

from . import atomicUtils as au


def _ensure_dir(d):
    os.makedirs(d, exist_ok=True)


def _frame_to_lines(es, apos):
    return [f"{e} {p[0]:.10f} {p[1]:.10f} {p[2]:.10f}\n" for e, p in zip(es, apos)]


def _write_psi4_in(
    fname,
    lines,
    q=0,
    multiplicity=1,
    method='b3lyp',
    basis_main='cc-pvdz',
    basis_ag='def2-SVP',
    ecp_ag='def2-SVP',
    frozen_cartesian=None,
    opt=False,
    mem='2GB',
    bsse=None,
):
    with open(fname, 'w') as fout:
        fout.write(f"memory {mem}\n")
        fout.write("molecule {\n")
        fout.write(f"{q} {multiplicity}\n")
        for l in lines:
            fout.write(l)
        fout.write("units angstrom\n")
        fout.write("}\n")

        fout.write("set {\n")
        fout.write("    scf_type df\n")
        fout.write("    opt_coordinates cartesian\n")
        fout.write("    geom_maxiter 200\n")
        fout.write("}\n")

        fout.write("basis {\n")
        fout.write(f"    assign {basis_main}\n")
        fout.write(f"    assign Ag {basis_ag}\n")
        fout.write("}\n")

        if ecp_ag is not None:
            fout.write("ecp {\n")
            fout.write(f"    assign Ag {ecp_ag}\n")
            fout.write("}\n")

        if frozen_cartesian:
            inds = " ".join(str(int(i)) for i in frozen_cartesian)
            fout.write("set optking {\n")
            fout.write(f"  frozen_cartesian = (\"{inds}\")\n")
            fout.write("}\n")

        if opt:
            if bsse is None:
                fout.write(f"optimize('{method}')\n")
            else:
                fout.write(f"optimize('{method}', bsse_type={bsse})\n")
        else:
            if bsse is None:
                fout.write(f"energy('{method}')\n")
            else:
                fout.write(f"energy('{method}', bsse_type={bsse})\n")


def export_movie_to_psi4(
    xyz_movie,
    outdir,
    method='b3lyp',
    basis_main='cc-pvdz',
    basis_ag='def2-SVP',
    ecp_ag='def2-SVP',
    freeze_ag=True,
    opt=False,
    q=0,
    multiplicity=1,
    mem='2GB',
):
    _ensure_dir(outdir)

    trj = au.load_xyz_movie(xyz_movie)
    if not trj:
        raise ValueError(f"No frames in {xyz_movie}")

    for iframe, (es, apos, qs, rs, comment) in enumerate(trj):
        lines = _frame_to_lines(es, apos)

        frozen = None
        if freeze_ag:
            frozen = [i + 1 for i, e in enumerate(es) if e == 'Ag']

        tag = f"frame_{iframe:04d}"
        if comment is not None:
            c = comment.strip().replace(' ', '_').replace('/', '_')
            if c:
                tag = f"{tag}_{c[:80]}"

        fname = os.path.join(outdir, f"{tag}.psi4.in")

        _write_psi4_in(
            fname=fname,
            lines=lines,
            q=q,
            multiplicity=multiplicity,
            method=method,
            basis_main=basis_main,
            basis_ag=basis_ag,
            ecp_ag=ecp_ag,
            frozen_cartesian=frozen,
            opt=opt,
            mem=mem,
        )

    return {'n_frames': len(trj), 'outdir': outdir}
