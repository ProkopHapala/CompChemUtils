# Topical Audit

Cross-implementation map of scientific topics in this repository. One section per topic.

---

```yaml
---
type: TopicalAudit
title: Water dimer (H-bond)
tags: [noncovalent, hbond, xtb, dftb]
---
```

## Summary

Oriented H₂O (and general O/N host) dimers via e-pair dummy atoms, backend-agnostic relax and rigid host–host distance scans. Geometry construction lives in `geom_engine.build_hbond_dimer`; scan grids in `make_scan_grid_geometric`; thin CLIs under `examples/hbond/`.

## Implementations

| Location | Status | Notes |
|----------|--------|-------|
| [`py/geom_engine.py`](../py/geom_engine.py) — `build_hbond_dimer`, `strip_epairs` | active | Acceptor lp along `+axis`; donor O–H along `−axis`; E stripped per monomer |
| [`py/tasks/scan.py`](../py/tasks/scan.py) — `make_scan_grid_geometric` | active | Fine 0.1 Å near r_eq; geometric bands; 1 Å / 5 Å steps to r_max |
| [`examples/hbond/`](../examples/hbond/README.md) | active | `relax_dimer.py`, `scan_dimer.py` — xTB, DFTB+ |
| [`examples/pySCF/`](../examples/pySCF/README.md) | active | Legacy PySCF H-bond scans (separate workflow) |
| [`examples/tPsi4resp/`](../examples/tPsi4resp/README.md) | active | Psi4 RESP + scans |

## Parity Status

| Pair | Metric | Tolerance | Test / reference |
|------|--------|-----------|------------------|
| GFN2-xTB H₂O dimer | O···O at E_bind min | ~2.8–2.9 Å | `examples/hbond/` manual run |
| GFN2-xTB H₂O dimer | E_bind min | ~−0.15 to −0.25 eV | vs [`noncovalent_interactions.md`](AGENTS/protocols/domain/noncovalent_interactions.md) (~−5 kcal/mol) |
| DFTB+ SCC (no D3) | E_bind min | order-of-magnitude only | Dispersion missing without s-dftd3 build |

## Open Issues

- DFTB+ default `D3` dispersion requires binary compiled with `WITH_SDFTD3=ON`; current fork build may need `--method-dftb none`.
- Homodimer O index detection in library snippets assumes first half / second half layout; `scan_dimer._dimer_indices` is the robust path for general dimers.
- Parallel PySCF/Psi4 scan examples predate `build_hbond_dimer` — not unified yet.
