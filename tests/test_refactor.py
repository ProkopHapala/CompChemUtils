#!/usr/bin/env python3
"""
tests/test_refactor.py — Regression tests for the CompChemUtils refactor.

Run from the repo root:
    python -m pytest tests/test_refactor.py -v
  or directly:
    python tests/test_refactor.py

Tests do NOT require PySCF / Psi4 / DFTB+ installed — only numpy and the
pure-Python parts of the repo. External-program tests are skipped if the
package is not importable.
"""

import sys, os, tempfile, shutil
import numpy as np

# Ensure repo root is on path
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)


# ─────────────────────────────────────────────────────────────────── #
# 1. Core module imports
# ─────────────────────────────────────────────────────────────────── #

def test_import_atomicUtils():
    from py import atomicUtils as au
    assert hasattr(au, 'load_xyz'), "atomicUtils.load_xyz missing"
    assert hasattr(au, 'saveXYZ'),  "atomicUtils.saveXYZ missing"
    print("PASS  test_import_atomicUtils")

def test_import_AtomicSystem():
    from py.AtomicSystem import AtomicSystem
    a = AtomicSystem()
    assert hasattr(a, 'apos')
    assert hasattr(a, 'enames')
    print("PASS  test_import_AtomicSystem")

def test_import_geom_engine():
    from py import geom_engine as ge
    assert hasattr(ge, 'GeomConstraint')
    assert hasattr(ge, 'freeze_atoms')
    assert hasattr(ge, 'fix_distance')
    assert hasattr(ge, 'fix_angle')
    assert hasattr(ge, 'fix_dihedral')
    print("PASS  test_import_geom_engine")

def test_import_AtomicGraph():
    from py import AtomicGraph
    print("PASS  test_import_AtomicGraph")

def test_import_elements():
    from py import elements
    print("PASS  test_import_elements")

def test_import_plotUtils():
    from py import plotUtils
    print("PASS  test_import_plotUtils")


# ─────────────────────────────────────────────────────────────────── #
# 2. New subpackage imports
# ─────────────────────────────────────────────────────────────────── #

def test_import_interfaces_base():
    from py.interfaces._base import CalculationBackend
    assert callable(CalculationBackend.check)
    print("PASS  test_import_interfaces_base")

def test_import_interfaces_package():
    from py.interfaces import CalculationBackend
    print("PASS  test_import_interfaces_package")

def test_import_tasks_base():
    from py.tasks.base import RelaxResult, ScanResult, VibResult, FukuiResult, PhononResult
    print("PASS  test_import_tasks_base")

def test_import_tasks_package():
    from py.tasks import RelaxResult, ScanResult, VibResult, FukuiResult, PhononResult
    print("PASS  test_import_tasks_package")

def test_import_tasks_relax():
    from py.tasks.relax import relax
    print("PASS  test_import_tasks_relax")

def test_import_tasks_scan():
    from py.tasks.scan import rigid_scan, relaxed_scan
    print("PASS  test_import_tasks_scan")

def test_import_tasks_vibrations():
    from py.tasks.vibrations import vibrations
    print("PASS  test_import_tasks_vibrations")

def test_import_cluster():
    from py.cluster import ResourceSpec
    from py.cluster.pbs import write_pbs_script, write_array_pbs
    print("PASS  test_import_cluster")

def test_import_interfaces_psi4_module():
    from py.interfaces.psi4 import Psi4Backend
    print("PASS  test_import_interfaces_psi4_module")

def test_import_interfaces_pyscf_module():
    from py.interfaces.pyscf import PySCFBackend
    print("PASS  test_import_interfaces_pyscf_module")

def test_import_interfaces_mmff_module():
    from py.interfaces.mmff import MMFFBackend
    print("PASS  test_import_interfaces_mmff_module")


# ─────────────────────────────────────────────────────────────────── #
# 3. GeomConstraint behaviour
# ─────────────────────────────────────────────────────────────────── #

