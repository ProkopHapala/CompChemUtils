"""
py/interfaces/psi4.py — Psi4 backend.

Supports:
  - local execution (run_energy, run_relax, run_resp)
  - file export (export_energy, export_relax, export_scan_frames, export_movie)
"""

import os
import sys
import numpy as np
from typing import Optional, List, Tuple
from ._base import CalculationBackend
from ..tasks.base import RelaxResult

# ============ Module-level globals for lazy loading

resp = None
psi4 = None

# ============ Constants from psi4_utils

default_resp_options = {
    'VDW_SCALE_FACTORS': [1.4, 1.6, 1.8, 2.0],
    'VDW_POINT_DENSITY': 1.0,
    'RESP_A': 0.0005,
    'RESP_B': 0.1,
}

default_psi4_options = {
    "geom_maxiter": 100,
    "intrafrag_step_limit": 0.1,
    "intrafrag_step_limit_min": 0.1,
    "intrafrag_step_limit_max": 0.1,
    "opt_coordinates": "cartesian",
    "step_type": "nr"
}

default_params_block = '''
    scf_type df
    opt_type MIN
    geom_maxiter 1000
    g_convergence qchem
    print_trajectory_xyz_file true
    opt_coordinates cartesian
    step_type nr
'''

# ============ Utility functions from psi4_utils

def load_res():
    global resp
    global psi4
    if resp is None:
        import resp
    if psi4 is None:
        import psi4

def try_make_dirs(dname):
    try:
        os.mkdir(dname)
    except:
        pass

def xyz2str(fname):
    ls = [" ".join(l.split()[:4]) for l in open(fname).readlines()[2:]]
    return '\n'.join(ls)

def save_xyz_Q(fname, lines, Qs):
    n = len(Qs)
    with open(fname, 'w') as fout:
        fout.write("%i\n" % n)
        fout.write("#comment \n")
        for i, Q in enumerate(Qs):
            fout.write("%s %10.5f \n" % (lines[i], Q))

def preparemol(fname='input.xyz', geom_str=None):
    load_res()
    if os.path.isfile(fname):
        geom_str = xyz2str(fname)
    mol = psi4.geometry(geom_str)
    mol.update_geometry()
    return mol

def unpack_mol(mol):
    na = mol.natom()
    apos = np.zeros((na, 3))
    es = [str(mol.symbol(i)) for i in range(na)]
    for i in range(na):
        p = mol.xyz(i)
        apos[i, 0] = p[0]
        apos[i, 1] = p[1]
        apos[i, 2] = p[2]
    return apos, es

def pack_mol(apos, es, ifrag_line=None):
    print("pack_mol es=" + str(es) + " apos=" + str(apos))
    load_res()
    na = len(es)
    strs = ["%s %g %g %g" % (es[i], apos[i, 0], apos[i, 1], apos[i, 2]) for i in range(na)]
    if ifrag_line is not None:
        strs.insert(ifrag_line, "--")
    geom = "\n".join(strs)
    print(geom)
    mol = psi4.geometry(geom)
    return mol

def eval(geom, params=None, id=None):
    load_res()
    pars = params.copy()
    method = pars['method']
    del pars['method']
    basis = pars['basis']
    del pars['basis']
    bsse = pars['bsse']
    del pars['bsse']
    ifrag_line = None
    if 'ifrag_line' in params.keys():
        ifrag_line = params.get('ifrag_line')
        del pars['ifrag_line']
    method_basis = method + "/" + basis
    apos, es = geom
    mol = pack_mol(apos, es, ifrag_line=ifrag_line)
    mol.update_geometry()
    mol.symmetrize(1e-3)
    psi4.set_options(pars)
    E = psi4.energy(method_basis, molecule=mol, bsse_type=bsse)
    return E

def relax(geom=None, params=None, fname=None):
    load_res()
    if geom is not None:
        apos, es = geom
        mol = pack_mol(apos, es)
    elif fname is not None:
        smol = xyz2str(fname)
        mol = psi4.geometry(smol)
    pars = params.copy()
    method = pars['method']
    basis = pars['basis']
    del pars['method']
    del pars['basis']
    method_basis = method + "/" + basis
    mol.update_geometry()
    mol.symmetrize(1e-3)
    psi4.set_options(pars)
    psi4.optimize(method_basis, molecule=mol)
    return mol

