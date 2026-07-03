# Molecule-on-Surface Orientation Engine & QM Input Generation

## Overview

This system provides a modular pipeline for orienting small molecules (H2O, NH3, CH2NH, CH2O, HCN) on silver substrates and exporting ready-to-run quantum chemistry inputs. It separates geometry/orientation, surface construction, and QM job export into independent modules.

## Architecture

| Concern | Module | Key APIs |
|---|---|---|
| Geometry / orientation | `py/geom_engine.py` | `_resolve_point()`, `_resolve_vector()`, `_transform_positions()`, `_mol_frame_from_epairs()`, `ag4_directions()`, `generate_ag4_attach_movie()`, `run_from_json()`, **`place_molecule_on_edge()`**, **`auto_edge_placement()`**, **`generate_edge_attach_movie()`** |
| Surface construction (ASE) | `py/surface_ase.py` | `build_ag111_adatom()`, `pick_fcc_hollow_base3()`, `slab_to_arrays()`, **`build_ag111_adatom_pair()`** |
| Clash detection | `py/atomicUtils.py` | `findShortContactsNP()` |
| Psi4 input export | `py/export_psi4_jobs.py` | `export_movie_to_psi4()` |
| GPAW / PBC export | `py/export_gpaw_jobs.py` | `build_surface_frame()`, `ag111_directions_from_base3()`, `export_surface_movie_from_molecule_frames()`, `write_gpaw_runner()`, **`export_surface_edgepair_movie_from_molecule()`** |
| CLI examples (old) | `examples/AgTip_CarboxAnhydride_bonds/geom_ag4_attach_movies.py`, `examples/AgTip_CarboxAnhydride_bonds/geom_ag111_export_movies.py`, `examples/AgTip_CarboxAnhydride_bonds/geom_psi4_export_inputs.py` | batch generation and export |
| CLI examples (edge) | **`examples/AgTip_CarboxAnhydride_bonds/geom_ag7_edge_attach_movies.py`**, **`examples/AgTip_CarboxAnhydride_bonds/geom_ag111_edgepair_export_movies.py`** | edge-based batch generation |
| Input export (edge) | **`examples/AgTip_CarboxAnhydride_bonds/geom_ag7_edge_psi4_inputs.py`**, **`examples/AgTip_CarboxAnhydride_bonds/geom_ag111_edgepair_gpaw_inputs.py`** | Psi4/GPAW runner generation from edge movies |

---

## 1. Geometry Engine (`py/geom_engine.py`)

### Purpose
Handles flexible point/vector resolution, rigid-body transforms, electron-pair-based molecule orientation, and scan-direction generation.

### Core concepts

#### PointSpec & VectorSpec
The engine does **not** hard-code atom indices. It uses `_resolve_point()` and `_resolve_vector()` to interpret flexible specifications:

- **PointSpec** (`_resolve_point(apos, spec, _0=0)`):
  - `int` -> single atom index
  - `list/tuple of ints` -> average of those atom positions
  - `dict` -> `"type":"atom"`, `"average"`, `"cog"`, or `"vector"` (explicit 3-vector)

- **VectorSpec** (`_resolve_vector(apos, spec, _0=0)`):
  - `[x, y, z]` -> explicit normalized vector
  - `dict` -> `"type":"vector"`, `"bond"` (bond vector from src to dst PointSpec), or `"pca"` (PCA axis: `"longest"`, `"middle"`, `"shortest"`)

#### Molecule orientation from electron pairs
`_mol_frame_from_epairs(mol, i_host)`:
1. Builds bonding via `mol.neighs(bBond=True)`
2. Adds dummy `"E"` atoms for electron pairs via `mol.add_electron_pairs()`
3. Defines **forward** = `host -> E` (so the E-pair points opposite to `fw`, i.e. toward the substrate)
4. Defines **up** = perpendicular to `fw`, using a second E-pair or a real neighbor
5. Returns `(origin, fw, up, mask_keep)` where `mask_keep` flags real atoms (E excluded)

If no E-pairs exist, it falls back to the **lone-pair direction opposite the nearest heavy-atom neighbor**.

#### Rigid-body transform
`_transform_positions(apos, origin, M_rows, T_rows, target_origin)` applies:

```
p' = T^T * (M * (p - origin)) + target_origin
```

