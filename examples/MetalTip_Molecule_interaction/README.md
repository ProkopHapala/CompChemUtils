# MetalTip × Molecule Interaction Study

Systematic study of coordination bond strength between small molecules and
FCC(111) metal surfaces (bare vs. adatom vs. multi-adatom). See
[spec](../../doc/MetalTip_Molecule_Interaction_Study_Spec.md) for full design.

## Phase 1: Metal geometry generation

Generated 41 geometries: 16 metals × {bare, adatom} + Cu/Ag/Au × {dimer, trimer, row}.
All 41 slab geometries relaxed (GPAW PBE PW(400eV) gamma-point, dipole correction, 18 frozen atoms).

### Directory structure (ChemBook protocol)
```
systems/<Metal>/
  meta.json                    # system metadata (element, a_fcc, rt_phase)
  README.md                    # system summary table
  bare_111_3x3x3.png           # preview plot (next to job dir)
  bare_111_3x3x3/
    meta.json                  # job metadata (cell, frozen indices, adatom index, ...)
    README.md                  # job summary
    input/CONTCAR              # VASP format (Jmol, VESTA)
    input/start.xyz            # extended XYZ with lattice
  adatom_111_3x3x3.png
  adatom_111_3x3x3/
    ...
  dimer_111_3x3x3.png          # Cu, Ag, Au only
  dimer_111_3x3x3/
    ...
  trimer_111_3x3x3.png
  trimer_111_3x3x3/
    ...
  row_111_3x3x3.png
  row_111_3x3x3/
    ...
```

### Summary table

| Metal | a_FCC (Å) | Variant | Atoms | Layers | Frozen | cell_z (Å) | vac_below | vac_above |
|-------|-----------|---------|-------|--------|--------|------------|-----------|-----------|
| Ti | 4.130 | bare | 27 | 3 | 18 | 19.77 | 5.00 | 10.00 |
| Ti | 4.130 | adatom | 28 | 4 | 18 | 21.77 | 5.00 | 10.00 |
| V | 3.810 | bare | 27 | 3 | 18 | 19.40 | 5.00 | 10.00 |
| V | 3.810 | adatom | 28 | 4 | 18 | 21.40 | 5.00 | 10.00 |
| Cr | 3.630 | bare | 27 | 3 | 18 | 19.19 | 5.00 | 10.00 |
| Cr | 3.630 | adatom | 28 | 4 | 18 | 21.19 | 5.00 | 10.00 |
| Mn | 3.590 | bare | 27 | 3 | 18 | 19.15 | 5.00 | 10.00 |
| Mn | 3.590 | adatom | 28 | 4 | 18 | 21.15 | 5.00 | 10.00 |
| Fe | 3.570 | bare | 27 | 3 | 18 | 19.12 | 5.00 | 10.00 |
| Fe | 3.570 | adatom | 28 | 4 | 18 | 21.12 | 5.00 | 10.00 |
| Co | 3.540 | bare | 27 | 3 | 18 | 19.09 | 5.00 | 10.00 |
| Co | 3.540 | adatom | 28 | 4 | 18 | 21.09 | 5.00 | 10.00 |
| Ni | 3.524 | bare | 27 | 3 | 18 | 19.07 | 5.00 | 10.00 |
| Ni | 3.524 | adatom | 28 | 4 | 18 | 21.07 | 5.00 | 10.00 |
| Cu | 3.615 | bare | 27 | 3 | 18 | 19.17 | 5.00 | 10.00 |
| Cu | 3.615 | adatom | 28 | 4 | 18 | 21.17 | 5.00 | 10.00 |
| Cu | 3.615 | dimer | 29 | 4 | 18 | 21.17 | 5.00 | 10.00 |
| Cu | 3.615 | trimer | 30 | 4 | 18 | 21.17 | 5.00 | 10.00 |
| Cu | 3.615 | row | 30 | 4 | 18 | 21.17 | 5.00 | 10.00 |
| Zn | 3.930 | bare | 27 | 3 | 18 | 19.54 | 5.00 | 10.00 |
| Zn | 3.930 | adatom | 28 | 4 | 18 | 21.54 | 5.00 | 10.00 |
| Mo | 3.960 | bare | 27 | 3 | 18 | 19.57 | 5.00 | 10.00 |
| Mo | 3.960 | adatom | 28 | 4 | 18 | 21.57 | 5.00 | 10.00 |
| W | 3.990 | bare | 27 | 3 | 18 | 19.61 | 5.00 | 10.00 |
| W | 3.990 | adatom | 28 | 4 | 18 | 21.61 | 5.00 | 10.00 |
| Al | 4.050 | bare | 27 | 3 | 18 | 19.68 | 5.00 | 10.00 |
| Al | 4.050 | adatom | 28 | 4 | 18 | 21.68 | 5.00 | 10.00 |
| Pd | 3.891 | bare | 27 | 3 | 18 | 19.49 | 5.00 | 10.00 |
| Pd | 3.891 | adatom | 28 | 4 | 18 | 21.49 | 5.00 | 10.00 |
| Ag | 4.086 | bare | 27 | 3 | 18 | 19.72 | 5.00 | 10.00 |
| Ag | 4.086 | adatom | 28 | 4 | 18 | 21.72 | 5.00 | 10.00 |
| Ag | 4.086 | dimer | 29 | 4 | 18 | 21.72 | 5.00 | 10.00 |
| Ag | 4.086 | trimer | 30 | 4 | 18 | 21.72 | 5.00 | 10.00 |
| Ag | 4.086 | row | 30 | 4 | 18 | 21.72 | 5.00 | 10.00 |
| Pt | 3.924 | bare | 27 | 3 | 18 | 19.53 | 5.00 | 10.00 |
| Pt | 3.924 | adatom | 28 | 4 | 18 | 21.53 | 5.00 | 10.00 |
| Au | 4.078 | bare | 27 | 3 | 18 | 19.71 | 5.00 | 10.00 |
| Au | 4.078 | adatom | 28 | 4 | 18 | 21.71 | 5.00 | 10.00 |
| Au | 4.078 | dimer | 29 | 4 | 18 | 21.71 | 5.00 | 10.00 |
| Au | 4.078 | trimer | 30 | 4 | 18 | 21.71 | 5.00 | 10.00 |
| Au | 4.078 | row | 30 | 4 | 18 | 21.71 | 5.00 | 10.00 |