def test_geom_constraint_freeze():
    from py.geom_engine import freeze_atoms, GeomConstraint
    c = freeze_atoms([0, 2, 5])
    assert isinstance(c, GeomConstraint)
    assert c.type == 'freeze_atoms'
    assert c.atoms == [0, 2, 5]
    assert c.value is None
    print("PASS  test_geom_constraint_freeze")

def test_geom_constraint_distance():
    from py.geom_engine import fix_distance
    c = fix_distance(0, 1, 1.5)
    assert c.type == 'fix_distance'
    assert c.atoms == [0, 1]
    assert abs(c.value - 1.5) < 1e-12
    print("PASS  test_geom_constraint_distance")

def test_geom_constraint_angle():
    from py.geom_engine import fix_angle
    c = fix_angle(0, 1, 2, 109.5)
    assert c.type == 'fix_angle'
    assert abs(c.value - 109.5) < 1e-12
    print("PASS  test_geom_constraint_angle")

def test_geom_constraint_dihedral():
    from py.geom_engine import fix_dihedral
    c = fix_dihedral(0, 1, 2, 3, 180.0)
    assert c.type == 'fix_dihedral'
    assert c.atoms == [0, 1, 2, 3]
    print("PASS  test_geom_constraint_dihedral")


# ─────────────────────────────────────────────────────────────────── #
# 4. Result dataclasses
# ─────────────────────────────────────────────────────────────────── #

def test_result_dataclasses():
    from py.tasks.base import RelaxResult, ScanResult, VibResult
    rr = RelaxResult(geom=None, energies=[1.0, 2.0], converged=True, n_steps=2)
    assert rr.converged
    sr = ScanResult(coords=[0.0, 1.0], energies=[-1.0, -2.0])
    assert sr.energies[1] == -2.0
    vr = VibResult(geom=None, frequencies=np.array([100., 200.]), modes=np.zeros((2,3,3)), masses=np.ones(3))
    assert vr.frequencies.shape == (2,)
    print("PASS  test_result_dataclasses")


# ─────────────────────────────────────────────────────────────────── #
# 5. ResourceSpec + PBS script generation
# ─────────────────────────────────────────────────────────────────── #

def test_resource_spec():
    from py.cluster.resources import ResourceSpec
    r = ResourceSpec(n_cores=8, mem_gb=16.0, walltime_h=12.0)
    assert r.walltime_str() == "12:00:00"
    assert r.mem_mb() == 16384
    print("PASS  test_resource_spec")

def test_pbs_script_write():
    from py.cluster.pbs import write_pbs_script
    from py.cluster.resources import ResourceSpec
    tmpdir = tempfile.mkdtemp()
    try:
        r = ResourceSpec(n_cores=4, mem_gb=8.0, walltime_h=2.5, queue='gpu')
        fpath = write_pbs_script("myjob", ["echo hello", "python run.py"],
                                  r, tmpdir, modules=["python/3.10"])
        assert os.path.isfile(fpath)
        txt = open(fpath).read()
        assert "#PBS -N myjob" in txt
        assert "ppn=4" in txt
        assert "module load python/3.10" in txt
        assert "echo hello" in txt
        assert "#PBS -q gpu" in txt
        print("PASS  test_pbs_script_write")
    finally:
        shutil.rmtree(tmpdir)

def test_pbs_array_write():
    from py.cluster.pbs import write_array_pbs
    from py.cluster.resources import ResourceSpec
    tmpdir = tempfile.mkdtemp()
    try:
        r = ResourceSpec(n_cores=2, mem_gb=4.0, walltime_h=1.0)
        dirs = ['/tmp/job0', '/tmp/job1', '/tmp/job2']
        fpath = write_array_pbs("arrjob", dirs, "python compute.py", r, tmpdir)
        assert os.path.isfile(fpath)
        txt = open(fpath).read()
        assert "#PBS -J 0-2" in txt
        assert "PBS_ARRAY_INDEX" in txt
        print("PASS  test_pbs_array_write")
    finally:
        shutil.rmtree(tmpdir)


# ─────────────────────────────────────────────────────────────────── #
# 6. AtomicSystem I/O with real data files
# ─────────────────────────────────────────────────────────────────── #