Where `M_rows` is the molecule's local frame and `T_rows` is the target frame (both orthonormal row-basis matrices from `atomicUtils.makeRotMat()`).

#### Direction sets
- `ag4_directions(ag, i_apex=0, base=(1,2,3), tilt_degs=(20,45))` generates 5 directions for an Ag4 tetrahedron:
  1. `up` (straight +z)
  2. `tilt20_corner`, `tilt20_face`
  3. `tilt45_corner`, `tilt45_face`
- `ag111_directions_from_base3(slab, i_adatom, base3, ...)` generates an equivalent set from a real ASE Ag(111) surface.

#### Movie generation
`generate_ag4_attach_movie(mol_xyz, out_xyz, ...)`:
- Loads molecule + Ag4 cluster
- Computes local frame via `_mol_frame_from_epairs()`
- For each direction × roll angle, transforms molecule and writes one XYZ frame
- Roll is applied around the scan direction via `_roll_up()`
- E-pair dummy atoms are removed by default (`remove_epairs=True`)
- Comments encode `dof`, `idir`, `iroll`, `theta`, `roll`, host index, distance

#### JSON config driver
`run_from_json(config_path)` reads a JSON file and calls `generate_ag4_attach_movie()` with all parameters. Example JSON:

```json
{
  "molecule": {"file": "data/xyz/H2O.xyz"},
  "substrate": {"file": "data/xyz/Ag4.xyz"},
  "placement": {"dist": 2.0},
  "scan": {"tilt_degs": [20, 45], "roll_degs": [0, 90]},
  "output": {"xyz_movie": "tmp/H2O_Ag4_orients.xyz", "plot_dirs_png": "tmp/dirs.png"}
}
```

### Edge-based molecule placement

For larger molecules (maleic anhydride, NDCA, dihydroxy pyridin) on Ag substrates with **two adatoms forming an edge**, the engine provides a specialized placement system that aligns the molecule's **peripheral axis** to the Ag–Ag bond and positions the molecule "standing" in the XZ plane with oxygens pointing down.

#### `place_molecule_on_edge(mol_es, mol_ps, edge_p0, edge_p1, i_anchor, i_axis0, i_axis1, ...)`
Rigid-body transform that:
1. Aligns the molecule's **peripheral axis** (`i_axis0 → i_axis1`) to the Ag–Ag adatom bond (`edge_p0 → edge_p1`)
2. Positions the **anchor atom** (`i_anchor`) at the edge midpoint, lifted by `lift` Å above the edge
3. Tilts the molecule around the edge axis by `tilt_deg`
4. Orient the molecule "standing" via `target_up_mode='standing'` (plane normal perpendicular to edge and vertical)

Key parameters:
- `origin_mode='axis_mid'` | `'anchor'` — translate by edge midpoint or by anchor position
- `target_up_mode='standing'` | `'flat'` — standing (XZ plane) vs flat (XY plane)
- `target_up_sign=+1.0` | `-1.0` — flip the molecule upside-down (used for oxygen-down correction)

#### `auto_edge_placement(...)`
Automatically resolves orientation ambiguities and lift to produce a **clash-free, oxygen-down** geometry:
1. Evaluates 4 discrete variants:
   - `swap_edge ∈ {False, True}` (reverse Ag–Ag direction)
   - `target_up_sign ∈ {+1.0, -1.0}` (flip molecule vertically)
2. For each variant, **increases lift** from `lift0` to `lift_max` in `lift_step` increments
3. Validates **all requested tilts** using `findShortContactsNP()`
4. Selects the first clash-free candidate with preference for **oxygen-down** (`mean(z_O) < mean(z_nonO)`)
5. Returns a dict with `swap_edge`, `target_up_sign`, `lift`, `oxygen_dz`, `nshort`

#### `generate_edge_attach_movie(mol_xyz, out_xyz, cluster_xyz, tilts_deg=(0.0, 15.0, 30.0), lift=2.0, auto_fix=True, ...)`
High-level wrapper:
- Loads Ag7 cluster + molecule
- Infers anchor atom and peripheral axis automatically from bonding
- Calls `auto_edge_placement()` to find the best orientation
- Generates a multi-frame XYZ movie with one frame per tilt angle
- Prints clash warnings if any remain after auto-fixing

---

## 2. Surface ASE Builder (`py/surface_ase.py`)

