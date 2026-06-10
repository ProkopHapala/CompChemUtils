#!/usr/bin/env python3
"""
phonon_utils.py
===============
Core utilities for the modular phonon band-structure pipeline.

- Structure loading: .cif (ASE), .xyz with lvs, standard .xyz
- QPath: exact q-point files OR segment-based generation
- PhononCalculator: backend-agnostic FC computation with caching
"""

import os
import sys
import json
import hashlib
import tempfile
import argparse
from pathlib import Path

import numpy as np


# ============================================================================
# Structure loaders
# ============================================================================

def read_structure(path):
    """Load atomic structure from .cif, .xyz (with lvs), or standard .xyz.
    
    Returns: positions (N,3) Ang, cell (3,3) Ang, symbols list, is_primitive bool
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Structure file not found: {path}")
    
    suffix = path.suffix.lower()
    if suffix == '.cif':
        return _read_cif(path)
    elif suffix == '.xyz':
        return _read_xyz(path)
    else:
        raise ValueError(f"Unsupported structure format: {suffix}")


def _read_cif(path):
    """Read .cif via ASE."""
    from ase.io import read
    atoms = read(str(path))
    return (
        atoms.get_positions(),
        atoms.get_cell(),
        atoms.get_chemical_symbols(),
        True  # .cif is typically primitive
    )


def _read_xyz(path):
    """Read .xyz; detect custom 'lvs' lattice-vector comment line."""
    with open(path) as f:
        natoms = int(f.readline().strip())
        comment = f.readline().strip()
        
        # Check for custom lvs format: "lvs  a1x a1y a1z  a2x a2y a2z  a3x a3y a3z"
        parts = comment.split()
        if len(parts) >= 10 and parts[0].lower() == 'lvs':
            vals = list(map(float, parts[1:10]))
            cell = np.array(vals).reshape(3, 3)
            symbols, pos = [], []
            for _ in range(natoms):
                tok = f.readline().strip().split()
                symbols.append(tok[0])
                pos.append([float(tok[1]), float(tok[2]), float(tok[3])])
            return np.array(pos), cell, symbols, True
        else:
            # Standard XYZ — use ASE
            from ase.io import read
            atoms = read(str(path))
            return atoms.get_positions(), atoms.get_cell(), atoms.get_chemical_symbols(), True


# ============================================================================
# Q-point path handling
# ============================================================================

class QPath:
    """Container for q-points along a band-structure path.
    
    Supports two construction modes:
      1. from_file()  — exact q-points from a .dat file
      2. from_segments() — linear interpolation between high-symmetry points
    """
    
    def __init__(self, qpts, labels=None, distances=None, segments=None):
        """
        qpts:       (N, 3) array, fractional reciprocal coordinates
        labels:     list of str length N (optional)
        distances:  1D array length N (optional, cumulative path distance)
        segments:   list of (start_idx, end_idx) tuples (optional)
        """
        self.qpts = np.asarray(qpts, dtype=float)
        self.labels = labels or [''] * len(self.qpts)
        self.distances = distances if distances is not None else self._compute_distances()
        self.segments = segments
        
        assert self.qpts.ndim == 2 and self.qpts.shape[1] == 3
        assert len(self.labels) == len(self.qpts)
        assert len(self.distances) == len(self.qpts)
    
    def __len__(self):
        return len(self.qpts)
    
    @classmethod
    def from_file(cls, path):
        """Load from .dat file: # qx qy qz distance [freqs...] label"""
        qpts, dists, labels = [], [], []
        with open(path) as f:
            next(f)  # skip header
            for line in f:
                parts = line.strip().split()
                if len(parts) < 4:
                    continue
                qpts.append([float(parts[0]), float(parts[1]), float(parts[2])])
                dists.append(float(parts[3]))
                # Label is last column if non-numeric
                label = ""
                if len(parts) >= 5:
                    try:
                        float(parts[-1])
                    except ValueError:
                        label = parts[-1]
                labels.append(label)
        
        qpts = np.array(qpts)
        dists = np.array(dists)
        
        # Detect segment boundaries
        segments = _detect_segments(qpts, dists)
        
        return cls(qpts, labels=labels, distances=dists, segments=segments)
    
    @classmethod
    def from_segments(cls, high_sym_points, npts_per_seg=40):
        """Generate q-path from high-symmetry points.
        
        high_sym_points: dict {label: [qx,qy,qz]} or list of (label, qpt) tuples
        npts_per_seg: int or list of ints (one per segment)
        
        Returns QPath with linearly interpolated q-points.
        """
        if isinstance(high_sym_points, dict):
            items = list(high_sym_points.items())
        else:
            items = high_sym_points
        
        if isinstance(npts_per_seg, int):
            npts_per_seg = [npts_per_seg] * (len(items) - 1)
        
        qpts_all, labels_all, dists_all = [], [], []
        cumulative_dist = 0.0
        
        for i in range(len(items) - 1):
            lab1, q1 = items[i]
            lab2, q2 = items[i + 1]
            q1 = np.asarray(q1, dtype=float)
            q2 = np.asarray(q2, dtype=float)
            npts = npts_per_seg[i]
            
            for j in range(npts):
                t = j / (npts - 1) if npts > 1 else 0
                q = q1 + t * (q2 - q1)
                qpts_all.append(q)
                
                if j == 0:
                    labels_all.append(lab1)
                else:
                    labels_all.append('')
                
                if j > 0:
                    dq = qpts_all[-1] - qpts_all[-2]
                    cumulative_dist += np.linalg.norm(dq)
                dists_all.append(cumulative_dist)
        
        # Last point
        qpts_all.append(np.asarray(items[-1][1], dtype=float))
        labels_all.append(items[-1][0])
        dq = qpts_all[-1] - qpts_all[-2]
        cumulative_dist += np.linalg.norm(dq)
        dists_all.append(cumulative_dist)
        
        return cls(np.array(qpts_all), labels=labels_all, distances=np.array(dists_all))
    
    def _compute_distances(self):
        """Compute cumulative path distance from q-points."""
        dists = np.zeros(len(self.qpts))
        for i in range(1, len(self.qpts)):
            dists[i] = dists[i-1] + np.linalg.norm(self.qpts[i] - self.qpts[i-1])
        return dists
    
    def get_segment_boundaries(self):
        """Return indices of segment boundaries (labels or large jumps)."""
        if self.segments:
            return [s[0] for s in self.segments] + [self.segments[-1][1]]
        
        # Detect from labels or jumps
        boundaries = [0]
        for i in range(1, len(self.qpts)):
            if self.labels[i]:
                boundaries.append(i)
            elif np.linalg.norm(self.qpts[i] - self.qpts[i-1]) > 0.1:
                boundaries.append(i)
        boundaries.append(len(self.qpts))
        return sorted(set(boundaries))
    
    def to_phonopy_segments(self):
        """Convert to phonopy run_band_structure format: (segments, labels, connections)."""
        boundaries = self.get_segment_boundaries()
        segments = []
        seg_labels = []
        
        for i in range(len(boundaries) - 1):
            start = boundaries[i]
            end = boundaries[i + 1]
            seg = self.qpts[start:end]
            if len(seg) >= 2:
                segments.append(seg)
                start_lab = self.labels[start] if start < len(self.labels) else ""
                end_lab = self.labels[end-1] if (end-1) < len(self.labels) else ""
                seg_labels.append((start_lab, end_lab))
        
        # phonopy expects connected segments with endpoint labels
        path_connections = [True] * (len(segments) - 1) + [False]
        phonopy_labels = []
        for i, (s_lab, e_lab) in enumerate(seg_labels):
            if i == 0:
                phonopy_labels.append(s_lab if s_lab else "?")
            phonopy_labels.append(e_lab if e_lab else "?")
        
        return segments, path_connections, phonopy_labels
    
    def save_dat(self, path, freqs=None):
        """Save q-path to .dat file (optionally with frequencies)."""
        with open(path, 'w') as f:
            f.write("# qx qy qz distance")
            if freqs is not None:
                for b in range(freqs.shape[1]):
                    f.write(f" band{b+1}")
            f.write(" label\n")
            
            for i, (q, d) in enumerate(zip(self.qpts, self.distances)):
                f.write(f"{q[0]:12.8f} {q[1]:12.8f} {q[2]:12.8f} {d:12.8f}")
                if freqs is not None:
                    for fr in freqs[i]:
                        f.write(f" {fr:12.8f}")
                lab = self.labels[i] if i < len(self.labels) else ""
                f.write(f" {lab}\n")


