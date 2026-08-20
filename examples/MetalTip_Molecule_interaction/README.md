# MetalTip × Molecule Interaction Study

Systematic study of coordination bond strength between small molecules and
FCC(111) metal surfaces (bare vs. adatom vs. multi-adatom). See
[spec](../../doc/MetalTip_Molecule_Interaction_Study_Spec.md) for full design.

## Phase 1: Metal geometry generation

Generated 41 geometries: 16 metals × {bare, adatom} + Cu/Ag/Au × {dimer, trimer, row}.

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
