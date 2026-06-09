#!/usr/bin/env python3
"""Match vibrational modes between methods via mass-weighted eigenvector projection."""

import csv
import numpy as np
from scipy.optimize import linear_sum_assignment

from vib_store import match_csv_path, load_method


def kabsch_rotation(P, Q):
    """Rotation R mapping Q onto P (both Nx3)."""
    C = P.T @ Q
    V, _, Wt = np.linalg.svd(C)
    d = np.sign(np.linalg.det(V @ Wt))
    D = np.diag([1.0, 1.0, d])
    return V @ D @ Wt


def align_mode_displacements(ref_pos, tgt_pos, tgt_modes):
    """Rotate target mode vectors so target geometry is Kabsch-aligned to reference."""
    ref_c = ref_pos - ref_pos.mean(axis=0)
    tgt_c = tgt_pos - tgt_pos.mean(axis=0)
    R = kabsch_rotation(ref_c, tgt_c)
    aligned = np.asarray(tgt_modes).copy()
    for i in range(len(aligned)):
        aligned[i] = aligned[i] @ R.T
    return aligned


def mass_weight_vectors(modes, masses):
    """Flatten modes to (n_modes, 3N) with sqrt(m) weighting."""
    modes = np.asarray(modes)
    n_modes, n_atoms, _ = modes.shape
    w = np.repeat(np.sqrt(masses), 3)
    flat = modes.reshape(n_modes, 3 * n_atoms)
    return flat * w[np.newaxis, :]


def normalize_rows(vecs):
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms = np.where(norms < 1e-12, 1.0, norms)
    return vecs / norms


def geometry_rmsd(ref_pos, tgt_pos):
    """RMSD (Å) between two Nx3 coordinate sets (same atom order)."""
    d = np.asarray(ref_pos) - np.asarray(tgt_pos)
    return float(np.sqrt(np.mean(d ** 2)))


def _prepare_mode_vectors(ref_modes, tgt_modes, masses, align, ref_pos, tgt_pos):
    tgt = np.asarray(tgt_modes)
    if align and ref_pos is not None and tgt_pos is not None:
        tgt = align_mode_displacements(ref_pos, tgt_pos, tgt)
    A = normalize_rows(mass_weight_vectors(ref_modes, masses))
    B = normalize_rows(mass_weight_vectors(tgt, masses))
    return A, B


def mode_similarity(a, b):
    """Signed cosine and RMSE for unit mass-weighted mode vectors a,b (sign of b flipped if needed)."""
    cos = float(np.dot(a, b))
    if cos < 0.0:
        cos = -cos
        b = -b
    rmse = float(np.sqrt(np.mean((a - b) ** 2)))
    return cos, rmse


def overlap_matrix(ref_modes, tgt_modes, masses, align=True, ref_pos=None, tgt_pos=None):
    """|<ref_i|tgt_j>| for mass-weighted unit vectors (Kabsch rotates target modes if align=True)."""
    A, B = _prepare_mode_vectors(ref_modes, tgt_modes, masses, align, ref_pos, tgt_pos)
    return np.abs(A @ B.T)


def match_modes(ref_freqs, ref_modes, tgt_freqs, tgt_modes, masses, ref_pos=None, tgt_pos=None, align=True):
    """Optimal 1:1 assignment ref->tgt maximizing |overlap| (Hungarian). Returns metrics per ref mode."""
    ref_freqs = np.asarray(ref_freqs, dtype=float)
    tgt_freqs = np.asarray(tgt_freqs, dtype=float)
    A, B = _prepare_mode_vectors(ref_modes, tgt_modes, masses, align, ref_pos, tgt_pos)
    O = np.abs(A @ B.T)
    n_ref, n_tgt = O.shape
    cost = np.zeros((max(n_ref, n_tgt), max(n_ref, n_tgt)))
    cost[:n_ref, :n_tgt] = 1.0 - O
    row_ind, col_ind = linear_sum_assignment(cost)
    matches = []
    for i, j in zip(row_ind, col_ind):
        if i >= n_ref or j >= n_tgt:
            continue
        cos, rmse = mode_similarity(A[i], B[j])
        matches.append({
            'ref_idx': int(i), 'tgt_idx': int(j),
            'ref_freq': float(ref_freqs[i]), 'tgt_freq': float(tgt_freqs[j]),
            'delta_freq': float(tgt_freqs[j] - ref_freqs[i]),
            'cosine': cos, 'rmse': rmse,
        })
    matches.sort(key=lambda m: m['ref_freq'])
    return matches