def _detect_segments(qpts, dists):
    """Detect segment boundaries from q-points and distances."""
    boundaries = {0, len(qpts)}
    
    # Duplicate q-points
    for i in range(1, len(qpts)):
        if np.allclose(qpts[i], qpts[i-1], atol=1e-6):
            boundaries.add(i)
    
    # Negative distance jumps
    diffs = np.diff(dists)
    for i in range(len(diffs)):
        if diffs[i] < -1e-6:
            boundaries.add(i + 1)
    
    # Large q-space jumps (minimum image)
    dq = np.diff(qpts, axis=0)
    dq = dq - np.round(dq)
    qjumps = np.linalg.norm(dq, axis=1)
    for i in range(len(qjumps)):
        if qjumps[i] > 0.05:
            boundaries.add(i + 1)
    
    boundaries = sorted(boundaries)
    segments = []
    for i in range(len(boundaries) - 1):
        start = boundaries[i]
        end = boundaries[i + 1]
        if end - start >= 2:
            segments.append((start, end))
    
    return segments


# ============================================================================
# Force-constant cache
# ============================================================================

def _hash_structure(positions, cell, symbols, supercell, backend_name, backend_config):
    """Compute a deterministic hash for caching."""
    h = hashlib.sha256()
    h.update(positions.tobytes())
    h.update(cell.tobytes())
    h.update(''.join(symbols).encode())
    h.update(str(supercell).encode())
    h.update(backend_name.encode())
    h.update(json.dumps(backend_config, sort_keys=True).encode())
    return h.hexdigest()[:16]