### Purpose
Builds periodic Ag(111) surfaces with an adatom using ASE, and identifies the 3 top-layer atoms that form the hollow site under the adatom.

### Key functions

#### `build_ag111_adatom(size=(2,2,2), a=4.086, vacuum=10.0, height=2.0, position='fcc', periodic=True)`
- Uses `ase.build.fcc111('Ag', size=size, a=a, vacuum=vacuum, periodic=periodic)`
- Adds adatom via `ase.build.add_adsorbate(slab, 'Ag', height=height, position=position)`
- Centers slab in z with `slab.center(vacuum=vacuum, axis=2)`
- Returns `(slab, i_adatom)` where `i_adatom` is the **highest-z atom** (the adatom)

#### `pick_fcc_hollow_base3(slab, i_adatom, z_tol=0.35)`
- Finds the top surface layer by looking for atoms well below the adatom
- Selects the **3 closest top-layer atoms in xy distance** to the adatom
- These 3 atoms are the natural "base" of the tetrahedral-like hollow site
- Returns a stable ordering: `(i_corner, i1, i2)` where `i_corner` is the atom with the largest x-coordinate among the 3 (arbitrary but stable reference)

#### `slab_to_arrays(slab)`
- Extracts ASE `Atoms` into plain NumPy/Lists:
  - `es` = element symbols
  - `ps` = positions `(N,3)`
  - `lvec` = cell vectors `(3,3)`
  - `pbc` = periodic boundary flags

---

## 2b. Clash Detection (`py/atomicUtils.py`)

### `findShortContactsNP(ps, es, factor=0.7)`
Detects atomic clashes by comparing inter-atomic distances against the sum of covalent radii scaled by `factor`:

```python
from py.atomicUtils import findShortContactsNP
shorts = findShortContactsNP(ps, es, factor=0.7)
# shorts -> list of (i, j, r, rmin) tuples
#   i, j   : atom indices
#   r      : actual distance
#   rmin   : threshold distance (sum of covalent radii * factor)
```

- **Handles element symbols** by mapping to atomic numbers for radius lookup
- **Ignores intramolecular** contacts by default (only cross-substrate checks in the edge placement loop)
- Used as the objective signal in `auto_edge_placement()` to drive lift/orientation optimization

---

## 3. Psi4 Input Exporter (`py/export_psi4_jobs.py`)

### Purpose
Converts an XYZ movie into per-frame Psi4 input files, with Ag atoms frozen and mixed basis/ECP treatment.

### Key function

#### `export_movie_to_psi4(xyz_movie, outdir, method='b3lyp', basis_main='cc-pvdz', basis_ag='def2-SVP', ecp_ag='def2-SVP', freeze_ag=True, opt=False, ...)`

What it does:
1. Loads the movie via `atomicUtils.load_xyz_movie()`
2. For each frame, writes a `.psi4.in` file containing:
   - `memory 2GB`
   - `molecule { ... }` block with all atoms
   - `set { scf_type df; opt_coordinates cartesian; geom_maxiter 200 }`
   - `basis { assign cc-pvdz; assign Ag def2-SVP }`
   - `ecp { assign Ag def2-SVP }`
   - `set optking { frozen_cartesian = ("1 2 3 4 ...") }` for all Ag atoms (1-based)
   - `energy('b3lyp')` or `optimize('b3lyp')` depending on `opt`

### Why this ECP/basis choice?
- **Ag**: `def2-SVP` basis + `def2-SVP` ECP. Silver is a heavy transition metal; a frozen-core ECP is essential for tractability in cluster calculations. The def2 family is a robust, widely used choice for 4d metals.
- **Main group (O, N, C, H)**: `cc-pvdz` is a standard polarized double-zeta basis.
- **Mixing Dunning and def2**: Not perfectly consistent, but pragmatic for metal-organic clusters when cost matters and you primarily care about relative trends across orientations.

### CLI wrapper
`examples/AgTip_CarboxAnhydride_bonds/geom_psi4_export_inputs.py`

Example usage:
```bash
python3 examples/AgTip_CarboxAnhydride_bonds/geom_psi4_export_inputs.py tmp/ag4_movies/H2O_Ag4_attach_orients.xyz \
  --outdir tmp/psi4_inputs_H2O_b3lyp --method b3lyp --basis cc-pvdz
```

