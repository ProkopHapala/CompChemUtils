# pyutils

Ad-hoc geometry and force-field debugging scripts — NaCl surface steps, stuck-atom trajectories, orientation tests. Legacy `pyBall` imports; not part of the orthogonal `py/` task stack.

- **orient.py** — center + PCA-orient an XYZ, write `*-oriented.xyz`
- **NaCl_step.py** / **NaCl_step_.py** / **NaCl_step_2.py** — build NaCl slab steps with ASE (iterative variants)
- **PTCDA_NaCl.py** — place PTCDA on NaCl slab (geometry experiment)
- **test_sequence_placer.py** — trial placements for molecular sequences on surfaces
- **plotStuckAtomTrj.py** — plot position/velocity/force components for stuck-atom MD debug trajectories
- **plotStuckAtomFF.py** — force component differences along reaction coordinate