class PhononCalculator:
    """Backend-agnostic phonon calculator with force-constant caching.
    
    Uses phonopy internally for displacement generation and FC construction.
    Supports arbitrary q-point evaluation via phonopy's get_frequencies_with_eigenvectors.
    """
    
    def __init__(self, positions, cell, symbols, supercell, backend, outdir,
                 primitive_matrix='auto', masses=None,
                 band_solver=None, freq_convention='positive'):
        """
        positions: (N,3) Ang
        cell:      (3,3) Ang
        symbols:   list of str length N
        supercell: int or [nx, ny, nz]
        backend:   object with compute_forces(positions, cell, symbols, outdir, disp_idx)
        outdir:    str, directory for cache and displacement outputs
        primitive_matrix: 'auto' or explicit 3x3 matrix
        masses:    list of floats (optional, auto-detected from symbols)
        """
        self.positions = np.asarray(positions, dtype=float)
        self.cell = np.asarray(cell, dtype=float)
        self.symbols = list(symbols)
        self.supercell = supercell if hasattr(supercell, '__iter__') else [supercell]*3
        self.backend = backend
        self.outdir = Path(outdir)
        self.outdir.mkdir(parents=True, exist_ok=True)
        self.primitive_matrix = primitive_matrix
        
        # Auto-detect masses if not provided
        if masses is None:
            masses = _get_masses(symbols)
        self.masses = np.asarray(masses, dtype=float)
        
        # Phonopy objects
        self._phonon = None
        self._force_constants = None
        self._dirty = True
        self._hessian_mode = getattr(backend, 'is_hessian_backend', False)
        self._phi_blocks = None
        self._hessian_cell = None  # Bohr lattice for Phi/R_cart consistency
        self.band_solver = band_solver or ('unified' if self._hessian_mode else 'phonopy')
        self.freq_convention = freq_convention
        
        # Cache file
        self._cache_file = self.outdir / 'force_constants.npz'
        self._state_file = self.outdir / 'phonon_state.json'

    @classmethod
    def from_cached_results(cls, result_dir, config=None, structure_search=None):
        """Restore calculator from a prior run directory (force_constants or hessian cache)."""
        result_dir = Path(result_dir)
        meta_path = result_dir / 'phonon_bands.npz'
        if not meta_path.exists():
            raise FileNotFoundError(f"No phonon_bands.npz in {result_dir}")
        meta = np.load(meta_path, allow_pickle=True)
        method = str(meta['method'])
        supercell = [int(x) for x in str(meta['supercell']).split('x')]
        sf = str(meta.get('structure_file', 'diamond_primitive.cif'))
        if config is None:
            config = {}
        tools = config.get('tools', {})
        if method == 'mmff':
            from phonon_backends import resolve_mmff_structure, make_backend
            fc_path = tools.get('firecore_path') or os.environ.get('FIRECORE_PATH', '')
            structure_path = resolve_mmff_structure(sf, fc_path)
        else:
            from phonon_backends import make_backend
            repo_root = Path(__file__).resolve().parents[2]
            structure_search = structure_search or [repo_root / 'data' / 'crystals']
            structure_path = None
            for root in structure_search:
                cand = Path(root) / sf
                if cand.exists():
                    structure_path = cand
                    break
            if structure_path is None:
                raise FileNotFoundError(f"Structure file {sf} not found under {structure_search}")
        positions, cell, symbols, _ = read_structure(structure_path)
        if method == 'mmff':
            from phonon_backends import BOHR_TO_ANG
            positions = positions * BOHR_TO_ANG
            cell = cell * BOHR_TO_ANG
        fc_mode = 'hessian' if (result_dir / 'hessian_phi_blocks.npz').exists() and not (result_dir / 'force_constants.npz').exists() else 'phonopy'
        backend = make_backend(method, config=config, fc_mode=fc_mode)
        calc = cls(positions, cell, symbols, supercell, backend, result_dir)
        if calc._hessian_mode:
            if not (result_dir / 'hessian_phi_blocks.npz').exists():
                raise FileNotFoundError(f"No hessian_phi_blocks.npz in {result_dir}")
            calc._compute_hessian_force_constants(force_recompute=False)
        else:
            if calc._load_cache() is None:
                raise FileNotFoundError(f"Could not load force_constants.npz from {result_dir}")
        return calc
    
    @property
    def n_atoms(self):
        return len(self.symbols)
    
    @property
    def dirty(self):
        return self._dirty
    
    @dirty.setter
    def dirty(self, value):
        self._dirty = value
    
    def _get_current_state(self):
        """Return serializable state dict for cache invalidation."""
        return {
            'hash': _hash_structure(
                self.positions, self.cell, self.symbols,
                self.supercell, self.backend.name, self.backend.config
            ),
            'n_atoms': self.n_atoms,
            'symbols': self.symbols,
            'supercell': self.supercell,
            'backend_name': self.backend.name,
        }
    
    def _init_phonopy(self):
        """Initialize phonopy with current structure."""
        from phonopy import Phonopy
        from phonopy.structure.atoms import PhonopyAtoms
        
        atoms = PhonopyAtoms(
            symbols=self.symbols,
            positions=self.positions,
            cell=self.cell,
            masses=self.masses,
        )
        
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            phonon = Phonopy(
                atoms,
                supercell_matrix=self.supercell,
                primitive_matrix=self.primitive_matrix,
            )
        return phonon
    
    def compute_force_constants(self, force_recompute=False):
        """Compute force constants. Skip if cached.
        
        Returns: phonopy force_constants array (n_primitive, n_supercell, 3, 3)
        """
        if self._hessian_mode:
            return self._compute_hessian_force_constants(force_recompute)
        if not force_recompute:
            if self._force_constants is not None:
                return self._force_constants
            if self._cache_file.exists():
                loaded = self._load_cache()
                if loaded is not None:
                    return loaded
        
        print(f"[phonon] Computing force constants (backend: {self.backend.name})")
        
        phonon = self._init_phonopy()
        phonon.generate_displacements()
        displacements = phonon.displacements
        print(f"[phonon] {len(displacements)} displacement structures")
        
        force_sets = []
        for i, disp in enumerate(displacements):
            disp_dir = self.outdir / f"disp-{i+1:03d}"
            disp_dir.mkdir(exist_ok=True)
            
            # Build displaced supercell
            supercell = phonon.supercell.copy()
            pos = supercell.positions.copy()
            atom_idx = int(disp[0])
            pos[atom_idx] += np.array(disp[1:4])
            supercell.positions = pos
            
            forces = self.backend.compute_forces(
                supercell.positions,
                supercell.cell,
                [s for s in supercell.symbols],
                str(disp_dir),
                i,
            )
            force_sets.append(forces)
            max_f = np.max(np.abs(forces))
            print(f"[phonon]   disp {i+1}/{len(displacements)} max|F|={max_f:.4f} eV/A")
        
        phonon.forces = force_sets
        phonon.produce_force_constants()
        self._force_constants = phonon.force_constants
        self._phonon = phonon
        self._dirty = False
        self._save_cache()
        
        return self._force_constants
    
    def _compute_hessian_force_constants(self, force_recompute=False):
        """Hessian-based FC extraction (MMFF supercell workflow)."""
        hess_cache = self.outdir / 'hessian_phi_blocks.npz'
        if not force_recompute and hess_cache.exists() and self._state_file.exists():
            with open(self._state_file) as f:
                cached_state = json.load(f)
            if cached_state.get('hash') == self._get_current_state()['hash']:
                data = np.load(hess_cache, allow_pickle=True)
                self._phi_blocks = {tuple(k): data[f'phi_{i}'] for i, k in enumerate(data['R_keys'])}
                self._hessian_cell = data['hessian_cell']
                self._dirty = False
                print(f"[phonon] Loaded cached Hessian Phi blocks: {hess_cache}")
                return self._phi_blocks
        if not hasattr(self.backend, 'compute_phi_blocks'):
            raise RuntimeError(f"Backend {self.backend.name} claims hessian mode but has no compute_phi_blocks()")
        super_n = self.supercell[0]
        if not all(s == super_n for s in self.supercell):
            raise ValueError(f"Hessian backend requires cubic supercell NxNxN, got {self.supercell}")
        print(f"[phonon] Computing Hessian on {super_n}x{super_n}x{super_n} supercell (backend: {self.backend.name})")
        self._phi_blocks, self._hessian_cell = self.backend.compute_phi_blocks(
            self.positions, self.cell, self.symbols, super_n)
        self._dirty = False
        state = self._get_current_state()
        with open(self._state_file, 'w') as f:
            json.dump(state, f, indent=2)
        R_keys = np.array(list(self._phi_blocks.keys()))
        save_dict = {'R_keys': R_keys, 'hessian_cell': self._hessian_cell}
        for i, k in enumerate(R_keys):
            save_dict[f'phi_{i}'] = self._phi_blocks[tuple(k)]
        np.savez(hess_cache, **save_dict)
        print(f"[phonon] Cached Hessian Phi blocks: {hess_cache}")
        return self._phi_blocks

    def get_phonopy(self):
        """Return phonopy object with force constants loaded."""
        self.compute_force_constants()
        if self._hessian_mode:
            raise RuntimeError("phonopy object not available for hessian backends")
        if self._phonon is None:
            self._phonon = self._init_phonopy()
            self._phonon.force_constants = self._force_constants
        return self._phonon

    def get_phi_blocks(self):
        """Return Phi(0,R) blocks, cell, masses, and fc_units for unified solver."""
        if self._hessian_mode:
            self.compute_force_constants()
            # MMFF getPhononPhiBlocks returns Phi in eV/Å² (same as phonopy)
            return self._phi_blocks, self._hessian_cell, self.masses, 'ev_ang2'
        phonon = self.get_phonopy()
        phi = phi_blocks_from_phonopy_fc(phonon)
        prim = phonon.primitive
        return phi, np.asarray(prim.cell, float), np.asarray(prim.masses, float), 'ev_ang2'

    def solve_bands(self, qpath, band_solver=None, freq_convention=None):
        """Evaluate phonon frequencies at arbitrary q-points.
        
        band_solver: 'phonopy' | 'unified'  (default: self.band_solver)
        freq_convention: 'positive' | 'signed'  (unified solver only; phonopy is always positive)
        """
        band_solver = band_solver or self.band_solver
        freq_convention = freq_convention or self.freq_convention
        if self._hessian_mode and band_solver == 'phonopy':
            raise ValueError("hessian backends (MMFF) require band_solver='unified'")
        if band_solver == 'phonopy':
            phonon = self.get_phonopy()
            freqs = solve_bands_phonopy(phonon, qpath.qpts)
        elif band_solver == 'unified':
            phi, cell, masses, fc_units = self.get_phi_blocks()
            freqs = solve_bands_from_phi(phi, cell, masses, qpath.qpts, fc_units=fc_units, convention=freq_convention)
        else:
            raise ValueError(f"Unknown band_solver: {band_solver}")
        return freqs, qpath.distances, qpath.labels

    def check_band_solver_parity(self, qpath, tol=0.01, freq_convention='positive'):
        """Compare phonopy vs unified band solvers on identical FC data."""
        if self._hessian_mode:
            print("[parity] hessian backend: phonopy solver N/A (MMFF cluster FC only)")
            return None
        return check_band_solver_parity(self, qpath, tol=tol, freq_convention=freq_convention)
    
    def solve_bands_phonopy_format(self, qpath):
        """Use phonopy run_band_structure for standard phonopy output format.
        
        This is useful for generating band.yaml compatible with phonopy tools.
        """
        fc = self.compute_force_constants()
        
        if self._phonon is None:
            self._phonon = self._init_phonopy()
            self._phonon.force_constants = fc
        
        segments, connections, labels = qpath.to_phonopy_segments()
        self._phonon.run_band_structure(segments, labels=labels, path_connections=connections)
        return self._phonon.get_band_structure_dict()
    
    def save_band_yaml(self, path, qpath=None):
        """Save phonopy band.yaml (requires phonopy run_band_structure first)."""
        if qpath is not None:
            self.solve_bands_phonopy_format(qpath)
        self._phonon.write_yaml_band_structure(filename=str(path))
        print(f"[phonon] Saved band.yaml: {path}")
    
    def _save_cache(self):
        """Save force constants and state to disk."""
        state = self._get_current_state()
        with open(self._state_file, 'w') as f:
            json.dump(state, f, indent=2)
        
        np.savez(
            self._cache_file,
            force_constants=self._force_constants,
            positions=self.positions,
            cell=self.cell,
            symbols=np.array(self.symbols, dtype=str),
            masses=self.masses,
            supercell=np.array(self.supercell),
        )
        print(f"[phonon] Cached force constants: {self._cache_file}")
    
    def _load_cache(self):
        """Load force constants from disk if state matches."""
        if not self._state_file.exists():
            return None
        
        with open(self._state_file) as f:
            cached_state = json.load(f)
        
        current_state = self._get_current_state()
        if cached_state.get('hash') != current_state['hash']:
            print("[phonon] Cache invalidated (structure/backend changed)")
            return None
        
        if not self._cache_file.exists():
            return None
        
        data = np.load(self._cache_file)
        self._force_constants = data['force_constants']
        
        # Restore phonopy
        self._phonon = self._init_phonopy()
        self._phonon.force_constants = self._force_constants
        
        self._dirty = False
        print(f"[phonon] Loaded cached force constants: {self._cache_file}")
        return self._force_constants


