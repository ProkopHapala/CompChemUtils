# AgTip CarboxAnhydride Bonds — Molecule+Metal Cluster Calculations

Scripts for studying adsorption of organic molecules (with COOH/anhydride
functional groups) on metal cluster tips (Au4 tetrahedra) and metal
surfaces (M(111)+adatom). Uses DFTB+ and xTB for geometry relaxation,
then rigid scan to compute binding energy curves.

## Files

| File | Type | Purpose |
|------|------|---------|
| `generate_metal4.py` | Reusable | Generate M4 tetrahedron cluster XYZ from FCC lattice constant. Supports any metal (Ag, Au, Cu). |
| `batch_relax_dftb.py` | Reusable | Batch relax molecule+Au4 systems with DFTB+. Freezes Au atoms, optimizes molecule. Uses `py.interfaces.dftbplus`. |
| `batch_relax_xtb.py` | Reusable | Same as above but with xTB (GFN2-xTB). Resets Au positions after relax (xTB lacks constraints). |
| `scan_adsorption.py` | Reusable | Rigid adsorption-energy scan: shift molecule along Au-apex→O bond direction. Compares xTB and DFTB+ methods. Outputs .dat + .xyz + combined PNG. |
| `scan_surface_adsorption.py` | Reusable | Same concept but for M(111)+adatom surface systems. Loads DFTB+ geo_end.gen files. Supports Ag/Au/Cu. |
| `test_dftb_export.py` | One-off | Debug script: exports DFTB+ input files without running, to diagnose SK parameter issues. |

## Workflow

1. **Generate cluster**: `python generate_metal4.py --metal Au --output data/xyz/Au4.xyz`
2. **Prepare molecule+cluster geometries** (orientations in XYZ movie format)
3. **Relax**: `python batch_relax_dftb.py --cluster-dir tmp/cluster_apex --outdir tmp/relax_dftb`
4. **Scan**: `python scan_adsorption.py --molecule CH2O_ep --outdir tmp/scan_CH2O`

## Dependencies

- `py.AtomicSystem`, `py.interfaces.dftbplus`, `py.interfaces.xtb`
- `py.tasks.scan` (make_scan_grid, rigid shift frames)
- DFTB+ binary + Slater-Koster files (for DFTB+ backend)
- xTB binary (for xTB backend)
- ASE (for structure I/O)

## Notes

- Au atoms are frozen during relaxation (cluster tip is rigid)
- Scan uses rigid shift: molecule moved as rigid body along bond direction
- Binding energy reference: energy at relaxed distance (cluster scan) or r_inf=20Å (surface scan)
- `scan_adsorption.py` has hardcoded SK path for auorg — edit `SK_PATH` for your setup