def test_load_xyz_H2O():
    from py.AtomicSystem import AtomicSystem
    fname = os.path.join(REPO, 'data/xyz/H2O.xyz')
    assert os.path.isfile(fname), f"Missing fixture: {fname}"
    mol = AtomicSystem(fname=fname)
    assert mol.apos is not None, "apos is None"
    assert mol.enames is not None, "enames is None"
    assert len(mol.apos) == 3, f"Expected 3 atoms, got {len(mol.apos)}"
    assert 'O' in mol.enames
    print(f"PASS  test_load_xyz_H2O  apos.shape={mol.apos.shape}")

def test_load_xyz_Ag4():
    from py.AtomicSystem import AtomicSystem
    fname = os.path.join(REPO, 'data/xyz/Ag4.xyz')
    assert os.path.isfile(fname)
    mol = AtomicSystem(fname=fname)
    assert len(mol.apos) == 4
    assert all(e == 'Ag' for e in mol.enames)
    print(f"PASS  test_load_xyz_Ag4  apos.shape={mol.apos.shape}")

def test_save_reload_xyz():
    from py.AtomicSystem import AtomicSystem
    from py import atomicUtils as au
    fname = os.path.join(REPO, 'data/xyz/H2O.xyz')
    mol = AtomicSystem(fname=fname)
    tmpdir = tempfile.mkdtemp()
    try:
        out = os.path.join(tmpdir, 'H2O_copy.xyz')
        mol.saveXYZ(out)
        mol2 = AtomicSystem(fname=out)
        assert len(mol2.apos) == 3
        assert np.allclose(mol.apos[:, :3], mol2.apos[:, :3], atol=1e-5), \
            f"Position mismatch\n{mol.apos}\nvs\n{mol2.apos}"
        print("PASS  test_save_reload_xyz")
    finally:
        shutil.rmtree(tmpdir)


# ─────────────────────────────────────────────────────────────────── #
# 7. geom_engine core functions
# ─────────────────────────────────────────────────────────────────── #

def test_geom_engine_normalize():
    from py.geom_engine import _normalize
    v = np.array([3.0, 0.0, 0.0])
    vn = _normalize(v)
    assert abs(np.linalg.norm(vn) - 1.0) < 1e-12
    print("PASS  test_geom_engine_normalize")

def test_geom_engine_resolve_point():
    from py.geom_engine import _resolve_point
    apos = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
    # atom index
    p = _resolve_point(apos, 1)
    assert np.allclose(p, [1.0, 0.0, 0.0])
    # explicit array
    p2 = _resolve_point(apos, np.array([2.0, 3.0, 4.0]))
    assert np.allclose(p2, [2.0, 3.0, 4.0])
    print("PASS  test_geom_engine_resolve_point")


# ─────────────────────────────────────────────────────────────────── #
# 8. Mock backend — tasks/scan + tasks/relax with no QM dependency
# ─────────────────────────────────────────────────────────────────── #

class MockBackend:
    """Trivial backend: energy = number of atoms, relax = identity."""
    name = "mock"
    capabilities = {'energy', 'relax', 'vibrations'}

    def check(self, task):
        if task not in self.capabilities:
            raise NotImplementedError(task)

    def run_energy(self, geom, method='mock', basis=None, **kw):
        return float(len(geom.apos))

    def run_relax(self, geom, method='mock', basis=None, constraints=None, **kw):
        return geom  # identity

    def export_relax(self, geom, method='mock', basis=None, constraints=None,
                     outdir='.', **kw):
        os.makedirs(outdir, exist_ok=True)
        fpath = os.path.join(outdir, 'mock_relax.txt')
        with open(fpath, 'w') as f:
            f.write(f"# mock relax export  method={method}  natoms={len(geom.apos)}\n")
        return [fpath]

    def export_scan_frames(self, frames, method='mock', basis=None, outdir='.', **kw):
        os.makedirs(outdir, exist_ok=True)
        fpath = os.path.join(outdir, 'mock_scan.txt')
        with open(fpath, 'w') as f:
            f.write(f"# mock scan export  n_frames={len(frames)}\n")
        return [fpath]