def _get_masses(symbols):
    """Get atomic masses from symbols (amu)."""
    # Standard atomic masses (IUPAC 2021)
    ATOMIC_MASSES = {
        'H': 1.008, 'He': 4.0026, 'Li': 6.94, 'Be': 9.0122, 'B': 10.81,
        'C': 12.011, 'N': 14.007, 'O': 15.999, 'F': 18.998, 'Ne': 20.180,
        'Na': 22.990, 'Mg': 24.305, 'Al': 26.982, 'Si': 28.0855, 'P': 30.974,
        'S': 32.06, 'Cl': 35.45, 'Ar': 39.948, 'K': 39.098, 'Ca': 40.078,
        'Sc': 44.956, 'Ti': 47.867, 'V': 50.942, 'Cr': 51.996, 'Mn': 54.938,
        'Fe': 55.845, 'Co': 58.933, 'Ni': 58.693, 'Cu': 63.546, 'Zn': 65.38,
        'Ga': 69.723, 'Ge': 72.630, 'As': 74.922, 'Se': 78.971, 'Br': 79.904,
        'Kr': 83.798, 'Rb': 85.468, 'Sr': 87.62, 'Y': 88.906, 'Zr': 91.224,
        'Nb': 92.906, 'Mo': 95.95, 'Tc': 98.0, 'Ru': 101.07, 'Rh': 102.91,
        'Pd': 106.42, 'Ag': 107.87, 'Cd': 112.41, 'In': 114.82, 'Sn': 118.71,
        'Sb': 121.76, 'Te': 127.60, 'I': 126.90, 'Xe': 131.29, 'Cs': 132.91,
        'Ba': 137.33, 'La': 138.91, 'Ce': 140.12, 'Pr': 140.91, 'Nd': 144.24,
        'Pm': 145.0, 'Sm': 150.36, 'Eu': 151.96, 'Gd': 157.25, 'Tb': 158.93,
        'Dy': 162.50, 'Ho': 164.93, 'Er': 167.26, 'Tm': 168.93, 'Yb': 173.05,
        'Lu': 174.97, 'Hf': 178.49, 'Ta': 180.95, 'W': 183.84, 'Re': 186.21,
        'Os': 190.23, 'Ir': 192.22, 'Pt': 195.08, 'Au': 196.97, 'Hg': 200.59,
        'Tl': 204.38, 'Pb': 207.2, 'Bi': 208.98, 'Po': 209.0, 'At': 210.0,
        'Rn': 222.0, 'Fr': 223.0, 'Ra': 226.0, 'Ac': 227.0, 'Th': 232.04,
        'Pa': 231.04, 'U': 238.03,
    }
    
    masses = []
    for s in symbols:
        if s in ATOMIC_MASSES:
            masses.append(ATOMIC_MASSES[s])
        else:
            raise ValueError(f"Unknown element: {s} (add to ATOMIC_MASSES in phonon_utils.py)")
    return masses