This produces 10 `.psi4.in` files (5 directions × 2 rolls), ready to run with:
```bash
psi4 frame_0000_....psi4.in
```

---

## 4. GPAW / PBC Exporter (`py/export_gpaw_jobs.py`)

### Purpose
Generates periodic Ag(111) + adatom + molecule orientations, writes XYZ movies, and exports per-frame structures in formats readable by VESTA and ASE-GUI.

### Key functions

#### `build_surface_frame(size=(2,2,2), a=4.086, vacuum=10.0, height=2.0, position='fcc')`
Wraps `surface_ase.build_ag111_adatom()` + `pick_fcc_hollow_base3()`.

#### `ag111_directions_from_base3(slab, i_adatom, base3, tilt_degs=(20.0, 45.0))`
Uses the **real surface geometry** to define scan directions:
- `corner` azimuth = projection of `adatom -> base3[0]` onto the xy plane
- `face` azimuth = projection of `adatom -> midpoint(base3[1], base3[2])`
- Equivalent 5 directions to the Ag4 tetrahedron set

#### `export_surface_movie_from_molecule_frames(mol_xyz, out_xyz, surface_size=(2,2,2), ...)`
1. Builds ASE surface + adatom
2. Computes molecule frame via `geom_engine._mol_frame_from_epairs()`
3. For each direction × roll, applies rigid-body transform so the molecule's host atom is at `adatom + fwd * dist`
4. Writes concatenated XYZ movie with full DOF comments
5. Optionally exports per-frame structures:
   - `.xyz` (ASE extxyz, readable by ase-gui)
   - `.cif` (Crystallographic Information File, readable by VESTA)
   - `.POSCAR` (VASP format, readable by VESTA)

#### `write_gpaw_runner(fname, structure_file, ...)`
Writes a minimal Python script that:
- Loads the structure with ASE
- Sets `FixAtoms(indices=[...])` for surface atoms
- Attaches a GPAW calculator (`mode=PW(400), xc='PBE', kpts={'size': (4,4,1)}`)
- Runs a single-point energy and writes `final.traj`

#### `export_surface_edgepair_movie_from_molecule(mol_xyz, out_xyz, surface_size=(2,2,2), shift_frac=(0.5, 0.0), lift=2.0, tilts_deg=(0.0, 15.0, 30.0), auto_fix=True, ...)`
Generates PBC Ag(111) slab with **two adatoms forming an edge**, places the molecule standing on that edge:
1. Builds slab via `build_ag111_adatom_pair(...)` — second adatom shifted by `shift_frac` in surface lattice units
2. Infers molecule anchor/peripheral-axis from bonding
3. Calls `auto_edge_placement()` to fix orientation and lift
4. Exports:
   - Concatenated XYZ movie
   - Per-frame structures (`extxyz`, `cif`, `vasp`) if `export_formats` requested
   - Clash warnings for any remaining short contacts

Key parameters:
- `shift_frac=(0.5, 0.0)` — offset of second adatom relative to first (fcc hollow → neighboring hollow)
- `auto_fix=True` — automatically find clash-free orientation and lift
- `lift_step=0.25`, `lift_max=8.0` — search bounds for lift adjustment

### CLI wrappers
- `examples/AgTip_CarboxAnhydride_bonds/geom_ag111_export_movies.py` (single adatom / old scan directions)

Example usage:
```bash
python3 examples/AgTip_CarboxAnhydride_bonds/geom_ag111_export_movies.py \
  --outdir tmp/ag111_movies \
  --export-structs --plot-dirs \
  --size 2 2 2 --adatom-height 2.0 --dist 2.0
```

This generates:
- `tmp/ag111_movies/*_Ag111_attach_orients.xyz` (movies for all molecules)
- `tmp/ag111_movies/H2O_frames/up_roll0.cif` (per-frame CIF for VESTA)
- `tmp/ag111_movies/H2O_frames/up_roll0.POSCAR` (per-frame POSCAR for VESTA)
- `tmp/ag111_movies/ag111_scan_directions.png` (matplotlib 3D direction plot)

---

## 5. Step-by-Step User Tutorial

### Step 1: Generate finite-cluster orientation movies (Ag4)

