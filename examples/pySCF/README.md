# pySCF

Small-molecule PySCF demos using the `py.interfaces.pyscf` backend and `plotUtils` — precursors to the modular `py/tasks` layer.

- **relax_small_mols.py** — relax H₂O, NH₃, HCOOH, CH₂O via `pyscf` interface + overlay energy plots
- **map_hbonds.py** — linear/angular H-bond potential scans on dimer geometries (legacy `FFFit` + PySCF energies)
- **try_pyscf.py** — minimal PySCF geometry optimization (Berny solver) sanity check

For production Fukui/cluster workflows see [`../fukui/pyscf_fukui_cluster/README.md`](../fukui/pyscf_fukui_cluster/README.md).