# ============================================================================
# High-symmetry q-point definitions
# ============================================================================

QPATHS = {
    'fcc': {
        'Γ': [0.0, 0.0, 0.0],
        'X': [0.5, 0.5, 0.0],
        'W': [0.5, 0.25, 0.75],
        'K': [0.375, 0.375, 0.75],
        'L': [0.5, 0.5, 0.5],
        'U': [0.25, 0.25, 0.75],
    },
    'diamond_standard': [
        ('Γ', [0.0, 0.0, 0.0]),
        ('X', [0.5, 0.5, 0.0]),
        ('W', [0.5, 0.25, 0.75]),
        ('K', [0.375, 0.375, 0.75]),
        ('Γ', [0.0, 0.0, 0.0]),
        ('L', [0.5, 0.5, 0.5]),
        ('U', [0.25, 0.25, 0.75]),
        ('W', [0.5, 0.25, 0.75]),
    ],
    'fcc_mp': [
        ('Γ', [0.0, 0.0, 0.0]),
        ('X', [0.5, 0.0, 0.5]),
        ('U', [0.625, 0.25, 0.625]),
        ('K', [0.375, 0.375, 0.75]),
        ('Γ', [0.0, 0.0, 0.0]),
        ('L', [0.5, 0.5, 0.5]),
        ('W', [0.5, 0.25, 0.75]),
        ('X', [0.5, 0.0, 0.5]),
    ],
}