Run the cluster movie generator for all molecules:
```bash
python3 examples/AgTip_CarboxAnhydride_bonds/geom_ag4_attach_movies.py \
  --outdir tmp/ag4_movies \
  --plot-dirs --dist 2.0
```

You will get files like:
- `tmp/ag4_movies/H2O_Ag4_attach_orients.xyz`
- `tmp/ag4_movies/scan_directions.png`

### Step 2: Export Psi4 inputs from cluster movies

For **B3LYP** (reference):
```bash
python3 examples/AgTip_CarboxAnhydride_bonds/geom_psi4_export_inputs.py \
  tmp/ag4_movies/H2O_Ag4_attach_orients.xyz \
  --outdir tmp/psi4_inputs_H2O_b3lyp \
  --method b3lyp --basis cc-pvdz --basis-ag def2-SVP --ecp-ag def2-SVP
```

For **PBE** (to compare with GPAW):
```bash
python3 examples/AgTip_CarboxAnhydride_bonds/geom_psi4_export_inputs.py \
  tmp/ag4_movies/H2O_Ag4_attach_orients.xyz \
  --outdir tmp/psi4_inputs_H2O_pbe \
  --method pbe --basis cc-pvdz --basis-ag def2-SVP --ecp-ag def2-SVP
```

Run a frame:
```bash
conda activate p4env
psi4 tmp/psi4_inputs_H2O_b3lyp/frame_0000_....psi4.in
```

### Step 3: Generate periodic surface orientation movies (Ag111)

```bash
python3 examples/AgTip_CarboxAnhydride_bonds/geom_ag111_export_movies.py \
  --outdir tmp/ag111_movies \
  --export-structs --plot-dirs \
  --size 2 2 2 --adatom-height 2.0 --dist 2.0
```

### Step 4: View structures in VESTA or ASE-GUI

Open a per-frame CIF:
```bash
ase-gui tmp/ag111_movies/H2O_frames/up_roll0.cif
# or
vesta tmp/ag111_movies/H2O_frames/up_roll0.cif
```

Or open the extxyz movie directly:
```bash
ase-gui tmp/ag111_movies/H2O_Ag111_attach_orients.xyz
```

### Step 5: Generate GPAW runner scripts

From Python (or a small script):
```python
from py.interfaces.gpaw import write_gpaw_runner

# Freeze all surface atoms (indices 0 to 8 for 2x2x2 slab + adatom)
write_gpaw_runner(
    fname='tmp/run_gpaw_up_roll0.py',
    structure_file='tmp/ag111_movies/H2O_frames/up_roll0.xyz',
    fix_indices=range(9),
    txt='gpaw_up_roll0.txt',
)
```

Run it:
```bash
python3 tmp/run_gpaw_up_roll0.py
```

### Step 6: Edge-based orientation on Ag7 clusters

For molecules with a central bridge atom and two peripheral oxygens (maleic anhydride, NDCA, dihydroxy pyridin), use the edge-attachment system:

```bash
python3 examples/AgTip_CarboxAnhydride_bonds/geom_ag7_edge_attach_movies.py \
  --outdir tmp/ag7_edge_movies \
  --tilts 0 15 30 --lift 2.0
```

This automatically:
- Detects the anchor atom (bridge O or N) and peripheral O–O axis from bonding
- Places the molecule standing in the XZ plane on the Ag7 edge
- Flips orientation and increases lift until **no clashes** remain
- Generates `tmp/ag7_edge_movies/*_edge_tilts.xyz`

### Step 7: Edge-based orientation on Ag(111) PBC surface

```bash
python3 examples/AgTip_CarboxAnhydride_bonds/geom_ag111_edgepair_export_movies.py \
  --outdir tmp/ag111_edgepair_movies \
  --tilts 0 15 30 --lift 2.0 --export-structs \
  --mols data/xyz/maleic_anhydride.xyz data/xyz/NDCA.xyz data/xyz/dihydroxy_pyridin.xyz
```

Output:
- `tmp/ag111_edgepair_movies/maleic_anhydride_Ag111_edgepair_tilts.xyz`
- `tmp/ag111_edgepair_movies/maleic_anhydride_frames/tilt000.cif` (per-frame for VESTA)
- `tmp/ag111_edgepair_movies/maleic_anhydride_frames/tilt000.POSCAR`

### Step 8: Export Psi4 inputs from edge cluster movies

