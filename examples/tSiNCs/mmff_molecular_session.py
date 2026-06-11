#!/usr/bin/env python3
"""
Reusable MMFF session for molecular vibration calculations (no k-space).

Similar to MMFFPhononSession but for isolated molecules using getHessian3Nx3N.
"""

import os
import tempfile
import numpy as np


class MMFFMolecularSession:
    """Reusable MMFF session for molecular vibration calculations.

    Initializes MMFF once and exposes:
      - in-place scaling of bond/angle stiffness via numpy buffer wrappers
      - repeated getHessian3Nx3N() calls

    This is intended for tight loops (grid search / optimization) where MMFF
    init and I/O overhead would dominate.
    """

    def __init__(self, positions, symbols, firecore_path=None, enable_angles=True, quiet=False):
        self.positions = np.asarray(positions, dtype=float)
        self.symbols = list(symbols)
        self.n_atoms = len(symbols)
        self.firecore_path = firecore_path or os.environ.get('FIRECORE_PATH', '/home/prokop/git/FireCore')
        self.enable_angles = bool(enable_angles)
        self.quiet = bool(quiet)

        self.tmp_xyz = None
        self.MMFF = None

        self._bKs0 = None
        self._apars0 = None
        self._bmask = None
        self._angle_col = 1

        self._perm_int2in = None
        self._perm_in2int = None

        self._init_once()

    def _init_once(self):
        """Initialize MMFF once, save original buffer values."""
        import sys
        sys.path.insert(0, self.firecore_path)
        from pyBall import MMFF

        tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.xyz', delete=False)
        tmp.close()
        self.tmp_xyz = tmp.name

        # Write XYZ
        with open(self.tmp_xyz, 'w') as f:
            f.write(f"{self.n_atoms}\n")
            f.write("MMFF molecular\n")
            for s, p in zip(self.symbols, self.positions):
                f.write(f"{s}  {p[0]:.8f}  {p[1]:.8f}  {p[2]:.8f}\n")

        # Data paths
        data_dir = os.path.join(self.firecore_path, "cpp/common_resources")
        dp = {
            "ElementTypes": os.path.join(data_dir, "ElementTypes.dat"),
            "AtomTypes": os.path.join(data_dir, "AtomTypes.dat"),
            "BondTypes": os.path.join(data_dir, "BondTypes.dat"),
            "AngleTypes": os.path.join(data_dir, "AngleTypes.dat"),
            "DihedralTypes": os.path.join(data_dir, "DihedralTypes.dat"),
        }

        # Set switches
        switches = {"MMFF": 1, "NonBonded": -1, "Angles": 0, "PiSigma": 0, "PiPiI": 0}
        if self.enable_angles:
            switches["Angles"] = 1
        MMFF.setSwitches(**switches)

        # Init with nPBC=(0,0,0) for isolated molecule
        ptr = MMFF.init(xyz_name=self.tmp_xyz, nPBC=(0, 0, 0), bEpairs=False, bMMFF=True,
                        sElementTypes=dp["ElementTypes"], sAtomTypes=dp["AtomTypes"],
                        sBondTypes=dp["BondTypes"], sAngleTypes=dp["AngleTypes"],
                        sDihedralTypes=dp["DihedralTypes"])
        if ptr is None:
            raise RuntimeError(f"MMFF.init failed for {self.tmp_xyz}")

        # Get buffers and save originals
        MMFF.getBuffs()
        self.MMFF = MMFF

        apos = np.array(MMFF.apos, dtype=float)
        D = np.linalg.norm(apos[:, None, :] - self.positions[None, :, :], axis=2)
        perm_int2in = np.argmin(D, axis=1).astype(np.int32)
        if len(set(perm_int2in.tolist())) != self.n_atoms:
            raise RuntimeError("Failed to build a unique internal->input atom mapping")
        if np.max(np.min(D, axis=1)) > 1e-6:
            raise RuntimeError("Internal atom positions do not match input positions (mapping ambiguous)")
        perm_in2int = np.empty_like(perm_int2in)
        perm_in2int[perm_int2in] = np.arange(self.n_atoms, dtype=np.int32)
        self._perm_int2in = perm_int2in
        self._perm_in2int = perm_in2int

        self._bKs0 = np.array(MMFF.bKs, dtype=float).copy()
        self._apars0 = np.array(MMFF.apars, dtype=float).copy()
        self._bmask = self._bKs0 != 0.0

    def set_scales(self, scale_bond=1.0, scale_angle=1.0):
        """Set bond and angle stiffness scales in-place (no MMFF reinit)."""
        if self.MMFF is None:
            raise RuntimeError("MMFFMolecularSession is not initialized")
        sb = float(scale_bond)
        sa = float(scale_angle)
        self.MMFF.bKs[self._bmask] = self._bKs0[self._bmask] * sb
        self.MMFF.apars[:, self._angle_col] = self._apars0[:, self._angle_col] * sa

    def set_scales_per_bond_type(self, scale_ch=1.0, scale_cc=1.0, scale_angle=1.0):
        """Set bond stiffness scales per bond type (C-H vs C-C) in-place."""
        if self.MMFF is None:
            raise RuntimeError("MMFFMolecularSession is not initialized")

        sch = float(scale_ch)
        scc = float(scale_cc)
        sa  = float(scale_angle)

        neighs = self.MMFF.neighs
        nnode  = int(self.MMFF.nnode)
        valid  = neighs >= 0
        is_cc  = valid & (neighs < nnode)
        is_ch  = valid & (neighs >= nnode)

        self.MMFF.bKs[:] = self._bKs0
        self.MMFF.bKs[is_cc] = self._bKs0[is_cc] * scc
        self.MMFF.bKs[is_ch] = self._bKs0[is_ch] * sch
        self.MMFF.apars[:, self._angle_col] = self._apars0[:, self._angle_col] * sa

    def get_hessian(self, dx=1e-4):
        """Compute Hessian for current parameters."""
        if self.MMFF is None:
            raise RuntimeError("MMFFMolecularSession is not initialized")

        inds = np.arange(self.n_atoms, dtype=np.int32)
        hess = self.MMFF.getHessian3Nx3N(inds, dx=dx)
        hess = 0.5 * (hess + hess.T)  # Symmetrize
        return hess

    def compute_frequencies(self, masses, dx=1e-4):
        """Compute vibrational frequencies from Hessian."""
        hess = self.get_hessian(dx=dx)

        masses = np.asarray(masses, dtype=float)
        if masses.shape[0] != self.n_atoms:
            raise ValueError(f"masses has wrong length {masses.shape[0]} (expected {self.n_atoms})")
        masses_int = masses[self._perm_int2in]

        # Mass-weighted Hessian
        masses_3n = np.repeat(masses_int, 3)
        H_mw = hess / np.sqrt(np.outer(masses_3n, masses_3n))

        # Eigenvalues
        eigvals, eigvecs = np.linalg.eigh(H_mw)

        # Convert to frequencies
        FREQ_EV_AMU_ANG2_TO_THZ = 15.633728205761277
        THZ_TO_CM = 33.356

        freqs_thz = np.sqrt(np.maximum(eigvals, 0.0)) * FREQ_EV_AMU_ANG2_TO_THZ
        freqs_cm = freqs_thz * THZ_TO_CM

        # Keep vibrational subspace (remove translations+rotations)
        vib_idx = np.arange(6, self.n_atoms * 3, dtype=np.int32)
        freqs_vib = freqs_cm[vib_idx]
        modes_array = eigvecs[:, vib_idx].T

        inv = self._perm_in2int
        modes = [m.reshape(self.n_atoms, 3)[inv] for m in modes_array]

        dof_idx = np.empty(self.n_atoms * 3, dtype=np.int32)
        for ia in range(self.n_atoms):
            ii = inv[ia]
            dof_idx[3 * ia + 0] = 3 * ii + 0
            dof_idx[3 * ia + 1] = 3 * ii + 1
            dof_idx[3 * ia + 2] = 3 * ii + 2
        hess = hess[dof_idx][:, dof_idx]

        return freqs_vib, modes, hess

    def close(self):
        if self.tmp_xyz and os.path.exists(self.tmp_xyz):
            os.unlink(self.tmp_xyz)
        self.tmp_xyz = None
        self.MMFF = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
