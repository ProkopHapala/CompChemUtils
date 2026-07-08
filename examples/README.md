# examples

Runnable workflows and study scripts — thin CLIs on top of `py/` (geometry, tasks, interfaces). Not imported by the library; paths and datasets are often local. See [`/ARCHITECTURE.md`](/ARCHITECTURE.md) for layer rules.

- **add_epairs.py** — add electron-pair (`E`) dummy atoms to N/O in XYZ via `AtomicSystem.add_electron_pairs()`
- **replicate_xyz.py** — tile structure in XY with `AtomicSystem.clonePBC()`
- **plot_movies.py** — XY/XZ previews of XYZ movies via `plotUtils.plotGeometry`

| Topic | Path | README |
|-------|------|--------|
| H-bond dimer build + relax (xTB, DFTB+) | `hbond/` | [`hbond/README.md`](hbond/README.md) |
| Metal tip + anhydride adsorption | `AgTip_CarboxAnhydride_bonds/` | [`AgTip_CarboxAnhydride_bonds/README.md`](AgTip_CarboxAnhydride_bonds/README.md) |
| DFTB+ scans, orbitals, waveplot | `dftb/` | [`dftb/README.md`](dftb/README.md) |
| Fukui functions (GPAW, PySCF, metals) | `fukui/` | [`fukui/README.md`](fukui/README.md) |
| Metacentrum PBS monitoring | `metacentrum/` | [`metacentrum/README.md`](metacentrum/README.md) |
| Bulk phonons (DFTB, LAMMPS, MMFF) | `phonons/` | [`phonons/README.md`](phonons/README.md) |
| PySCF relax / H-bond scans | `pySCF/` | [`pySCF/README.md`](pySCF/README.md) |
| Geometry / FF debugging snippets | `pyutils/` | [`pyutils/README.md`](pyutils/README.md) |
| Molecule attachment / polymerization | `tAttach/` | [`tAttach/README.md`](tAttach/README.md) |
| Psi4 RESP + scans | `tPsi4resp/` | [`tPsi4resp/README.md`](tPsi4resp/README.md) |
| Molecular vibrations (PySCF, DFTB+, MMFF) | `tSiNCs/` | [`tSiNCs/README.md`](tSiNCs/README.md) |

Many scripts predate the `py/` refactor and still import legacy `pyBall` — prefer `py.*` for new work.
