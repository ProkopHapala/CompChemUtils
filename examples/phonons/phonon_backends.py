#!/usr/bin/env python3
"""
phonon_backends.py
==================
Pluggable force calculators for the modular phonon pipeline.

Backends:
  - DFTBBackend    : DFTB+ direct execution (no ASE)
  - LAMMPSBackend  : LAMMPS with various potentials (no ASE)
  - MMFFBackend    : FireCore MMFF (Hessian-based, EXPERIMENTAL)

Each backend implements:
    name: str
    config: dict
    compute_forces(positions, cell, symbols, outdir, disp_idx) -> forces (eV/Ang)
"""

import os
import re
import sys
import json
import subprocess
import tempfile
from pathlib import Path
from contextlib import contextmanager

import numpy as np


@contextmanager
def _suppress_native_output(enabled=False):
    if not enabled:
        yield
        return
    devnull = os.open(os.devnull, os.O_WRONLY)
    saved_out = os.dup(1)
    saved_err = os.dup(2)
    try:
        os.dup2(devnull, 1)
        os.dup2(devnull, 2)
        yield
    finally:
        os.dup2(saved_out, 1)
        os.dup2(saved_err, 2)
        os.close(saved_out)
        os.close(saved_err)
        os.close(devnull)


class BaseBackend:
    """Base class for force calculators."""
    
    name = "base"
    config = {}
    
    def compute_forces(self, positions, cell, symbols, outdir, disp_idx):
        """Return forces (eV/Ang) for given atomic configuration."""
        raise NotImplementedError


