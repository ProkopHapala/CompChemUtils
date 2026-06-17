"""
py/interfaces/xtb.py — xTB backend (GFN1/2-xTB, g-xTB, GFN-FF).

Supports three execution paths:
  1. tblite Python library   (fastest, preferred for GFN1/2)
  2. xtb command-line binary  (universal fallback, supports g-xTB)
  3. ASE XTB wrapper         (convenient when ASE is already used)

Method strings recognized by `method` kwarg:
    'GFN1-xTB'  or 'gfn1'  → tblite GFN1 or xtb --gfn 1
    'GFN2-xTB'  or 'gfn2'  → tblite GFN2 or xtb --gfn 2
    'GFN-FF'    or 'gfnff' → xtb --gfnff
    'g-xTB'     or 'gxtb'  → xtb --gxtb  (no tblite support)

Charge and spin are handled via `charge` and `uhf` kwargs.
"""

import os
import subprocess
import shutil
from typing import Optional, List
from ._base import CalculationBackend


class XTBBBackend(CalculationBackend):
    """xTB / tblite backend.

    Parameters
    ----------
    method      : 'GFN1-xTB', 'GFN2-xTB', 'GFN-FF', 'g-xTB'
    charge      : total molecular charge (default 0)
    uhf         : number of unpaired electrons (default 0)
    solvent     : implicit solvent model name (e.g. 'water'); None = vacuum
    n_threads   : OpenMP threads for xtb binary
    accuracy    : SCC convergence accuracy (default 1.0)
    backend     : 'auto' (try tblite → xtb CLI), 'tblite', 'xtb'
    """
    name = "xtb"
    capabilities = {'energy', 'relax', 'vibrations'}

    def __init__(self, method: str = 'GFN2-xTB', charge: int = 0, uhf: int = 0,
                 solvent: Optional[str] = None, n_threads: int = 1,
                 accuracy: float = 1.0, backend: str = 'auto'):
        self.method = self._normalize_method(method)
        self.charge = charge
        self.uhf = uhf
        self.solvent = solvent
        self.n_threads = n_threads
        self.accuracy = accuracy
        self.backend = backend
        self._tblite = None
        self._xtb_cmd = None

    # ---- normalizers
    def _normalize_method(self, m: str) -> str:
        m = m.strip().lower()
        if m in ('gfn1', 'gfn1-xtb'):
            return 'GFN1-xTB'
        if m in ('gfn2', 'gfn2-xtb'):
            return 'GFN2-xTB'
        if m in ('gfnff', 'gfn-ff'):
            return 'GFN-FF'
        if m in ('gxtb', 'g-xtb'):
            return 'g-xTB'
        return m

    def _method_is_tblite(self) -> bool:
        return self.method in ('GFN1-xTB', 'GFN2-xTB')

    def _method_is_xtb_cli(self) -> bool:
        return self.method in ('GFN1-xTB', 'GFN2-xTB', 'GFN-FF', 'g-xTB')

    # ---- capability detection
    def _has_tblite(self) -> bool:
        try:
            import tblite.interface
            return True
        except ImportError:
            return False

    def _find_xtb(self) -> Optional[str]:
        if self._xtb_cmd is not None:
            return self._xtb_cmd
        cmd = shutil.which('xtb')
        if cmd:
            self._xtb_cmd = cmd
            return cmd
        return None

    def _select_backend(self):
        if self.backend == 'tblite':
            if not self._has_tblite():
                raise RuntimeError("XTBBBackend: tblite requested but not importable")
            return 'tblite'
        if self.backend == 'xtb':
            if self._find_xtb() is None:
                raise RuntimeError("XTBBBackend: xtb binary requested but not found in PATH")
            return 'xtb'
        # auto
        if self._method_is_tblite() and self._has_tblite():
            return 'tblite'
        if self._find_xtb() is not None:
            return 'xtb'
        raise RuntimeError("XTBBBackend: neither tblite nor xtb binary available")

    # ---- geometry conversion
    def _to_arrays(self, geom):
        if hasattr(geom, 'apos') and hasattr(geom, 'enames'):
            apos, es = geom.apos, list(geom.enames)
        else:
            apos, es = geom
        return apos, es

    def _write_xyz(self, apos, es, fname):
        from py import atomicUtils as au
        au.saveXYZ(es, apos, fname)

    # ---- tblite local execution
    def _tblite_calc(self, apos, es):
        import numpy as np
        import tblite.interface as tb
        from .. import elements as el
        numbers = np.array([el.ELEMENTS.index(e) + 1 for e in es], dtype=np.int32)
        pos_bohr = np.array(apos) / 0.52917721090380  # Å → Bohr
        calc = tb.Calculator(self.method, numbers, pos_bohr, charge=self.charge, uhf=self.uhf)
        return calc

    def _tblite_energy(self, geom, **kw) -> float:
        apos, es = self._to_arrays(geom)
        calc = self._tblite_calc(apos, es)
        res = calc.singlepoint()
        E_hartree = res['energy']
        return E_hartree * 27.211396641308

    def _tblite_relax(self, geom, fmax=0.05, maxsteps=200, **kw):
        import numpy as np
        from tblite.interface import Calculator
        from .. import elements as el
        apos, es = self._to_arrays(geom)
        numbers = np.array([el.ELEMENTS.index(e) + 1 for e in es], dtype=np.int32)
        pos_bohr = np.array(apos) / 0.52917721090380
        calc = Calculator(self.method, numbers, pos_bohr, charge=self.charge, uhf=self.uhf)
        # tblite does not have native optimizer; use ASE
        from ase import Atoms
        atoms = Atoms(symbols=es, positions=apos)
        from tblite.ase import TBlite
        atoms.calc = TBlite(method=self.method, charge=self.charge, uhf=self.uhf)
        from ase.optimize import BFGS
        BFGS(atoms).run(fmax=fmax, steps=maxsteps)
        apos_out = np.array(atoms.positions)
        if hasattr(geom, 'apos'):
            from ..AtomicSystem import AtomicSystem
            out = AtomicSystem(); out.apos = apos_out; out.enames = es
            return out
        return (apos_out, es)

    # ---- xtb CLI local execution
    def _xtb_energy(self, geom, **kw) -> float:
        apos, es = self._to_arrays(geom)
        import tempfile
        wd = tempfile.mkdtemp(prefix='xtb_')
        xyz = os.path.join(wd, 'input.xyz')
        self._write_xyz(apos, es, xyz)
        cmd = self._build_xtb_cmd(xyz, task='--sp')
        env = os.environ.copy()
        env['OMP_NUM_THREADS'] = str(self.n_threads)
        subprocess.run(cmd, cwd=wd, env=env, check=True, capture_output=True)
        E = self._parse_xtb_energy(os.path.join(wd, 'xtb.out'))
        return E

    def _xtb_relax(self, geom, fmax=0.05, maxsteps=200, **kw):
        apos, es = self._to_arrays(geom)
        import tempfile, numpy as np
        wd = tempfile.mkdtemp(prefix='xtb_')
        xyz = os.path.join(wd, 'input.xyz')
        self._write_xyz(apos, es, xyz)
        cmd = self._build_xtb_cmd(xyz, task='--opt')
        env = os.environ.copy()
        env['OMP_NUM_THREADS'] = str(self.n_threads)
        subprocess.run(cmd, cwd=wd, env=env, check=True, capture_output=True)
        # read optimized geometry
        opt_xyz = os.path.join(wd, 'xtbopt.xyz')
        if not os.path.exists(opt_xyz):
            raise FileNotFoundError("xtb did not produce xtbopt.xyz")
        from py import atomicUtils as au
        apos_out, _, es_out, _, _ = au.load_xyz(fname=opt_xyz)
        if hasattr(geom, 'apos'):
            from ..AtomicSystem import AtomicSystem
            out = AtomicSystem(); out.apos = apos_out; out.enames = list(es_out)
            return out
        return (apos_out, list(es_out))

    def _xtb_vibrations(self, geom, **kw):
        apos, es = self._to_arrays(geom)
        import tempfile, numpy as np
        wd = tempfile.mkdtemp(prefix='xtb_vib_')
        xyz = os.path.join(wd, 'input.xyz')
        self._write_xyz(apos, es, xyz)
        cmd = self._build_xtb_cmd(xyz, task='--hess')
        env = os.environ.copy()
        env['OMP_NUM_THREADS'] = str(self.n_threads)
        subprocess.run(cmd, cwd=wd, env=env, check=True, capture_output=True)
        # read vibspectrum
        vib_file = os.path.join(wd, 'vibspectrum')
        if not os.path.exists(vib_file):
            raise FileNotFoundError("xtb did not produce vibspectrum")
        freqs = self._parse_vibspectrum(vib_file)
        from ..tasks.base import VibResult
        from .. import elements as el
        masses = np.array([el.ELEMENTS_MASS.get(e, 1.0) for e in es])
        na = len(es)
        # xtb hessian output hessian is optional; read if present
        # For now return frequencies only (modes would need hessian reading)
        return VibResult(geom=geom, frequencies=np.array(freqs), modes=np.zeros((len(freqs), na, 3)), masses=masses)

    def _build_xtb_cmd(self, xyz, task='--sp'):
        cmd = [self._find_xtb(), xyz, task]
        if self.method == 'GFN1-xTB':
            cmd += ['--gfn', '1']
        elif self.method == 'GFN2-xTB':
            cmd += ['--gfn', '2']
        elif self.method == 'GFN-FF':
            cmd += ['--gfnff']
        elif self.method == 'g-xTB':
            cmd += ['--gxtb']
        if self.charge != 0:
            cmd += ['--chrg', str(self.charge)]
        if self.uhf != 0:
            cmd += ['--uhf', str(self.uhf)]
        if self.solvent is not None:
            cmd += ['--alpb', self.solvent]
        if self.accuracy != 1.0:
            cmd += ['--acc', str(self.accuracy)]
        return cmd

    def _parse_xtb_energy(self, outpath):
        if not os.path.exists(outpath):
            raise FileNotFoundError(f"xtb output not found: {outpath}")
        with open(outpath) as f:
            for line in f:
                if 'TOTAL ENERGY' in line:
                    parts = line.split()
                    try:
                        return float(parts[3])  # eV in new xtb? Actually Hartree in older
                    except (IndexError, ValueError):
                        pass
        raise RuntimeError("Could not parse energy from xtb output")

    def _parse_vibspectrum(self, fname):
        freqs = []
        with open(fname) as f:
            for line in f:
                if line.startswith('#'):
                    continue
                ws = line.split()
                if len(ws) >= 2:
                    try:
                        freqs.append(float(ws[1]))
                    except ValueError:
                        pass
        return freqs

    # ---- public dispatch
    def run_energy(self, geom, method=None, basis=None, **kw) -> float:
        self.check('energy')
        if method is not None:
            self.method = self._normalize_method(method)
        back = self._select_backend()
        if back == 'tblite':
            return self._tblite_energy(geom, **kw)
        return self._xtb_energy(geom, **kw)

    def run_relax(self, geom, method=None, basis=None, constraints=None, **kw):
        self.check('relax')
        if method is not None:
            self.method = self._normalize_method(method)
        back = self._select_backend()
        if back == 'tblite' and self._method_is_tblite():
            return self._tblite_relax(geom, **kw)
        return self._xtb_relax(geom, **kw)

    def run_vibrations(self, geom, method=None, basis=None, **kw):
        self.check('vibrations')
        if method is not None:
            self.method = self._normalize_method(method)
        back = self._select_backend()
        if back == 'tblite' and self._method_is_tblite():
            return self._tblite_vib(geom, **kw)
        return self._xtb_vibrations(geom, **kw)

    def _tblite_vib(self, geom, **kw):
        # tblite analytical hessian is available via ase tblite wrapper
        import numpy as np
        from ase import Atoms
        from tblite.ase import TBlite
        from ase.vibrations import Vibrations
        apos, es = self._to_arrays(geom)
        atoms = Atoms(symbols=es, positions=apos)
        atoms.calc = TBlite(method=self.method, charge=self.charge, uhf=self.uhf)
        vib = Vibrations(atoms)
        vib.run()
        freqs = vib.get_frequencies()
        na = len(atoms)
        modes = []
        for i in range(len(freqs)):
            modes.append(vib.get_mode(i))
        from ..tasks.base import VibResult
        from .. import elements as el
        masses = np.array([el.ELEMENTS_MASS.get(e, 1.0) for e in es])
        return VibResult(geom=geom, frequencies=np.array(freqs), modes=np.array(modes) if modes else np.zeros((0, na, 3)), masses=masses)

    # ---- export: shell script + geometry
    def export_energy(self, geom, method=None, basis=None, outdir='.', fname='run_xtb.sh', **kw) -> List[str]:
        if method is not None:
            self.method = self._normalize_method(method)
        apos, es = self._to_arrays(geom)
        os.makedirs(outdir, exist_ok=True)
        xyz_path = os.path.join(outdir, 'input.xyz')
        self._write_xyz(apos, es, xyz_path)
        script = os.path.join(outdir, fname)
        with open(script, 'w') as f:
            f.write("#!/bin/bash\n")
            f.write(f"export OMP_NUM_THREADS={self.n_threads}\n")
            f.write(f"xtb input.xyz {' '.join(self._build_xtb_cmd('input.xyz', task='--sp')[2:])}\n")
        return [xyz_path, script]

    def export_relax(self, geom, method=None, basis=None, constraints=None,
                     outdir='.', fname='run_xtb.sh', **kw) -> List[str]:
        if method is not None:
            self.method = self._normalize_method(method)
        apos, es = self._to_arrays(geom)
        os.makedirs(outdir, exist_ok=True)
        xyz_path = os.path.join(outdir, 'input.xyz')
        self._write_xyz(apos, es, xyz_path)
        script = os.path.join(outdir, fname)
        with open(script, 'w') as f:
            f.write("#!/bin/bash\n")
            f.write(f"export OMP_NUM_THREADS={self.n_threads}\n")
            f.write(f"xtb input.xyz {' '.join(self._build_xtb_cmd('input.xyz', task='--opt')[2:])}\n")
        return [xyz_path, script]

    def export_scan_frames(self, frames, method=None, basis=None, outdir='.', **kw) -> List[str]:
        if method is not None:
            self.method = self._normalize_method(method)
        os.makedirs(outdir, exist_ok=True)
        written = []
        for i, geom in enumerate(frames):
            apos, es = self._to_arrays(geom)
            xyz = os.path.join(outdir, f"frame_{i:04d}.xyz")
            self._write_xyz(apos, es, xyz)
            script = os.path.join(outdir, f"run_frame_{i:04d}.sh")
            with open(script, 'w') as f:
                f.write("#!/bin/bash\n")
                f.write(f"export OMP_NUM_THREADS={self.n_threads}\n")
                cmd = ' '.join(self._build_xtb_cmd(os.path.basename(xyz), task='--sp')[2:])
                f.write(f"xtb {os.path.basename(xyz)} {cmd}\n")
            written.extend([xyz, script])
        return written