def test_rigid_scan_mock():
    from py.AtomicSystem import AtomicSystem
    from py.tasks.scan import rigid_scan
    mol = AtomicSystem(fname=os.path.join(REPO, 'data/xyz/H2O.xyz'))
    frames = [(float(i), mol) for i in range(4)]
    result = rigid_scan(frames, MockBackend(), method='mock', mode='local')
    assert len(result.coords) == 4
    assert all(result.energies == 3.0)  # H2O has 3 atoms
    print("PASS  test_rigid_scan_mock")

def test_rigid_scan_export_mock():
    from py.AtomicSystem import AtomicSystem
    from py.tasks.scan import rigid_scan
    mol = AtomicSystem(fname=os.path.join(REPO, 'data/xyz/H2O.xyz'))
    frames = [(float(i), mol) for i in range(3)]
    tmpdir = tempfile.mkdtemp()
    try:
        result = rigid_scan(frames, MockBackend(), method='mock',
                             mode='export', outdir=tmpdir)
        assert len(result.coords) == 3
        assert np.all(np.isnan(result.energies))
        print("PASS  test_rigid_scan_export_mock")
    finally:
        shutil.rmtree(tmpdir)

def test_relax_mock_local():
    from py.AtomicSystem import AtomicSystem
    from py.tasks.relax import relax
    mol = AtomicSystem(fname=os.path.join(REPO, 'data/xyz/H2O.xyz'))
    result = relax(mol, MockBackend(), method='mock', mode='local')
    assert result.geom is mol
    assert result.converged
    print("PASS  test_relax_mock_local")

def test_relax_mock_export():
    from py.AtomicSystem import AtomicSystem
    from py.tasks.relax import relax
    mol = AtomicSystem(fname=os.path.join(REPO, 'data/xyz/H2O.xyz'))
    tmpdir = tempfile.mkdtemp()
    try:
        result = relax(mol, MockBackend(), method='mock', mode='export', outdir=tmpdir)
        assert not result.converged  # export mode → not yet run
        assert len(result.output_files) == 1
        assert os.path.isfile(result.output_files[0])
        print("PASS  test_relax_mock_export")
    finally:
        shutil.rmtree(tmpdir)

def test_relaxed_scan_mock():
    from py.AtomicSystem import AtomicSystem
    from py.geom_engine import fix_distance
    from py.tasks.scan import relaxed_scan
    mol = AtomicSystem(fname=os.path.join(REPO, 'data/xyz/H2O.xyz'))
    coords = [1.0, 1.5, 2.0]
    result = relaxed_scan(
        mol, MockBackend(), method='mock',
        constraints_fn=lambda cv: [fix_distance(0, 1, cv)],
        step_callback=lambda g, cv: g,  # identity
        coord_values=coords,
        mode='local'
    )
    assert len(result.coords) == 3
    assert list(result.coords) == coords
    print("PASS  test_relaxed_scan_mock")


# ─────────────────────────────────────────────────────────────────── #
# 9. Psi4 export (no Psi4 needed — file writing only)
# ─────────────────────────────────────────────────────────────────── #

def test_psi4_export_energy():
    from py.interfaces.psi4 import Psi4Backend
    from py.AtomicSystem import AtomicSystem
    mol = AtomicSystem(fname=os.path.join(REPO, 'data/xyz/H2O.xyz'))
    tmpdir = tempfile.mkdtemp()
    try:
        backend = Psi4Backend()
        files = backend.export_energy(mol, method='b3lyp', basis='cc-pvdz',
                                       outdir=tmpdir, fname='sp.psi4.in')
        assert len(files) == 1
        assert os.path.isfile(files[0])
        txt = open(files[0]).read()
        assert "b3lyp" in txt
        assert "cc-pvdz" in txt.lower()
        assert "energy(" in txt
        print("PASS  test_psi4_export_energy")
    finally:
        shutil.rmtree(tmpdir)