class DFTBBackend(BaseBackend):
    """DFTB+ force calculator — runs dftb+ binary directly."""
    
    name = "dftb"
    
    def __init__(self, dftb_bin="dftb+", slakos_dir=""):
        self.dftb_bin = dftb_bin
        self.slakos_dir = slakos_dir
        self.config = {"dftb_bin": dftb_bin, "slakos_dir": slakos_dir}
    
    def compute_forces(self, positions, cell, symbols, outdir, disp_idx):
        os.makedirs(outdir, exist_ok=True)
        elem = symbols[0]
        natoms = len(positions)
        
        # Write dftb_in.hsd
        hsd = "Geometry = GenFormat {\n  {\n    <<< 'geometry.gen'\n  }\n}\n\n"
        hsd += "Hamiltonian = DFTB {\n  SCC = Yes\n"
        if self.slakos_dir:
            hsd += f'  SlaterKosterFiles = Type2FileNames {{\n'
            hsd += f'    Prefix = "{self.slakos_dir}/"\n'
            hsd += f'    Separator = "-"\n'
            hsd += f'    Suffix = ".skf"\n  }}\n'
        hsd += "  MaxAngularMomentum {\n"
        hsd += f"    {elem} = p\n  }}\n"
        hsd += "  KPointsAndWeights {\n    0.0 0.0 0.0 1.0\n  }\n}\n\n"
        hsd += "Options {\n  WriteResultsTag = Yes\n}\n\n"
        hsd += "Analysis {\n  CalculateForces = Yes\n}"
        
        with open(os.path.join(outdir, "dftb_in.hsd"), "w") as f:
            f.write(hsd)
        
        # geometry.gen
        gen = [f"{natoms} S", elem]
        for i, (x, y, z) in enumerate(positions, 1):
            gen.append(f"{i:4d} 1 {x:18.10f} {y:18.10f} {z:18.10f}")
        gen.append("0.0000000000 0.0000000000 0.0000000000")
        for i in range(3):
            gen.append(f"{cell[i][0]:18.10f} {cell[i][1]:18.10f} {cell[i][2]:18.10f}")
        with open(os.path.join(outdir, "geometry.gen"), "w") as f:
            f.write("\n".join(gen) + "\n")
        
        # Run DFTB+
        result = subprocess.run(
            [self.dftb_bin], cwd=outdir,
            capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0:
            raise RuntimeError(f"DFTB+ failed: {result.stderr[:500]}")
        
        # Parse forces
        forces = _parse_dftb_results_tag(os.path.join(outdir, "results.tag"), natoms)
        forces *= 27.211386245988 / 0.529177210903  # Hartree/Bohr -> eV/Ang
        return forces


class LAMMPSBackend(BaseBackend):
    """LAMMPS force calculator — runs lmp_serial directly."""
    
    name = "lammps"
    
    POTENTIAL_MAP = {
        "sw":       {"Si": "Si.sw",       "C": None},
        "tersoff":  {"Si": "Si.tersoff",  "C": "SiC.tersoff"},
        "meam":     {"Si": "SiS",         "C": None},
    }
    
    MEAM_LIB_NAMES = {"Si": "SiS", "C": None}
    
    def __init__(self, lammps_bin="lmp_serial", potential="tersoff",
                 pot_paths=None, mtp_file=None):
        self.lammps_bin = lammps_bin
        self.potential = potential
        self.pot_paths = pot_paths or {}
        self.mtp_file = mtp_file
        self.config = {
            "lammps_bin": lammps_bin,
            "potential": potential,
            "pot_paths": pot_paths,
            "mtp_file": mtp_file,
        }
    
    def compute_forces(self, positions, cell, symbols, outdir, disp_idx):
        os.makedirs(outdir, exist_ok=True)
        elem = symbols[0]
        natoms = len(positions)
        ax, ay, az = np.linalg.norm(cell[0]), np.linalg.norm(cell[1]), np.linalg.norm(cell[2])
        
        # Material info
        MASSES = {"Si": 28.0855, "C": 12.011}
        mass = MASSES.get(elem, 1.0)
        
        # structure.lammps
        data = [
            f"LAMMPS data", "", f"{natoms} atoms", "1 atom types", "",
            f"0.0 {ax:.6f} xlo xhi", f"0.0 {ay:.6f} ylo yhi", f"0.0 {az:.6f} zlo zhi", "",
            "Masses", "", f"1 {mass:.4f}", "", "Atoms", ""
        ]
        for i, (x, y, z) in enumerate(positions, 1):
            data.append(f"{i} 1 {x:.6f} {y:.6f} {z:.6f}")
        with open(os.path.join(outdir, "structure.lammps"), "w") as f:
            f.write("\n".join(data) + "\n")
        
        # force.in
        in_lines = [
            "# LAMMPS force calculation", "units metal", "atom_style atomic",
            "read_data structure.lammps", ""
        ]
        
        if self.potential == "sw":
            pot_file = self.pot_paths.get("si_sw", "Si.sw")
            in_lines += ["pair_style sw", f"pair_coeff * * {pot_file} {elem}"]
        elif self.potential == "tersoff":
            in_lines += ["pair_style tersoff"]
            if elem == "Si":
                pot_file = self.pot_paths.get("si_tersoff", "Si.tersoff")
                in_lines.append(f"pair_coeff * * {pot_file} Si")
            else:
                pot_file = self.pot_paths.get("c_tersoff", "SiC.tersoff")
                in_lines.append(f"pair_coeff * * {pot_file} C")
        elif self.potential == "meam":
            lib_name = self.MEAM_LIB_NAMES.get(elem)
            if not lib_name:
                raise ValueError(f"MEAM not configured for {elem}")
            meam_lib = self.pot_paths.get("meam_library", "library.meam")
            in_lines += ["pair_style meam", f"pair_coeff * * {meam_lib} {lib_name} NULL {lib_name}"]
        elif self.potential == "mtp":
            if not self.mtp_file:
                raise ValueError("mtp_file required for MTP")
            in_lines += ["pair_style mlip mlip.ini", f"pair_coeff * * {self.mtp_file}"]
        else:
            raise ValueError(f"Unknown potential: {self.potential}")
        
        in_lines += [
            "", "neighbor 0.3 bin", "neigh_modify delay 0", "",
            "timestep 0.001", "run 0", "",
            'dump 1 all custom 1 dump.force id type fx fy fz',
            'dump_modify 1 format line "%d %d %.10f %.10f %.10f"',
            "run 0"
        ]
        with open(os.path.join(outdir, "force.in"), "w") as f:
            f.write("\n".join(in_lines) + "\n")
        
        # Run LAMMPS
        log_path = os.path.join(outdir, "log.lammps")
        with open(log_path, "w") as logf:
            result = subprocess.run(
                [self.lammps_bin, "-in", "force.in"],
                cwd=outdir, stdout=logf, stderr=subprocess.STDOUT, timeout=60
            )
        if result.returncode != 0:
            raise RuntimeError(f"LAMMPS failed in {outdir}")
        
        forces = _parse_lammps_dump(os.path.join(outdir, "dump.force"), natoms)
        return forces


def resolve_mmff_structure(structure_path, firecore_path):
    """Return path to FireCore crystal .xyz (Bohr/lvs) for MMFF, if available."""
    stem = Path(structure_path).stem
    fc_xyz = os.path.join(firecore_path, "cpp/common_resources/crystals", f"{stem}.xyz")
    if os.path.isfile(fc_xyz):
        print(f"[MMFF] Using FireCore crystal: {fc_xyz}")
        return fc_xyz
    if Path(structure_path).suffix.lower() == ".xyz":
        return structure_path
    raise ValueError(
        f"MMFF requires FireCore crystal .xyz (Bohr/lvs); not found: {fc_xyz}. "
        f"Add crystal to FireCore/cpp/common_resources/crystals/ or pass .xyz directly."
    )


def _extract_phi_blocks_firecore(phi, sc_cell, sc_ia, inds_disp, n_prim, rmax=None):
    """Build Phi(R) from rectangular phi matrix (n_sc*3 x n_disp*3) - from FireCore test_diamond_phonon_bands.py."""
    if rmax is None:
        rmax = max(max(abs(c[0]), abs(c[1]), abs(c[2])) for c in sc_cell)
    Phi_blocks = {}
    for p_idx, ip in enumerate(inds_disp):
        ia_i = sc_ia[ip]
        n_sc = len(sc_cell)
        for j in range(n_sc):
            R = sc_cell[j]
            if max(abs(R[0]), abs(R[1]), abs(R[2])) > rmax:
                continue
            Rkey = tuple(R)
            ia_j = sc_ia[j]
            if Rkey not in Phi_blocks:
                Phi_blocks[Rkey] = np.zeros((n_prim, n_prim, 3, 3))
            Phi_blocks[Rkey][ia_i, ia_j] = phi[j*3:(j+1)*3, p_idx*3:(p_idx+1)*3]
    return Phi_blocks


def ensure_mmff_runtime():
    """Re-exec with ASAN preload only if libMMFF_lib.so was built with ASAN (Build-asan)."""
    if "libasan" in os.environ.get("LD_PRELOAD", ""):
        return  # already set
    # Check if the .so actually needs ASAN (Build-asan symlink vs Build-opt)
    import ctypes.util
    try:
        build_path = subprocess.check_output(
            ["python3", "-c",
             "import sys; sys.path.insert(0,'/home/prokop/git/FireCore'); "
             "from pyBall import cpp_utils_ as c; print(c.BUILD_PATH)"],
            text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        build_path = ""
    needs_asan = "Build-asan" in build_path or "Build-asan" in os.path.realpath(build_path)
    if not needs_asan:
        return  # Build-opt: no ASAN preload needed
    gxx = subprocess.run(["which", "g++"], capture_output=True, text=True)
    if gxx.returncode != 0:
        raise RuntimeError("MMFF requires g++ for ASAN runtime; set LD_PRELOAD manually")
    libasan = subprocess.check_output(["g++", "-print-file-name=libasan.so"], text=True).strip()
    libfftw = subprocess.check_output(["g++", "-print-file-name=libfftw3.so"], text=True).strip()
    if not os.path.isfile(libasan):
        raise RuntimeError(f"libasan not found: {libasan}")
    env = os.environ.copy()
    env["LD_PRELOAD"] = f"{libasan}:{libfftw}"
    env.setdefault("LSAN_OPTIONS", "detect_leaks=0")
    env.setdefault("ASAN_OPTIONS", "detect_leaks=0:halt_on_error=0")
    print(f"[MMFF] Re-exec with LD_PRELOAD={env['LD_PRELOAD']}")
    os.execve(sys.executable, [sys.executable] + sys.argv, env)


HA_TO_EV = 27.211386245988
BOHR_TO_ANG = 0.529177210903
ANG_TO_BOHR = 1.0 / BOHR_TO_ANG


class MMFFBackend(BaseBackend):
    """FireCore MMFF backend for periodic phonon force constants.
    
    fc_mode:
      'phonopy' — finite-difference forces on phonopy supercell displacements (DFTB-like; default)
      'hessian' — full supercell Hessian + central-cell Phi(0,R) extraction (legacy cluster)
    
    Periodic bonds: init with lvs xyz + nPBC>0 (hessian_pbc=True).  Bloch D(k) is applied in Python.
    Compile: cmake --build /home/prokop/git/FireCore/cpp/Build --target MMFF_lib
    """
    
    name = "mmff"
    
    def __init__(self, firecore_path="", mmff_data_dir="", dx=1e-4, fc_mode="hessian", hessian_pbc=True, enable_angles=False, use_uff=False, scale_bond=None, scale_angle=None):
        self.firecore_path = os.path.normpath(firecore_path or os.environ.get("FIRECORE_PATH", ""))
        if not self.firecore_path:
            raise ValueError("MMFF backend requires firecore_path in config or FIRECORE_PATH env var")
        self.mmff_data_dir = mmff_data_dir or os.path.join(self.firecore_path, "cpp/common_resources")
        if not os.path.isdir(self.mmff_data_dir):
            raise FileNotFoundError(f"MMFF data dir not found: {self.mmff_data_dir}")
        if fc_mode not in ("phonopy", "hessian"):
            raise ValueError(f"MMFF fc_mode must be 'phonopy' or 'hessian', got {fc_mode}")
        self.dx = dx
        self.fc_mode = fc_mode
        self.hessian_pbc = hessian_pbc
        self.is_hessian_backend = fc_mode == "hessian"
        self.enable_angles = enable_angles
        self.use_uff = use_uff
        self.scale_bond = scale_bond
        self.scale_angle = scale_angle
        self._MMFF = None
        self.config = {"firecore_path": self.firecore_path, "mmff_data_dir": self.mmff_data_dir,
                       "dx": dx, "fc_mode": fc_mode, "hessian_pbc": hessian_pbc,
                       "scale_bond": self.scale_bond, "scale_angle": self.scale_angle}
    
    def _mmff_data_paths(self):
        d = self.mmff_data_dir
        return {k: os.path.join(d, f"{k}.dat") for k in ("ElementTypes", "AtomTypes", "BondTypes", "AngleTypes", "DihedralTypes")}
    
    def _init_mmff(self):
        if self._MMFF is None:
            fc_py = os.path.join(self.firecore_path, "pyBall")
            if self.firecore_path not in sys.path:
                sys.path.insert(0, self.firecore_path)
            # MMFF.py loads libMMFF_lib.so from FireCore/cpp/Build/ only; do NOT ctypes.CDLL override
            from pyBall import MMFF
            self._MMFF = MMFF
        return self._MMFF
    
    def _write_mmff_xyz(self, path, positions, cell, symbols):
        """Write xyz in Angstrom (MMFF native units)."""
        n = len(symbols)
        with open(path, "w") as f:
            f.write(f"{n}\n")
            f.write(f"lvs  {cell[0,0]:.8f} {cell[0,1]:.8f} {cell[0,2]:.8f}  "
                    f"{cell[1,0]:.8f} {cell[1,1]:.8f} {cell[1,2]:.8f}  "
                    f"{cell[2,0]:.8f} {cell[2,1]:.8f} {cell[2,2]:.8f}\n")
            for sym, p in zip(symbols, positions):
                f.write(f"{sym}  {p[0]:.8f}  {p[1]:.8f}  {p[2]:.8f}\n")

    def _mmff_init_geometry(self, positions_ang, cell_ang, symbols, xyz_path, nPBC):
        """Init MMFF on geometry; positions/cell in Angstrom (MMFF native units)."""
        MMFF = self._init_mmff()
        self._write_mmff_xyz(xyz_path, positions_ang, cell_ang, symbols)
        dp = self._mmff_data_paths()
        ptr = MMFF.init(xyz_name=xyz_path, nPBC=tuple(nPBC), bEpairs=False, bMMFF=True,
                        sElementTypes=dp["ElementTypes"], sAtomTypes=dp["AtomTypes"],
                        sBondTypes=dp["BondTypes"], sAngleTypes=dp["AngleTypes"],
                        sDihedralTypes=dp["DihedralTypes"])
        if ptr is None:
            raise RuntimeError(f"MMFF.init failed for {xyz_path}")
        return MMFF

    def compute_forces(self, positions, cell, symbols, outdir, disp_idx):
        """Periodic supercell forces for phonopy FC workflow (positions/cell in Angstrom)."""
        os.makedirs(outdir, exist_ok=True)
        xyz_path = os.path.join(outdir, "geometry.xyz")
        # Explicit supercell atoms; PBC on supercell lattice (phonopy periodic displacements)
        MMFF = self._mmff_init_geometry(positions, cell, symbols, xyz_path, nPBC=(1, 1, 1))
        MMFF.getBuffs()
        MMFF.eval()
        forces = np.array(MMFF.fapos, dtype=float).copy()  # eV/Ang (MMFF native)
        if forces.shape[0] != len(symbols):
            raise RuntimeError(f"MMFF fapos shape {forces.shape} != natoms {len(symbols)}")
        return forces  # already eV/Ang, phonopy expects eV/Ang

    def compute_phi_blocks(self, positions, cell, symbols, super_n):
        """Build supercell, compute MMFF Hessian, return Phi(0,R) blocks.
        
        positions/cell in Angstrom. MMFF operates in eV/Ang internally.
        Returns (Phi_blocks dict, cell_ang ndarray).  Phi is in eV/Ang^2.
        """
        from phonon_utils import build_supercell, extract_phi_blocks
        pos_ang  = np.asarray(positions, dtype=float)
        cell_ang = np.asarray(cell, dtype=float)
        sc_pos, sc_cell, sc_ia, sc_lvec, n_prim = build_supercell(pos_ang, cell_ang, symbols, super_n)
        n_sc = len(sc_pos)
        nPBC = (1, 1, 1) if self.hessian_pbc else (0, 0, 0)
        tmp_xyz = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.xyz', delete=False) as f:
                tmp_xyz = f.name
            sc_syms = [symbols[sc_ia[i]] for i in range(n_sc)]
            self._write_mmff_xyz(tmp_xyz, sc_pos, sc_lvec, sc_syms)  # positions in Ang
            print(f"[MMFF] Supercell {super_n}x{super_n}x{super_n} = {n_sc} atoms, Hessian nPBC={nPBC}...")
            MMFF = self._init_mmff()
            # setSwitches: call before init to enable angles/MMFF
            # NOTE: Explicitly disable PiSigma/PiPiI so bond scaling affects ALL
            # force constants. Otherwise unscaled PiSigma/PiPiI terms dominate
            # the dynamical matrix and bond scaling has almost no effect.
            switches = {"MMFF": 1, "NonBonded": -1, "Angles": 0, "PiSigma": 0, "PiPiI": 0}
            if self.enable_angles:
                switches["Angles"] = 1
            MMFF.setSwitches(**switches)
            dp = self._mmff_data_paths()
            MMFF.init(xyz_name=tmp_xyz, nPBC=nPBC, bEpairs=False, bMMFF=True, bUFF=self.use_uff,
                      sElementTypes=dp["ElementTypes"], sAtomTypes=dp["AtomTypes"],
                      sBondTypes=dp["BondTypes"], sAngleTypes=dp["AngleTypes"],
                      sDihedralTypes=dp["DihedralTypes"])
            # Apply parameter scaling if requested (using FireCore API)
            print(f"[MMFF] scale_bond={self.scale_bond}, scale_angle={self.scale_angle}")
            if self.scale_bond is not None:
                print("[MMFF] Calling getBuffs() for bond scaling...")
                MMFF.getBuffs()
                current_k = MMFF.bKs[MMFF.bKs != 0].mean()
                MMFF.setBondParamsByType('C_3', 'C_3', k=current_k * self.scale_bond, forcefield='MMFF')
                print(f"[MMFF] Scaled bond stiffness by {self.scale_bond}: {current_k:.3f} -> {current_k * self.scale_bond:.3f} eV/Å²")
            if self.scale_angle is not None:
                print("[MMFF] Calling getBuffs() for angle scaling...")
                MMFF.getBuffs()
                current_k = MMFF.apars[:, 1].mean()
                MMFF.setAngleParamsByType('C_3', 'C_3', 'C_3', k=current_k * self.scale_angle, forcefield='MMFF')
                print(f"[MMFF] Scaled angle stiffness by {self.scale_angle}: {current_k:.3f} -> {current_k * self.scale_angle:.3f} eV/rad²")
            # Use getPhononPhiBlocks like working FireCore script (displace central atoms, read forces on all)
            inds_total = np.arange(n_sc, dtype=np.int32)
            central_atoms = [i for i, c in enumerate(sc_cell) if c == (0, 0, 0)]
            inds_disp = np.array(central_atoms, dtype=np.int32)
            print(f"[MMFF] Central cell atoms: {central_atoms}")
            print(f"[MMFF] Computing Phi blocks (displace {len(inds_disp)} atoms, read forces on {n_sc})...")
            phi = MMFF.getPhononPhiBlocks(inds_total, inds_disp, dx=self.dx)
            if np.isnan(phi).any() or np.isinf(phi).any():
                raise ValueError("NaN/Inf in MMFF Phi matrix")
            print(f"[MMFF] Phi matrix shape: {phi.shape}, norm: {np.linalg.norm(phi):.6e}")
            # MMFF is eV/Ang throughout: Phi is in eV/Ang^2, cell in Ang
            Phi_blocks = _extract_phi_blocks_firecore(phi, sc_cell, sc_ia, central_atoms, n_prim)
            print(f"[MMFF] Extracted {len(Phi_blocks)} R-vector Phi blocks")
            return Phi_blocks, cell_ang  # cell in Ang, Phi in eV/Ang^2
        finally:
            if tmp_xyz and os.path.exists(tmp_xyz):
                os.unlink(tmp_xyz)

    def make_phonon_session(self, positions, cell, symbols, super_n, enable_angles=True, disable_pi=True, quiet=False):
        """Create reusable MMFFPhononSession for fast parameter scans."""
        return MMFFPhononSession(self, positions, cell, symbols, super_n, enable_angles=enable_angles, disable_pi=disable_pi, quiet=quiet)


class MMFFPhononSession:
    """Reusable MMFF session for fast param scans without reinitialization.

    Initializes MMFF once on an explicit NxNxN supercell and exposes:
      - in-place scaling of bond/angle stiffness via numpy buffer wrappers
      - repeated getPhononPhiBlocks() calls

    This is intended for tight loops (grid search / optimization) where MMFF
    init and I/O overhead would dominate.
    """

    def __init__(self, backend, positions, cell, symbols, super_n, enable_angles=True, disable_pi=True, quiet=False):
        self.backend = backend
        self.positions = np.asarray(positions, dtype=float)
        self.cell = np.asarray(cell, dtype=float)
        self.symbols = list(symbols)
        self.super_n = int(super_n)
        self.enable_angles = bool(enable_angles)
        self.disable_pi = bool(disable_pi)
        self.quiet = bool(quiet)

        from phonon_utils import build_supercell

        sc_pos, sc_cell, sc_ia, sc_lvec, n_prim = build_supercell(self.positions, self.cell, self.symbols, self.super_n)
        self.sc_pos = sc_pos
        self.sc_cell = sc_cell
        self.sc_ia = sc_ia
        self.sc_lvec = sc_lvec
        self.n_prim = int(n_prim)
        self.n_sc = len(sc_pos)
        self.central_atoms = [i for i, c in enumerate(sc_cell) if c == (0, 0, 0)]

        self.inds_total = np.arange(self.n_sc, dtype=np.int32)
        self.inds_disp = np.array(self.central_atoms, dtype=np.int32)

        self.tmp_xyz = None
        self.MMFF = None

        self._bKs0 = None
        self._apars0 = None
        self._bmask = None
        self._angle_col = 1  # consistent with compute_phi_blocks() scaling path

        self._init_once()

    def _init_once(self):
        with _suppress_native_output(self.quiet):
            tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.xyz', delete=False)
            tmp.close()
            self.tmp_xyz = tmp.name

            sc_syms = [self.symbols[self.sc_ia[i]] for i in range(self.n_sc)]
            self.backend._write_mmff_xyz(self.tmp_xyz, self.sc_pos, self.sc_lvec, sc_syms)

            MMFF = self.backend._init_mmff()
            switches = {"MMFF": 1, "NonBonded": -1, "Angles": 1 if self.enable_angles else 0}
            if self.disable_pi:
                switches["PiSigma"] = 0
                switches["PiPiI"] = 0
            MMFF.setSwitches(**switches)

            dp = self.backend._mmff_data_paths()
            nPBC = (1, 1, 1) if self.backend.hessian_pbc else (0, 0, 0)
            MMFF.init(xyz_name=self.tmp_xyz, nPBC=nPBC, bEpairs=False, bMMFF=True, bUFF=self.backend.use_uff,
                      sElementTypes=dp["ElementTypes"], sAtomTypes=dp["AtomTypes"],
                      sBondTypes=dp["BondTypes"], sAngleTypes=dp["AngleTypes"],
                      sDihedralTypes=dp["DihedralTypes"])
            MMFF.getBuffs()
            self.MMFF = MMFF

            self._bKs0 = np.array(MMFF.bKs, dtype=float).copy()
            self._apars0 = np.array(MMFF.apars, dtype=float).copy()
            self._bmask = self._bKs0 != 0.0

    def set_scales(self, scale_bond=1.0, scale_angle=1.0):
        """Set bond and angle stiffness scales in-place (no MMFF reinit)."""
        if self.MMFF is None:
            raise RuntimeError("MMFFPhononSession is not initialized")
        sb = float(scale_bond)
        sa = float(scale_angle)
        self.MMFF.bKs[self._bmask] = self._bKs0[self._bmask] * sb
        self.MMFF.apars[:, self._angle_col] = self._apars0[:, self._angle_col] * sa

    def compute_phi_blocks(self, dx=None):
        """Compute Phi(0,R) blocks for current parameters."""
        if self.MMFF is None:
            raise RuntimeError("MMFFPhononSession is not initialized")
        dx = float(self.backend.dx if dx is None else dx)
        with _suppress_native_output(self.quiet):
            phi = self.MMFF.getPhononPhiBlocks(self.inds_total, self.inds_disp, dx=dx)
        if np.isnan(phi).any() or np.isinf(phi).any():
            raise ValueError("NaN/Inf in MMFF Phi matrix")
        return _extract_phi_blocks_firecore(phi, self.sc_cell, self.sc_ia, self.central_atoms, self.n_prim)

    def close(self):
        if self.tmp_xyz and os.path.exists(self.tmp_xyz):
            os.unlink(self.tmp_xyz)
        self.tmp_xyz = None
        self.MMFF = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()



# ============================================================================
# Parsers
# ============================================================================

def _parse_dftb_results_tag(path, natoms):
    with open(path) as f:
        text = f.read()
    match = re.search(r'forces\s+:real:2:3,(\d+)\n', text)
    if not match:
        raise RuntimeError(f"forces block not found in {path}")
    n = int(match.group(1))
    start = match.end()
    lines = text[start:].strip().split('\n')
    forces = []
    for i in range(natoms):
        parts = lines[i].strip().split()
        forces.append([float(parts[0]), float(parts[1]), float(parts[2])])
    return np.array(forces, dtype=float)


def _parse_lammps_dump(path, natoms):
    with open(path) as f:
        lines = f.readlines()
    atom_start = -1
    for i, line in enumerate(lines):
        if line.startswith("ITEM: ATOMS"):
            atom_start = i
    if atom_start < 0:
        raise RuntimeError(f"No ATOMS section in {path}")
    forces = [None] * natoms
    for i in range(atom_start + 1, len(lines)):
        parts = lines[i].strip().split()
        if len(parts) < 5:
            continue
        atom_id = int(parts[0]) - 1
        forces[atom_id] = [float(parts[2]), float(parts[3]), float(parts[4])]
    if None in forces:
        raise RuntimeError(f"Missing forces in {path}")
    return np.array(forces, dtype=float)


# ============================================================================
# Factory
# ============================================================================

def make_backend(method, config=None, **kwargs):
    """Factory to create a backend from method name and config.
    
    method: 'dftb', 'tersoff', 'sw', 'meam', 'mtp', 'mmff'
    config: dict with tool paths (from phonon_config.json)
    """
    config = config or {}
    
    if method == "dftb":
        tools = config.get("tools", {})
        return DFTBBackend(
            dftb_bin=tools.get("dftb_bin", "dftb+"),
            slakos_dir=tools.get("slakos_dir", ""),
        )
    
    elif method in ("tersoff", "sw", "meam", "mtp"):
        tools = config.get("tools", {})
        pot_paths = config.get("potentials", {})
        return LAMMPSBackend(
            lammps_bin=tools.get("lammps_bin", "lmp_serial"),
            potential=method,
            pot_paths=pot_paths,
            mtp_file=kwargs.get("mtp_file"),
        )
    
    elif method == "mmff":
        tools = config.get("tools", {})
        firecore_path = kwargs.get("firecore_path") or tools.get("firecore_path") or os.environ.get("FIRECORE_PATH", "")
        mmff_data_dir = kwargs.get("mmff_data_dir") or tools.get("mmff_data_dir") or ""
        return MMFFBackend(
            firecore_path=firecore_path, mmff_data_dir=mmff_data_dir,
            dx=kwargs.get("dx", 1e-4),
            fc_mode=kwargs.get("fc_mode", "hessian"),
            hessian_pbc=kwargs.get("hessian_pbc", True),
            enable_angles=kwargs.get("enable_angles", False),
            use_uff=kwargs.get("use_uff", False),
            scale_bond=kwargs.get("scale_bond"),
            scale_angle=kwargs.get("scale_angle"),
        )
    
    else:
        raise ValueError(f"Unknown method: {method}")