```bash
python3 examples/AgTip_CarboxAnhydride_bonds/geom_ag7_edge_psi4_inputs.py tmp/ag7_edge_movies \
  --outdir tmp/psi4_edge_inputs \
  --method b3lyp --basis-main cc-pvdz --basis-ag def2-SVP --ecp-ag def2-SVP \
  --freeze-ag --opt
```

This scans `tmp/ag7_edge_movies/*_edge_tilts.xyz` and writes one `.psi4.in` per frame per movie, with all Ag atoms frozen.

### Step 9: Export GPAW runners from edge PBC structures

```bash
# For each molecule's per-frame directory
for mol in maleic_anhydride NDCA dihydroxy_pyridin; do
  python3 examples/AgTip_CarboxAnhydride_bonds/geom_ag111_edgepair_gpaw_inputs.py \
    tmp/ag111_edgepair_movies/${mol}_frames \
    --outdir tmp/gpaw_edge_runners/${mol} \
    --xc PBE --pw 400 --kpts 4 4 1 \
    --fix-indices 0 1 2 3 4 5 6 7 8 9
done
```

Each runner loads the per-tilt `.xyz`, freezes the first 10 atoms (slab + adatoms), and attaches a GPAW PW calculator.

### Step 10: Compare methods

| Code | Method | Basis / Setup | Geometry | Atom freezing |
|------|--------|---------------|----------|---------------|
| Psi4 | B3LYP | cc-pvdz + def2-SVP(ECP) on Ag | Ag4 cluster | `frozen_cartesian` on all Ag |
| Psi4 | PBE | cc-pvdz + def2-SVP(ECP) on Ag | Ag4 cluster | `frozen_cartesian` on all Ag |
| Psi4 | B3LYP | cc-pvdz + def2-SVP(ECP) on Ag | **Ag7 edge** | `frozen_cartesian` on all Ag |
| GPAW | PBE | PAW (default), PW=400 eV | Ag111 PBC (single adatom) | `ase.constraints.FixAtoms` on surface atoms |
| GPAW | PBE | PAW (default), PW=400 eV | **Ag111 edgepair** | `ase.constraints.FixAtoms` on slab + adatoms |

---

## 6. File Summary

| File | Role |
|------|------|
| `py/geom_engine.py` | Core geometry engine: flexible specs, epair orientation, rigid-body transform, direction generation, **edge-based placement**, **auto-fix orientation/lift**, movie writer |
| `py/surface_ase.py` | ASE wrapper for Ag(111) slab + adatom construction, base-atom identification, **two-adatom edge pairs** |
| `py/atomicUtils.py` | Short-contact clash detection (`findShortContactsNP`), covalent radii, XYZ I/O |
| `py/export_psi4_jobs.py` | Converts XYZ movies to per-frame Psi4 inputs with ECPs and frozen atoms |
| `py/export_gpaw_jobs.py` | Generates PBC surface + molecule movies and per-frame CIF/POSCAR/extxyz exports; **edgepair PBC exporter** |
| `examples/AgTip_CarboxAnhydride_bonds/geom_ag4_attach_movies.py` | CLI: batch generate Ag4 + molecule orientation movies |
| `examples/AgTip_CarboxAnhydride_bonds/geom_ag111_export_movies.py` | CLI: batch generate Ag111 + molecule PBC movies + structure exports (single adatom) |
| `examples/AgTip_CarboxAnhydride_bonds/geom_psi4_export_inputs.py` | CLI: convert any XYZ movie to per-frame Psi4 inputs |
| `examples/AgTip_CarboxAnhydride_bonds/geom_ag7_edge_attach_movies.py` | **CLI**: batch generate Ag7 edge + molecule tilt movies with auto-fix |
| `examples/AgTip_CarboxAnhydride_bonds/geom_ag111_edgepair_export_movies.py` | **CLI**: batch generate Ag111 edgepair + molecule tilt movies + per-frame exports |
| `examples/AgTip_CarboxAnhydride_bonds/geom_ag7_edge_psi4_inputs.py` | **CLI**: batch export Psi4 inputs from all Ag7 edge movies |
| `examples/AgTip_CarboxAnhydride_bonds/geom_ag111_edgepair_gpaw_inputs.py` | **CLI**: batch export GPAW runner scripts from all edgepair per-frame structures |