### Key parameters
- Supercell: 3×3×3 FCC(111)
- Vacuum: 5 Å below slab (dipole correction), 10 Å above (molecule/scan room)
- Frozen: bottom 2 layers (18 atoms)
- Adatom: fcc hollow site, 2.0 Å above top layer
- Multi-adatom (Cu, Ag, Au only): dimer (2, NN), trimer (3, equilateral triangle), row (3, line) — all at a/√2 spacing
- Colors: Jmol (from `py/elements.py`)
- Plots: `<variant>.png` next to each job dir (not inside)

### Usage
```bash
python generate_metal_geometries.py                    # all 16 metals
python generate_metal_geometries.py --metals Cu Ag Au  # subset
```

## Phase 2: Molecule-on-surface geometry generation

Places 7 molecules (H2O, H2S, NH3, PH3, HCN, CH2O, CH2NH) on **relaxed** Cu/Ag/Au slabs (bare + adatom).
Molecule oriented so its electron lone pair faces the target metal atom at ~2.4 Å (epair-to-metal distance).
Binary hydrides (H2O, H2S, NH3, PH3) generated from bond length + H-X-H angle via `make_hydride()`.
Cell z-height fixed to 22 Å for all geometries (consistent vacuum).

### Key parameters
- Molecules: H2O, H2S, NH3, PH3, HCN, CH2O, CH2NH
- Metals: Cu, Ag, Au (coinage only — relaxed slabs from Phase 1)
- Variants: bare, adatom
- Epair-to-metal distance: 2.4 Å (host-metal dist ~2.9 Å including 0.5 Å epair offset)
- Cell z: 22 Å (fixed for all)
- Frozen: bottom 18 atoms (same as Phase 1)
- Total: 3 × 2 × 7 = 42 geometries

