# system_specific

Domain-specific geometry builders that depend on ASE — metal surfaces, adatom slabs, and tip/cluster motifs. Kept separate from the generic geometry/task layers so ASE is optional for the rest of `py/`.

- **MetalTips.py** — FCC(111) slab + adatom builders for Cu/Ag/Au/Pt/Pd/Ni/Al (and BCC lattice constants stubbed), edge-pair frames, Ag₄ cluster directions, `AtomicSystem` export helpers
- **__init__.py** — package marker; documents ASE-dependent scope