def psi4resp(name, bRelax=True, indir="./input/", outdir="./output/", method='scf', basis='/STO-3G', resp_options=default_resp_options, psi4_options=default_psi4_options):
    load_res()
    method_basis = method + "/" + basis
    geom = xyz2str(indir + name + ".xyz")
    mol = psi4.geometry(geom)
    mol.update_geometry()
    mol.symmetrize(1e-3)
    psi4.set_options(psi4_options)
    if bRelax:
        psi4.optimize(method_basis, molecule=mol)
    geom_lines = mol.save_string_xyz().split('\n')[1:]
    resp_options['METHOD_ESP'] = method
    resp_options['BASIS_ESP'] = basis
    Qs = resp.resp([mol], resp_options)
    Q_esp = Qs[0]
    Q_resp = Qs[1]
    print('ESP  Charges: ', Q_esp)
    print('RESP Charges: ', Q_resp)
    save_xyz_Q(outdir + name + ".xyz", geom_lines, Q_resp)

def extract_final_geom(fname):
    s = os.popen('grep -n "Final optimized geometry" %s | cut -b -10' % fname).read()
    nstart = int(s.split(':')[0])
    lines = []
    fin = open(fname, 'r')
    for i in range(nstart + 5):
        next(fin)
    for l in fin:
        ws = l.split()
        if len(ws) < 4:
            break
        lines.append(l)
    fin.close()
    return lines

def write_geom(fname, lines, comment="#comment"):
    fout = open(fname, 'w')
    fout.write("%i\n" % len(lines))
    fout.write(comment)
    for l in lines:
        fout.write(l)
    fout.close()

def extract_input_geom(fname):
    s = os.popen('grep -n "molecule " %s | cut -b -10' % fname).read()
    nstart = int(s.split(':')[0])
    fin = open(fname, 'r')
    lines = []
    for i in range(nstart + 1):
        next(fin)
    for l in fin:
        ws = l.split()
        nw = len(ws)
        if nw == 4:
            lines.append(l)
        elif nw == 1:
            nhyphen = len(lines)
        else:
            break
    fin.close()
    return lines, nhyphen

def write_psi4_in(lines, nhyphen=None, mem='500MB', method='b3lyp', basis='CC-pVDZ', bsse="'cp'", params_block=None, fname='psi.in', q=0, multiplicity=1, opt=True):
    fout = open(fname, 'w')
    fout.write('memory ' + mem + "\n")
    fout.write("molecule {\n")
    fout.write("%i %i\n" % (q, multiplicity))
    il = 0
    for l in lines:
        fout.write(l)
        if il == nhyphen:
            fout.write('  --\n')
        il += 1
    fout.write("units angstrom\n")
    fout.write("}\n")
    fout.write("set {\n")
    fout.write("    basis " + basis + "\n")
    if params_block is not None:
        fout.write(params_block)
    fout.write("}\n")
    if nhyphen is None:
        bsse = None
    if opt:
        if bsse is None:
            fout.write("optimize( '%s')\n" % method)
        else:
            fout.write("optimize( '%s', bsse_type=%s)\n" % (method, bsse))
    else:
        if bsse is None:
            fout.write("energy('%s')\n" % method)
        else:
            fout.write("energy( '%s', bsse_type=%s )\n" % (method, bsse))
    fout.close()