### Directory structure
```
systems/<Metal>/
  bare_H2O_111_3x3x3/input/CONTCAR    # molecule + slab
  bare_H2O_111_3x3x3/input/start.xyz
  adatom_H2O_111_3x3x3/input/CONTCAR
  ...
```

### Usage
```bash
python generate_molecule_on_surface.py                              # all 3 metals, 2 variants, 7 molecules
python generate_molecule_on_surface.py --metals Cu --molecules H2O  # subset
```

## Phase 2b: Relaxation jobs (molecule-on-surface)

42 GPAW relax jobs baked in `jobs_mol_on_surf/`. PBE PW(400eV) gamma-point, FermiDirac(0.05),
dipole correction, 8 CPUs, 32 GiB RAM, 23h walltime. Submitted to `luna` queue (magma.fzu.cz).

### Usage
```bash
python generate_relax_jobs.py --metals Cu Ag Au --variants bare adatom \
    --molecules H2O H2S NH3 PH3 HCN CH2O CH2NH --outdir jobs_mol_on_surf
cd jobs_mol_on_surf && bash submit_all.sh   # submit to Metacentrum
```

## Phase 2c: Aromatic molecules on all slab variants

Extended molecule set with 4 aromatic ring molecules (pyridine, furan, thiophene, pyrrol) on
**all 5 slab variants** (bare, adatom, dimer, trimer, row) for Cu, Ag, Au — 60 geometries total.
Also generated 63 additional geometries for the 7 original molecules on dimer/trimer/row variants.

### Molecules
- **pyridine** (N host, 1 epair) — nitrogen lone pair faces adatom
- **furan** (O host, 2 epairs) — oxygen lone pairs face adatom
- **thiophene** (S host, 2 epairs) — sulfur lone pairs face adatom
- **pyrrol** (N host, 1 epair) — nitrogen lone pair faces adatom

### Orientation
- Molecule placed via electron pair orientation toward target adatom (epair → metal at ~2.9 Å)
- For multi-adatom variants (dimer, trimer, row): H atoms rotated perpendicular to adatom chain
  via 90° CCW z-rotation when needed (checked by projecting H spread onto cluster axis)
- `find_adatom_cluster()` identifies cluster axis and corner atom (trimer) for placement

### Key parameters
- Metals: Cu, Ag, Au
- Variants: bare, adatom, dimer, trimer, row
- Molecules: pyridine, furan, thiophene, pyrrol
- Host-metal distance: 2.9 Å
- Cell z: 22 Å
- Total: 3 × 5 × 4 = 60 geometries (+ 63 from Phase 2d below)

### Directory structure
```
systems/<Metal>/
  bare_pyridine_111_3x3x3/input/CONTCAR
  adatom_furan_111_3x3x3/input/CONTCAR
  dimer_thiophene_111_3x3x3/input/CONTCAR
  trimer_pyrrol_111_3x3x3/input/CONTCAR
  row_pyridine_111_3x3x3/input/CONTCAR
  ...
```

### Usage
```bash
python generate_molecule_on_surface.py --metals Cu Ag Au --variants bare adatom dimer trimer row \
    --molecules pyridine furan thiophene pyrrol
python plot_pyridine_init.py    # generate inspection plots in init_plots_pyridine/
```

## Phase 2c-jobs: Relaxation jobs (aromatic molecules)

60 GPAW relax jobs baked in `jobs_mol_on_surf_3/`. Same parameters as Phase 2b.
Job IDs: 23064466–23064526 (pbs-m1.metacentrum.cz).

### Usage
```bash
python generate_relax_jobs.py --metals Cu Ag Au --variants bare adatom dimer trimer row \
    --molecules pyridine furan thiophene pyrrol --outdir jobs_mol_on_surf_3
cd jobs_mol_on_surf_3 && bash submit_all.sh
```
