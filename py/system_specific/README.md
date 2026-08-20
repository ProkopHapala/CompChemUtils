# system_specific

Domain-specific geometry builders that depend on ASE — metal surfaces, adatom slabs, and tip/cluster motifs. Kept separate from the generic geometry/task layers so ASE is optional for the rest of `py/`.

- **MetalTips.py** — FCC(111) slab + adatom builders for 16 study metals (separate FCC/BCC lattice constant tables), `build_fcc111_adatom` (single adatom), `build_fcc111_multi_adatom` (dimer/trimer/row configs via fractional shifts of supercell lattice vectors), `layer_indices`/`bottom_layer_indices`/`top_layer_indices` layer-indexing helpers, edge-pair frames, Ag₄ cluster directions, `AtomicSystem` export helpers (`slab_to_arrays`)
- **__init__.py** — package marker; documents ASE-dependent scope