def test_psi4_export_relax():
    from py.interfaces.psi4 import Psi4Backend
    from py.AtomicSystem import AtomicSystem
    from py.geom_engine import freeze_atoms
    mol = AtomicSystem(fname=os.path.join(REPO, 'data/xyz/Ag4.xyz'))
    tmpdir = tempfile.mkdtemp()
    try:
        backend = Psi4Backend()
        constraints = [freeze_atoms([0, 1])]
        files = backend.export_relax(mol, method='b3lyp', basis='def2-SVP',
                                      constraints=constraints, outdir=tmpdir)
        assert len(files) == 1
        txt = open(files[0]).read()
        assert "optimize(" in txt
        assert "frozen_cartesian" in txt
        print("PASS  test_psi4_export_relax")
    finally:
        shutil.rmtree(tmpdir)

def test_psi4_export_scan_frames():
    from py.interfaces.psi4 import Psi4Backend
    from py.AtomicSystem import AtomicSystem
    mol = AtomicSystem(fname=os.path.join(REPO, 'data/xyz/H2O.xyz'))
    frames = [mol, mol, mol]
    tmpdir = tempfile.mkdtemp()
    try:
        backend = Psi4Backend()
        files = backend.export_scan_frames(frames, method='hf', basis='sto-3g',
                                            outdir=tmpdir, freeze_ag=False)
        assert len(files) == 3
        for f in files:
            assert os.path.isfile(f)
        print("PASS  test_psi4_export_scan_frames")
    finally:
        shutil.rmtree(tmpdir)


# ─────────────────────────────────────────────────────────────────── #
# 10. Ag4 movie generation (existing geom_engine — regression test)
# ─────────────────────────────────────────────────────────────────── #

def test_ag4_movie_generation():
    """Regression: geom_engine.generate_ag4_attach_movie still works."""
    from py.geom_engine import generate_ag4_attach_movie
    ag4  = os.path.join(REPO, 'data/xyz/Ag4.xyz')
    mol  = os.path.join(REPO, 'data/xyz/H2O.xyz')
    tmpdir = tempfile.mkdtemp()
    try:
        out_xyz = os.path.join(tmpdir, 'test_ag4_H2O.xyz')
        res = generate_ag4_attach_movie(
            mol_xyz=mol, out_xyz=out_xyz, ag4_xyz=ag4,
            dist=2.0, tilt_degs=(0.0, 45.0), roll_degs=(0.0,),
            remove_epairs=True
        )
        assert os.path.isfile(out_xyz), "Output XYZ not written"
        assert res['n_frames'] > 0, "No frames generated"
        from py import atomicUtils as au
        trj = au.load_xyz_movie(out_xyz)
        assert len(trj) == res['n_frames']
        print(f"PASS  test_ag4_movie_generation  n_frames={res['n_frames']}")
    finally:
        shutil.rmtree(tmpdir)


# ─────────────────────────────────────────────────────────────────── #
# 11. export_psi4_jobs (existing module — regression test)
# ─────────────────────────────────────────────────────────────────── #

def test_export_psi4_from_movie():
    """Regression: Psi4Backend.export_movie replaces export_psi4_jobs."""
    from py.geom_engine import generate_ag4_attach_movie
    from py.interfaces.psi4 import Psi4Backend
    ag4 = os.path.join(REPO, 'data/xyz/Ag4.xyz')
    mol = os.path.join(REPO, 'data/xyz/H2O.xyz')
    tmpdir = tempfile.mkdtemp()
    try:
        movie_xyz = os.path.join(tmpdir, 'movie.xyz')
        res = generate_ag4_attach_movie(
            mol_xyz=mol, out_xyz=movie_xyz, ag4_xyz=ag4,
            dist=2.0, tilt_degs=(0.0,), roll_degs=(0.0,), remove_epairs=True
        )
        n = res['n_frames']
        backend = Psi4Backend()
        r2 = backend.export_movie(movie_xyz, outdir=os.path.join(tmpdir, 'psi4_inputs'),
                                   method='b3lyp', basis='cc-pvdz', freeze_element='Ag')
        assert r2['n_frames'] == n
        inp_files = [f for f in os.listdir(r2['outdir']) if f.endswith('.psi4.in')]
        assert len(inp_files) == n
        print(f"PASS  test_export_psi4_from_movie  n_frames={n}")
    finally:
        shutil.rmtree(tmpdir)