def get_standard_qpath(crystal_type='fcc', variant='diamond_standard'):
    """Get standard high-symmetry q-point path definitions."""
    if variant == 'diamond_standard':
        return QPATHS['diamond_standard']
    elif variant == 'fcc_mp':
        return QPATHS['fcc_mp']
    else:
        items = list(QPATHS['fcc'].items())
        return items


# ============================================================================
# Hessian-based phonon solver (MMFF / supercell finite differences)
# ============================================================================

ANG_TO_BOHR = 1.0 / 0.529177210903
BOHR_TO_ANG = 0.529177210903
# sqrt(Hartree/(amu*Bohr^2)) -> THz  (MMFF / FireCore Hessian units)
# Exact conversion: sqrt(Hartree/(amu*Bohr^2)) / (2*pi) * 1e-12
Hartree = 4.3597447222071e-18  # J
Bohr = 5.29177210903e-11  # m
amu = 1.66053906660e-27  # kg
FREQ_HA_AMU_BOHR2_TO_THZ = np.sqrt(Hartree / (amu * Bohr**2)) / (2 * np.pi) * 1e-12
# sqrt(eV/(amu*Ang^2)) -> THz  (phonopy force-constant units)
FREQ_EV_AMU_ANG2_TO_THZ = 15.633728205761277
FC_UNITS = {'hartree_bohr2': FREQ_HA_AMU_BOHR2_TO_THZ, 'ev_ang2': FREQ_EV_AMU_ANG2_TO_THZ}


def eigvals_to_freq_thz(eigvals, fc_units='ev_ang2', convention='positive'):
    """Convert dynamical-matrix eigenvalues to frequencies (THz)."""
    scale = FC_UNITS[fc_units]
    if convention == 'positive':
        return np.sqrt(np.maximum(eigvals, 0.0)) * scale
    if convention == 'signed':
        return np.sign(eigvals) * np.sqrt(np.abs(eigvals)) * scale
    raise ValueError(f"Unknown convention: {convention}")


def phi_blocks_from_phonopy_fc(phonon):
    """Convert phonopy force_constants (supercell pair layout) to Phi(0,R) blocks.
    
    phonopy stores FC[sc_i, sc_j, 3, 3] in eV/Ang^2.  Returns dict R_tuple -> (n_prim,n_prim,3,3).
    """
    fc = np.asarray(phonon.force_constants, dtype=float)
    prim = phonon.primitive
    sc = phonon.supercell
    n_prim = len(prim)
    smat = np.asarray(phonon.supercell_matrix, dtype=int)
    super_n = int(smat[0, 0])
    if not np.allclose(smat, np.diag([super_n, super_n, super_n])):
        raise ValueError(f"phi_blocks_from_phonopy_fc requires diagonal supercell matrix, got {smat}")
    sc_pos, sc_cell, sc_ia, _, _ = build_supercell(prim.positions, prim.cell, prim.symbols, super_n)
    perm = [int(np.argmin(np.linalg.norm(sc.positions - p, axis=1))) for p in sc_pos]
    if len(set(perm)) != len(perm):
        raise RuntimeError("supercell atom permutation is not unique — check structure/supercell")
    central = [i for i, c in enumerate(sc_cell) if c == (0, 0, 0)]
    Phi_blocks = {}
    for i0 in central:
        ia_i, si = sc_ia[i0], perm[i0]
        for j in range(len(sc_cell)):
            R, ia_j, sj = sc_cell[j], sc_ia[j], perm[j]
            if R not in Phi_blocks:
                Phi_blocks[R] = np.zeros((n_prim, n_prim, 3, 3))
            Phi_blocks[R][ia_i, ia_j] = fc[si, sj]
    return Phi_blocks


