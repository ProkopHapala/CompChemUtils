Here are the results and the geometry question answered directly.

## Geometry: why not one structure?

**Right now each method has its own relaxed geometry.** The pipeline is:

1. Optimize with method A → Hessian at A’s minimum → modes at A’s geometry  
2. Optimize with method B → Hessian at B’s minimum → modes at B’s geometry  

So eigenvectors are **not** computed at the same coordinates. They are close but not identical:

| Molecule | PySCF vs DFTB | RMSD (Å) |
|----------|---------------|----------|
| CH4 | mio-1-1 | 0.0055 |
| C2H6 | mio-1-1 | 0.0094 |
| C2H6 | 3ob-3-1 | 0.0093 |
| SiH4 | matsci-0-3 | 0.0020 |
| Si2H6 | matsci-0-3 | 0.0228 |

**Kabsch** only removes a rigid rotation between those two nearly-equal structures before comparing Cartesian displacement vectors. With RMSD ≈ 0.01 Å it barely changes anything; it’s a safeguard, not the main issue.

**What you’re suggesting (same geometry for all)** is the cleaner setup:

- Relax once (e.g. PySCF)  
- Compute **all** Hessians at that fixed geometry (DFTB single-point + finite differences)  

That would remove geometry ambiguity entirely. We don’t do that yet — each method relaxes independently.

## How matching works

For each PySCF mode we find the DFTB mode with largest **mass-weighted cosine similarity** (Hungarian assignment for 1:1 pairing).

- **cosine** ∈ [0, 1]: 1 = same pattern of atomic motion (sign flipped if needed)  
- **RMSE**: root-mean-square difference of the mass-weighted, normalized displacement vectors (0 = identical)

## C2H6 — PySCF vs DFTB mio-1-1 (didactic example)

Geometry RMSD: **0.0094 Å** — structures are essentially the same.

| Pair | ν PySCF | ν DFTB | Δν | cosine | RMSE | Comment |
|------|---------|--------|-----|--------|------|---------|
| 1 | 336 | 273 | −64 | 1.000 | 0.000 | C–C torsion / skeleton |
| 2–3 | 828 | 868 | +41 | 0.999 | 0.011 | CH₂ rock |
| 4 | 1017 | 1123 | +106 | 0.967 | 0.052 | C–C stretch (DFTB overestimates) |
| 5–6 | 1209 | 1244 | +34 | 1.000 | 0.006 | CH₂ scissor |
| 7 | 1387 | 1389 | +2 | 1.000 | 0.004 | CH₃ degenerate bend |
| 8 | 1411 | 1459 | +48 | 0.967 | 0.052 | CH₃ bend |
| 9–10 | 1474 | 1448 | −27 | 1.000 | 0.006 | CH₃ bend |
| 11–12 | 1477 | 1465 | −13 | 1.000 | 0.003 | CH₃ bend |
| 13–14 | 3018–3020 | 2928–2940 | −78 to −92 | 1.000 | 0.002–0.004 | C–H stretch |
| 15–18 | 3076–3101 | 3062–3076 | −14 to −26 | 0.999 | 0.003–0.008 | C–H stretch |

**Summary:** 18 pairs, mean cosine **0.996**, min **0.967**  
→ Eigenvectors match very well; frequency shifts are the main DFTB error.

### C2H6 — PySCF vs DFTB 3ob-3-1

Mean cosine **0.999**, min **0.996** — even better vector agreement; frequencies also closer than mio on several modes.

## All molecules (PySCF reference vs primary DFTB set)

| Molecule | DFTB set | Geom RMSD (Å) | mean cosine | min cosine | Worst mode |
|----------|----------|---------------|-------------|------------|------------|
| CH4 | mio | 0.0055 | 0.89 | 0.65 | T₂ bend ~1310 cm⁻¹ (degenerate trio splits) |
| CH4 | 3ob | 0.0092 | 0.88 | 0.65 | same — symmetry degeneracy |
| C2H6 | mio | 0.0094 | 0.996 | 0.967 | ν₄ 1017↔1123 cm⁻¹ |
| C2H6 | 3ob | 0.0093 | 0.999 | 0.996 | excellent overall |
| SiH4 | matsci | 0.0020 | 0.85 | 0.73 | H–Si–H bends ~908↔775 cm⁻¹ (−15%) |
| SiH4 | pbc | — | 0.85 | 0.70 | similar Si–H bend issue |
| Si2H6 | matsci | 0.0228 | 0.986 | 0.89 | **pair 4: 455↔1270 cm⁻¹** (mis-assigned bend) |
| Si2H6 | pbc | — | 0.99 | 0.99 | much better |

**Pattern:** C–H modes: vectors match (cosine ≈ 1), frequencies within a few %. Si–H bends: vectors still ~0.7–0.85 cosine but frequencies off by 15–20%. Si₂H₆ low-frequency modes: one bad pairing (high cosine 0.89 but Δν = 815 cm⁻¹) — likely DFTB reordering of low modes, worth checking in `all_modes.xyz`.

## CSV outputs

Full tables saved under:

```
results/<mol>/match/pyscf_b3lyp_cc-pVDZ_vs_<dftb-tag>.csv
```

Columns: `ref_idx`, `tgt_idx`, `ref_freq`, `tgt_freq`, `delta_freq`, `cosine`, `rmse`

Re-run anytime:

```bash
python vib_spectra.py match C2H6 --workdir results
python vib_spectra.py match C2H6 --workdir results --no-align   # skip Kabsch (negligible here)
```

**Bottom line:** You’re correct that ideally everyone should share one geometry. Currently each method has its own relaxed structure (they differ by ~0.01 Å). Kabsch is only there to align those tiny frame differences when comparing eigenvectors. The scientifically stricter next step would be: **fix geometry to PySCF relaxed.xyz, recompute DFTB Hessians there** — I can add that as a `run` option if you want.