# ─────────────────────────────────────────────────────────────────── #
# 12. CalculationBackend ABC — capability checking
# ─────────────────────────────────────────────────────────────────── #

def test_backend_capability_check():
    from py.interfaces._base import CalculationBackend
    class DummyBackend(CalculationBackend):
        name = "dummy"
        capabilities = {'energy'}
    b = DummyBackend()
    b.check('energy')  # must not raise
    try:
        b.check('relax')
        assert False, "Should have raised NotImplementedError"
    except NotImplementedError:
        pass
    print("PASS  test_backend_capability_check")


# ─────────────────────────────────────────────────────────────────── #
# Runner
# ─────────────────────────────────────────────────────────────────── #

def test_validate_geometry_pass():
    from py.AtomicSystem import AtomicSystem
    from py.geom_engine import validate_geometry
    mol = AtomicSystem(fname=os.path.join(REPO, 'data/xyz/H2O.xyz'))
    assert validate_geometry(mol) is True
    print("PASS  test_validate_geometry_pass")

def test_validate_geometry_nan_fail():
    from py.AtomicSystem import AtomicSystem
    from py.geom_engine import validate_geometry
    import numpy as np
    mol = AtomicSystem(fname=os.path.join(REPO, 'data/xyz/H2O.xyz'))
    mol.apos = mol.apos.copy()
    mol.apos[0, 0] = np.nan
    try:
        validate_geometry(mol)
        assert False, "Should have raised ValueError for NaN"
    except ValueError as e:
        assert "NaN" in str(e)
    print("PASS  test_validate_geometry_nan_fail")

def test_validate_geometry_overlap_fail():
    from py.AtomicSystem import AtomicSystem
    from py.geom_engine import validate_geometry
    import numpy as np
    mol = AtomicSystem(fname=os.path.join(REPO, 'data/xyz/H2O.xyz'))
    mol.apos = mol.apos.copy()
    mol.apos[1] = mol.apos[0]  # put H on top of O
    try:
        validate_geometry(mol)
        assert False, "Should have raised ValueError for overlap"
    except ValueError as e:
        assert "coincident" in str(e)
    print("PASS  test_validate_geometry_overlap_fail")

def test_validate_geometry_displacement():
    from py.AtomicSystem import AtomicSystem
    from py.geom_engine import validate_geometry
    import numpy as np
    mol = AtomicSystem(fname=os.path.join(REPO, 'data/xyz/H2O.xyz'))
    ref = AtomicSystem(fname=os.path.join(REPO, 'data/xyz/H2O.xyz'))
    mol.apos = mol.apos + np.array([0.1, 0.0, 0.0])  # small shift
    assert validate_geometry(mol, ref_geom=ref, max_atom_displacement=0.5) is True
    try:
        validate_geometry(mol, ref_geom=ref, max_atom_displacement=0.05)
        assert False, "Should have raised ValueError for large displacement"
    except ValueError as e:
        assert "displaced" in str(e)
    print("PASS  test_validate_geometry_displacement")


def test_config_loader_import():
    from py import config_loader as cfg
    assert callable(cfg.load_config)
    assert callable(cfg.get)
    assert callable(cfg.require)
    assert callable(cfg.get_path)
    assert callable(cfg.require_path)
    assert callable(cfg.get_tool)
    assert callable(cfg.require_tool)
    print("PASS  test_config_loader_import")

def test_config_loader_template_exists():
    template = os.path.join(REPO, 'machine_config.template.yaml')
    assert os.path.isfile(template), f"Template missing: {template}"
    # YAML or JSON fallback
    try:
        import yaml
        tmpl = yaml.safe_load(open(template))
    except ImportError:
        import json
        tmpl = json.load(open(template))
    assert 'tools' in tmpl
    assert 'sk_dir' in tmpl
    print("PASS  test_config_loader_template_exists")