def solve_bands_phonopy(phonon, qpts_frac):
    """Phonopy band solver: D(k) diagonalization via get_frequencies_with_eigenvectors."""
    n_bands = 3 * len(phonon.primitive)
    freqs = np.zeros((len(qpts_frac), n_bands))
    for ik, q in enumerate(qpts_frac):
        freqs[ik] = phonon.get_frequencies_with_eigenvectors(q)[0]
    return freqs


def _method_display_name(calc):
    m = calc.backend.name
    if m == 'dftb' and getattr(calc.backend, 'slakos_dir', ''):
        return f"dftb+/{Path(calc.backend.slakos_dir).name}"
    if m == 'lammps':
        return f"lammps/{calc.backend.config.get('potential', m)}"
    return m


def build_solver_comparison_payload(result_dirs, qpath, config=None, title=None):
    """Build JSON payload comparing band solvers on cached FC data from each result dir."""
    datasets, parity = [], []
    master_dists, master_labels = qpath.distances, qpath.labels
    for result_dir in result_dirs:
        calc = PhononCalculator.from_cached_results(result_dir, config=config)
        base = _method_display_name(calc)
        if calc._hessian_mode:
            f_pos, _, _ = calc.solve_bands(qpath, band_solver='unified', freq_convention='positive')
            f_sig, _, _ = calc.solve_bands(qpath, band_solver='unified', freq_convention='signed')
            datasets.append({"name": f"{base}/unified-positive", "frequencies": f_pos.tolist(), "visible": True, "group": base})
            datasets.append({"name": f"{base}/unified-signed", "frequencies": f_sig.tolist(), "visible": False, "group": base})
            diff = np.sort(f_pos, axis=1) - np.sort(f_sig, axis=1)
            parity.append({"pair": f"{base}: unified-positive vs unified-signed", "max_abs_THz": float(np.max(np.abs(diff))),
                           "rms_THz": float(np.sqrt(np.mean(diff ** 2))), "note": "signed shows imaginary modes as negative ω"})
            print(f"[compare] {base}: unified-positive vs signed max|Δω|={parity[-1]['max_abs_THz']:.4f} THz")
        else:
            f_ph, _, _ = calc.solve_bands(qpath, band_solver='phonopy')
            f_un, _, _ = calc.solve_bands(qpath, band_solver='unified', freq_convention='positive')
            datasets.append({"name": f"{base}/phonopy", "frequencies": f_ph.tolist(), "visible": True, "group": base})
            datasets.append({"name": f"{base}/unified", "frequencies": f_un.tolist(), "visible": True, "group": base})
            fp, fu = np.sort(f_ph, axis=1), np.sort(f_un, axis=1)
            diff = fp - fu
            parity.append({"pair": f"{base}: phonopy vs unified", "max_abs_THz": float(np.max(np.abs(diff))),
                           "rms_THz": float(np.sqrt(np.mean(diff ** 2))), "note": "same FCs, two D(k) solvers"})
            print(f"[compare] {base}: phonopy vs unified max|Δω|={parity[-1]['max_abs_THz']:.6f} THz")
    tick_pos, tick_lab, seen = [], [], set()
    for d, lab in zip(master_dists, master_labels):
        if lab and lab not in seen:
            tick_pos.append(float(d))
            tick_lab.append(str(lab))
            seen.add(lab)
    return {
        "title": title or "Phonon solver / backend comparison",
        "qpts": qpath.qpts.tolist(),
        "distances": master_dists.tolist(),
        "labels": list(master_labels),
        "tick_positions": tick_pos,
        "tick_labels": tick_lab,
        "datasets": datasets,
        "parity": parity,
    }


