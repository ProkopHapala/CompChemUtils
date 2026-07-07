# tAttach

Molecule attachment and polymerization experiments — orient backbone/endgroups via marker atoms (`Se`/`F`), join `.mol2` sequences, render composites. Uses legacy `pyBall.AtomicSystem` and `plotUtils`.

- **attach.py** — original attachment workflow: backbone + H-bond acceptor/donor endgroups, hardcoded group table
- **attach_new.py** / **attach_new2.py** / **attach_new3.py** — iterative refactors toward marker-atom placement API
- **join_mols.py** — merge two `.mol2` systems with `addSystems()`, export combined XYZ/MOL2
- **polymerize.py** — repeat unit attachment along a backbone
- **render_molecules.py** — static geometry plots for attached systems
- **run_editor.py** — CLI loader for `MoleculeEditor2D` GUI; `run_editor copy.py` — duplicate

For program-agnostic placement in library code see `py/geom_engine.py` (`place_molecule_on_edge`, `generate_edge_attach_movie`).