def test_config_loader_missing_config_raises():
    from py import config_loader as cfg
    # Ensure we start fresh (no cached config)
    cfg._config_cache = None
    # Temporarily point repo root somewhere without machine_config.yaml
    orig_root = cfg._REPO_ROOT
    try:
        cfg._REPO_ROOT = tempfile.mkdtemp()
        try:
            cfg.load_config()
            assert False, "Should have raised FileNotFoundError"
        except FileNotFoundError as e:
            assert "machine_config.yaml" in str(e)
            assert "machine_config.template.yaml" in str(e)
    finally:
        cfg._REPO_ROOT = orig_root
        cfg._config_cache = None
        import shutil
        shutil.rmtree(cfg._REPO_ROOT, ignore_errors=True)
    print("PASS  test_config_loader_missing_config_raises")

def test_config_loader_env_override():
    from py import config_loader as cfg
    os.environ['COMPCHEM_SK_DIR'] = '/tmp/fake_sk'
    try:
        val = cfg.get('sk_dir')
        assert val == '/tmp/fake_sk', f"Expected env override, got {val}"
    finally:
        del os.environ['COMPCHEM_SK_DIR']
        cfg._config_cache = None
    print("PASS  test_config_loader_env_override")


def test_import_gpaw_backend():
    from py.interfaces.gpaw import GPAWBackend
    b = GPAWBackend(kpts=(1,1,1), ecut=300, xc='PBE')
    assert b.name == 'gpaw'
    assert 'energy' in b.capabilities
    print("PASS  test_import_gpaw_backend")

def test_import_dftbplus_backend():
    from py.interfaces.dftbplus import DFTBPlusBackend
    assert DFTBPlusBackend.name == 'dftb+'
    print("PASS  test_import_dftbplus_backend")

def test_import_xtb_backend():
    from py.interfaces.xtb import XTBBBackend
    assert XTBBBackend.name == 'xtb'
    print("PASS  test_import_xtb_backend")

def test_gpaw_export_energy():
    from py.interfaces.gpaw import GPAWBackend
    from py.AtomicSystem import AtomicSystem
    mol = AtomicSystem(fname=os.path.join(REPO, 'data/xyz/Ag4.xyz'))
    tmpdir = tempfile.mkdtemp()
    try:
        backend = GPAWBackend(kpts=(1,1,1), ecut=400, xc='PBE')
        files = backend.export_energy(mol, method='PBE', outdir=tmpdir, fname='sp.py')
        assert len(files) == 1
        txt = open(files[0]).read()
        assert "GPAW(mode=PW(400.0), xc='PBE'" in txt
        assert "Ag" in txt
        print("PASS  test_gpaw_export_energy")
    finally:
        shutil.rmtree(tmpdir)

def test_dftbplus_export_energy():
    from py.interfaces.dftbplus import DFTBPlusBackend
    from py.AtomicSystem import AtomicSystem
    mol = AtomicSystem(fname=os.path.join(REPO, 'data/xyz/H2O.xyz'))
    tmpdir = tempfile.mkdtemp()
    sk_dir = os.path.join(tmpdir, 'fake_sk')
    os.makedirs(sk_dir, exist_ok=True)
    try:
        backend = DFTBPlusBackend(sk_path=sk_dir, method='D3H5',
                                   scc=True, orbital_resolved_scc=False)
        files = backend.export_energy(mol, outdir=tmpdir)
        assert any(os.path.basename(f) == 'dftb_in.hsd' for f in files)
        hsd = open(next(f for f in files if f.endswith('.hsd'))).read()
        assert 'SCC = Yes' in hsd
        assert 'DftD3' in hsd
        assert 'H = "s"' in hsd
        assert 'O = "p"' in hsd
        print("PASS  test_dftbplus_export_energy")
    finally:
        shutil.rmtree(tmpdir)