class Psi4Backend(CalculationBackend):
    """Psi4 backend: local execution + input file export."""

    name = "psi4"
    capabilities = {'energy', 'relax', 'resp', 'esp'}

    def __init__(self, mem: str = '2GB', n_threads: int = 1,
                 scratch_dir: Optional[str] = None):
        self.mem = mem
        self.n_threads = n_threads
        self.scratch_dir = scratch_dir
        self._psi4 = None

    def _load_psi4(self):
        if self._psi4 is None:
            load_res()
            import psi4 as _p4
            _p4.set_memory(self.mem)
            _p4.set_num_threads(self.n_threads)
            if self.scratch_dir:
                _p4.core.IOManager.shared_object().set_default_path(self.scratch_dir)
            self._psi4 = _p4
        return self._psi4

    def _geom_to_str(self, geom) -> str:
        """Convert AtomicSystem or (apos, es) to Psi4 geometry string."""
        if hasattr(geom, 'apos') and hasattr(geom, 'enames'):
            apos, es = geom.apos, geom.enames
        else:
            apos, es = geom
        return "\n".join(f"{e} {p[0]:.10f} {p[1]:.10f} {p[2]:.10f}" for e, p in zip(es, apos))

    def _make_mol(self, geom, ifrag_line=None):
        p4 = self._load_psi4()
        geom_str = self._geom_to_str(geom)
        if ifrag_line is not None:
            lines = geom_str.split("\n")
            lines.insert(ifrag_line, "--")
            geom_str = "\n".join(lines)
        mol = p4.geometry(geom_str)
        mol.update_geometry()
        mol.symmetrize(1e-3)
        return mol

    # ---- local execution
    def run_energy(self, geom, method: str = 'b3lyp', basis: Optional[str] = 'cc-pvdz',
                   bsse=None, ifrag_line=None, **kw) -> float:
        self.check('energy')
        p4 = self._load_psi4()
        mol = self._make_mol(geom, ifrag_line=ifrag_line)
        method_basis = f"{method}/{basis}" if basis else method
        if bsse:
            E = p4.energy(method_basis, molecule=mol, bsse_type=bsse)
        else:
            E = p4.energy(method_basis, molecule=mol)
        hartree2eV = 27.211396641308
        return float(E) * hartree2eV

    def run_relax(self, geom, method: str = 'b3lyp', basis: Optional[str] = 'cc-pvdz',
                  constraints=None, **kw) -> object:
        self.check('relax')
        apos_in, es_in = (geom.apos, geom.enames) if hasattr(geom, 'apos') else geom
        mol = pack_mol(apos_in, es_in)
        mol.update_geometry()
        mol.symmetrize(1e-3)
        opts = {'geom_maxiter': 200, 'opt_coordinates': 'cartesian'}
        if constraints:
            import warnings
            warnings.warn("Psi4Backend.run_relax(): GeomConstraint → Psi4 frozen_cartesian only; non-freeze constraints not translated.")
            freeze_inds = []
            for c in constraints:
                if c.type == 'freeze_atoms':
                    freeze_inds.extend([i + 1 for i in c.atoms])  # 1-based
            if freeze_inds:
                _p4 = self._load_psi4()
                _p4.set_module_options('optking', {'frozen_cartesian': " ".join(str(i) for i in freeze_inds)})
        p4 = self._load_psi4()
        p4.set_options(opts)
        p4.optimize(f"{method}/{basis}", molecule=mol)
        na = mol.natom()
        apos = np.array([[mol.xyz(i)[j] for j in range(3)] for i in range(na)]) * 0.52917721090380
        es = [str(mol.symbol(i)) for i in range(na)]
        if hasattr(geom, 'apos'):
            from ..AtomicSystem import AtomicSystem
            out = AtomicSystem()
            out.apos = apos
            out.enames = es
            return out
        return (apos, es)

    def run_resp(self, geom, method: str = 'scf', basis: Optional[str] = 'sto-3g', **kw):
        self.check('resp')
        apos, es = (geom.apos, geom.enames) if hasattr(geom, 'apos') else geom
        mol = pack_mol(apos, es)
        mol.update_geometry()
        mol.symmetrize(1e-3)
        opts = kw.get('psi4_options', {})
        p4 = self._load_psi4()
        p4.set_options(opts)
        resp_opts = kw.get('resp_options', default_resp_options.copy())
        resp_opts['METHOD_ESP'] = method
        resp_opts['BASIS_ESP'] = basis
        import resp
        Qs = resp.resp([mol], resp_opts)
        return Qs[1]  # RESP charges

    # ---- internal export helpers

    @staticmethod
    def _frame_to_lines(es, apos):
        return [f"{e} {p[0]:.10f} {p[1]:.10f} {p[2]:.10f}\n" for e, p in zip(es, apos)]

    @staticmethod
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

    # ---- export methods
    def export_energy(self, geom, method: str = 'b3lyp', basis: Optional[str] = 'cc-pvdz',
                      outdir: str = '.', fname: str = 'job.psi4.in',
                      bsse=None, mem: Optional[str] = None, **kw) -> List[str]:
        apos, es = (geom.apos, list(geom.enames)) if hasattr(geom, 'apos') else geom
        lines = self._frame_to_lines(es, apos)
        os.makedirs(outdir, exist_ok=True)
        fpath = os.path.join(outdir, fname)
        self._write_psi4_in(fname=fpath, lines=lines, method=method,
                            basis_main=basis, opt=False, mem=mem or self.mem, bsse=bsse)
        return [fpath]

    def export_relax(self, geom, method: str = 'b3lyp', basis: Optional[str] = 'cc-pvdz',
                     constraints=None, outdir: str = '.', fname: str = 'job.psi4.in',
                     mem: Optional[str] = None, **kw) -> List[str]:
        apos, es = (geom.apos, list(geom.enames)) if hasattr(geom, 'apos') else geom
        lines = self._frame_to_lines(es, apos)
        frozen = []
        if constraints:
            for c in constraints:
                if c.type == 'freeze_atoms':
                    frozen.extend([i + 1 for i in c.atoms])
        os.makedirs(outdir, exist_ok=True)
        fpath = os.path.join(outdir, fname)
        self._write_psi4_in(fname=fpath, lines=lines, method=method,
                            basis_main=basis, frozen_cartesian=frozen if frozen else None,
                            opt=True, mem=mem or self.mem)
        return [fpath]

    def export_scan_frames(self, frames, method: str = 'b3lyp', basis: Optional[str] = 'cc-pvdz',
                           outdir: str = '.', freeze_ag: bool = True,
                           mem: Optional[str] = None, bsse=None, **kw) -> List[str]:
        """Write one Psi4 input file per geometry frame in `frames`.

        frames: list of AtomicSystem or (apos, es) tuples.
        """
        import numpy as np
        os.makedirs(outdir, exist_ok=True)
        written = []
        for i, geom in enumerate(frames):
            apos, es = (geom.apos, list(geom.enames)) if hasattr(geom, 'apos') else geom
            lines = self._frame_to_lines(es, apos)
            frozen = [j + 1 for j, e in enumerate(es) if e == 'Ag'] if freeze_ag else None
            fpath = os.path.join(outdir, f"frame_{i:04d}.psi4.in")
            self._write_psi4_in(fname=fpath, lines=lines, method=method,
                                basis_main=basis, frozen_cartesian=frozen,
                                opt=False, mem=mem or self.mem, bsse=bsse)
            written.append(fpath)
        return written

    def export_movie(self, xyz_movie: str, outdir: str = '.',
                     method: str = 'b3lyp', basis: Optional[str] = 'cc-pvdz',
                     freeze_element: Optional[str] = 'Ag',
                     mem: Optional[str] = None, **kw) -> dict:
        """Export Psi4 inputs from an XYZ movie file.

        Replaces export_psi4_jobs.export_movie_to_psi4().
        """
        from .. import atomicUtils as au
        os.makedirs(outdir, exist_ok=True)
        trj = au.load_xyz_movie(xyz_movie)
        if not trj:
            raise ValueError(f"No frames in {xyz_movie}")

        for iframe, (es, apos, qs, rs, comment) in enumerate(trj):
            lines = self._frame_to_lines(es, apos)
            frozen = None
            if freeze_element is not None:
                frozen = [i + 1 for i, e in enumerate(es) if e == freeze_element]
            tag = f"frame_{iframe:04d}"
            if comment is not None:
                c = comment.strip().replace(' ', '_').replace('/', '_')
                if c:
                    tag = f"{tag}_{c[:80]}"
            fpath = os.path.join(outdir, f"{tag}.psi4.in")
            self._write_psi4_in(fname=fpath, lines=lines, method=method,
                                basis_main=basis, frozen_cartesian=frozen,
                                opt=False, mem=mem or self.mem)
        return {'n_frames': len(trj), 'outdir': outdir}