def export_match_csv(mol_name, ref_tag, tgt_tag, matches, workdir='.'):
    path = match_csv_path(mol_name, ref_tag, tgt_tag, workdir)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ['ref_idx', 'tgt_idx', 'ref_freq', 'tgt_freq', 'delta_freq', 'cosine', 'rmse']
    with open(path, 'w', newline='') as fp:
        w = csv.DictWriter(fp, fieldnames=fields)
        w.writeheader()
        w.writerows(matches)
    print(f'  [match] Saved {path}')
    return path


def print_geometry_note(mol_name, ref_tag, tgt_tag, ref_pos, tgt_pos):
    rmsd = geometry_rmsd(ref_pos, tgt_pos)
    print(f'\n=== {mol_name}: {ref_tag}  vs  {tgt_tag} ===')
    print('Each method has its OWN relaxed geometry (separate geometry optimization).')
    print(f'Coordinate RMSD between relaxed structures: {rmsd:.4f} Å')
    if rmsd < 0.05:
        print('Geometries are nearly identical; Kabsch rotation has little effect.')
    else:
        print('Geometries differ — Kabsch aligns target before comparing Cartesian eigenvectors.')


def print_match_table(matches):
    print('\nCorresponding modes (sorted by reference frequency):')
    print(f'{"pair":>4} {"ref#":>4} {"tgt#":>4} {"nu_ref":>9} {"nu_tgt":>9} {"d_nu":>8} {"cosine":>8} {"RMSE":>8}')
    print('-' * 62)
    for k, m in enumerate(matches, 1):
        print(f'{k:4d} {m["ref_idx"]:4d} {m["tgt_idx"]:4d} {m["ref_freq"]:9.1f} {m["tgt_freq"]:9.1f} {m["delta_freq"]:8.1f} {m["cosine"]:8.4f} {m["rmse"]:8.4f}')
    cosines = [m['cosine'] for m in matches]
    print(f'\nSummary: {len(matches)} pairs | mean cosine={np.mean(cosines):.4f} | min cosine={np.min(cosines):.4f}')


def run_match(mol_name, ref_tag, tgt_tags, workdir='.', align=True, threshold=10.0):
    """Match reference method against one or more targets."""
    ref = load_method(mol_name, ref_tag, workdir=workdir, threshold=threshold)
    if ref['atoms'] is None:
        raise ValueError(f'Missing relaxed geometry for reference {ref_tag}')
    masses = ref['atoms'].get_masses()
    ref_pos = ref['atoms'].get_positions()
    all_out = {}
    for tgt_tag in tgt_tags:
        tgt = load_method(mol_name, tgt_tag, workdir=workdir, threshold=threshold)
        if tgt['atoms'] is None:
            raise ValueError(f'Missing relaxed geometry for target {tgt_tag}')
        if len(ref['mode_freqs']) != len(ref['modes']):
            raise ValueError(f'Ref {ref_tag}: mode_freqs/modes length mismatch')
        if len(tgt['mode_freqs']) != len(tgt['modes']):
            raise ValueError(f'Tgt {tgt_tag}: mode_freqs/modes length mismatch')
        tgt_pos = tgt['atoms'].get_positions()
        print_geometry_note(mol_name, ref_tag, tgt_tag, ref_pos, tgt_pos)
        matches = match_modes(
            ref['mode_freqs'], ref['modes'], tgt['mode_freqs'], tgt['modes'], masses,
            ref_pos=ref_pos, tgt_pos=tgt_pos, align=align,
        )
        print_match_table(matches)
        export_match_csv(mol_name, ref_tag, tgt_tag, matches, workdir=workdir)
        all_out[tgt_tag] = matches
    return all_out