def test_xtb_export_energy():
    from py.interfaces.xtb import XTBBBackend
    from py.AtomicSystem import AtomicSystem
    mol = AtomicSystem(fname=os.path.join(REPO, 'data/xyz/H2O.xyz'))
    tmpdir = tempfile.mkdtemp()
    try:
        backend = XTBBBackend(method='GFN2-xTB', charge=0, uhf=0)
        files = backend.export_energy(mol, outdir=tmpdir)
        assert any(f.endswith('.xyz') for f in files)
        assert any(f.endswith('.sh') for f in files)
        sh = open(next(f for f in files if f.endswith('.sh'))).read()
        assert '--gfn 2' in sh
        print("PASS  test_xtb_export_energy")
    finally:
        shutil.rmtree(tmpdir)

def test_xtb_export_scan_frames():
    from py.interfaces.xtb import XTBBBackend
    from py.AtomicSystem import AtomicSystem
    mol = AtomicSystem(fname=os.path.join(REPO, 'data/xyz/H2O.xyz'))
    frames = [mol, mol]
    tmpdir = tempfile.mkdtemp()
    try:
        backend = XTBBBackend(method='GFN1-xTB')
        files = backend.export_scan_frames(frames, outdir=tmpdir)
        assert len(files) == 4  # 2 xyz + 2 sh
        sh0 = open(next(f for f in files if 'run_frame_0000' in f)).read()
        assert '--gfn 1' in sh0
        print("PASS  test_xtb_export_scan_frames")
    finally:
        shutil.rmtree(tmpdir)


ALL_TESTS = [
    # imports
    test_import_atomicUtils,
    test_import_AtomicSystem,
    test_import_geom_engine,
    test_import_AtomicGraph,
    test_import_elements,
    test_import_plotUtils,
    test_import_interfaces_base,
    test_import_interfaces_package,
    test_import_tasks_base,
    test_import_tasks_package,
    test_import_tasks_relax,
    test_import_tasks_scan,
    test_import_tasks_vibrations,
    test_import_cluster,
    test_import_interfaces_psi4_module,
    test_import_interfaces_pyscf_module,
    test_import_interfaces_mmff_module,
    # constraints
    test_geom_constraint_freeze,
    test_geom_constraint_distance,
    test_geom_constraint_angle,
    test_geom_constraint_dihedral,
    # results
    test_result_dataclasses,
    # cluster
    test_resource_spec,
    test_pbs_script_write,
    test_pbs_array_write,
    # I/O
    test_load_xyz_H2O,
    test_load_xyz_Ag4,
    test_save_reload_xyz,
    # geom_engine internals
    test_geom_engine_normalize,
    test_geom_engine_resolve_point,
    # mock-backend tasks
    test_rigid_scan_mock,
    test_rigid_scan_export_mock,
    test_relax_mock_local,
    test_relax_mock_export,
    test_relaxed_scan_mock,
    # psi4 export (no Psi4 needed)
    test_psi4_export_energy,
    test_psi4_export_relax,
    test_psi4_export_scan_frames,
    # regression: existing scripts
    test_ag4_movie_generation,
    test_export_psi4_from_movie,
    # ABC
    test_backend_capability_check,
    # geometry validation
    test_validate_geometry_pass,
    test_validate_geometry_nan_fail,
    test_validate_geometry_overlap_fail,
    test_validate_geometry_displacement,
    # new backends: import + export
    test_import_gpaw_backend,
    test_import_dftbplus_backend,
    test_import_xtb_backend,
    test_gpaw_export_energy,
    test_dftbplus_export_energy,
    test_xtb_export_energy,
    test_xtb_export_scan_frames,
    # config loader
    test_config_loader_import,
    test_config_loader_template_exists,
    test_config_loader_missing_config_raises,
    test_config_loader_env_override,
]


if __name__ == '__main__':
    passed, failed = 0, []
    for fn in ALL_TESTS:
        try:
            fn()
            passed += 1
        except Exception as e:
            import traceback
            print(f"FAIL  {fn.__name__}")
            traceback.print_exc()
            failed.append(fn.__name__)
    print(f"\n{'='*55}")
    print(f"  {passed}/{len(ALL_TESTS)} passed   {len(failed)} failed")
    if failed:
        print("  FAILED:", failed)
        sys.exit(1)
    else:
        print("  ALL TESTS PASSED")