def check_band_solver_parity(calc, qpath, tol=0.01, freq_convention='positive'):
    """Compare phonopy vs unified solvers on the same force constants."""
    calc.compute_force_constants()
    phonon = calc.get_phonopy()
    freqs_p = solve_bands_phonopy(phonon, qpath.qpts)
    phi, cell, masses, fc_units = calc.get_phi_blocks()
    freqs_u = solve_bands_from_phi(phi, cell, masses, qpath.qpts, fc_units=fc_units, convention=freq_convention)
    # Eigenvector ordering may differ — compare sorted bands per q-point
    fp = np.sort(freqs_p, axis=1)
    fu = np.sort(freqs_u, axis=1)
    diff = fp - fu
    max_abs = float(np.max(np.abs(diff)))
    rms = float(np.sqrt(np.mean(diff ** 2)))
    n_over = int(np.sum(np.abs(diff) > tol))
    report = {'max_abs_THz': max_abs, 'rms_THz': rms, 'n_over_tol': n_over, 'tol_THz': tol,
              'freqs_phonopy': freqs_p, 'freqs_unified': freqs_u}
    status = 'PASS' if max_abs <= tol else 'FAIL'
    print(f"[parity] phonopy vs unified ({freq_convention}): {status}  max|Δω|={max_abs:.6f} THz  rms={rms:.6f} THz  over_tol={n_over}/{diff.size}")
    if status == 'FAIL':
        iq, ib = np.unravel_index(np.argmax(np.abs(diff)), diff.shape)
        print(f"[parity] worst at q-index {iq} band {ib}: phonopy={fp[iq,ib]:.6f} unified={fu[iq,ib]:.6f} THz")
    return report


def build_supercell(positions, cell, symbols, super_n):
    """Build NxNxN supercell from primitive cell.  super_n must be odd."""
    super_n = int(super_n)
    if super_n % 2 != 1:
        raise ValueError(f"supercell size must be odd for central-cell extraction, got {super_n}")
    Nc = super_n // 2
    n_prim = len(positions)
    sc_pos, sc_cell, sc_ia = [], [], []
    for iz in range(super_n):
        for iy in range(super_n):
            for ix in range(super_n):
                R = ix * cell[0] + iy * cell[1] + iz * cell[2]
                for ia, p in enumerate(positions):
                    sc_pos.append(p + R)
                    sc_cell.append((ix - Nc, iy - Nc, iz - Nc))
                    sc_ia.append(ia)
    sc_lvec = super_n * cell
    return np.array(sc_pos), sc_cell, sc_ia, sc_lvec, n_prim


def extract_phi_blocks(H_sc, sc_cell, sc_ia, n_prim):
    """Extract K(0,L) force-constant blocks from supercell Hessian."""
    central_atoms = [i for i, c in enumerate(sc_cell) if c == (0, 0, 0)]
    Phi_blocks = {}
    for i0 in central_atoms:
        ia_i = sc_ia[i0]
        for j in range(len(sc_cell)):
            Rkey = sc_cell[j]
            ia_j = sc_ia[j]
            if Rkey not in Phi_blocks:
                Phi_blocks[Rkey] = np.zeros((n_prim, n_prim, 3, 3))
            Phi_blocks[Rkey][ia_i, ia_j] = H_sc[i0*3:(i0+1)*3, j*3:(j+1)*3]
    return Phi_blocks


def reciprocal_lattice(cell):
    """Reciprocal lattice vectors (rows) with 2pi convention."""
    vol = np.dot(cell[0], np.cross(cell[1], cell[2]))
    recip = np.zeros((3, 3))
    recip[0] = 2 * np.pi * np.cross(cell[1], cell[2]) / vol
    recip[1] = 2 * np.pi * np.cross(cell[2], cell[0]) / vol
    recip[2] = 2 * np.pi * np.cross(cell[0], cell[1]) / vol
    return recip


def solve_bands_from_phi(Phi_blocks, cell, masses, qpts_frac, fc_units='hartree_bohr2', convention='positive'):
    """Diagonalize dynamical matrix D(k) at fractional reciprocal q-points.

    Phi_blocks: dict (ix,iy,iz) -> (n_prim,n_prim,3,3)
      MMFF/cluster Hessian: hartree_bohr2; phonopy FC: ev_ang2
    cell:       (3,3) lattice vectors (must match Phi/R_cart units)
    masses:     (n_prim,) amu
    qpts_frac:  (N,3) fractional reciprocal coordinates
    fc_units:   'hartree_bohr2' | 'ev_ang2'
    convention: 'positive' (phonopy-style) | 'signed' (FireCore-style imaginary modes)

    Returns freqs (N, 3*n_prim) in THz.
    """
    if fc_units not in FC_UNITS:
        raise ValueError(f"Unknown fc_units: {fc_units}")
    n_prim = len(masses)
    dim = 3 * n_prim
    recip = reciprocal_lattice(cell)
    nk = len(qpts_frac)
    freqs = np.zeros((nk, dim))
    for ik, qf in enumerate(qpts_frac):
        k = qf[0] * recip[0] + qf[1] * recip[1] + qf[2] * recip[2]
        Dk = np.zeros((dim, dim), dtype=complex)
        for Rkey, Phi_R in Phi_blocks.items():
            R_cart = Rkey[0] * cell[0] + Rkey[1] * cell[1] + Rkey[2] * cell[2]
            phase = np.exp(1j * np.dot(k, R_cart))
            for i in range(n_prim):
                for j in range(n_prim):
                    block = Phi_R[i, j] * phase
                    Dk[i*3:(i+1)*3, j*3:(j+1)*3] += block / np.sqrt(masses[i] * masses[j])
        Dk = 0.5 * (Dk + Dk.conj().T)
        freqs[ik, :] = eigvals_to_freq_thz(np.linalg.eigvalsh(Dk), fc_units=fc_units, convention=convention)
    return freqs
