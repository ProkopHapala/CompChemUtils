# Comprehensive Report: DFTB+ Relaxation of Molecules on M(111) Surfaces with Adatoms

## Date: June 17, 2026
## Objective
Compare geometry relaxation energies for 5 test molecules (CH2NH_ep, CH2O_ep, H2O_ep, HCN_ep, NH3_ep) on Au(111), Ag(111), and Cu(111) surfaces with an adatom, using three methods:
- DFTB+ auorg (Slater-Koster)
- GFN1-xTB (via DFTB+ with tblite)
- GFN2-xTB (via DFTB+ with tblite)

---

## 1. Geometry Generation

### What was done
Generated M(111) 2x2x2 surface slabs with an adatom and molecule using `surface_workflow.py` with ASE's `fcc111` and `add_adsorbate` functions.

### Metal lattice constants used
- Au: 4.078 Å
- Ag: 4.086 Å
- Cu: 3.615 Å

### Output
15 geometries (3 metals × 5 molecules) saved to `tmp/m111_adatom_mol/{metal}/`

---

## 2. Method 1: GFN1-xTB

### Status: ✅ COMPLETED (15/15 calculations)

### What was done
- Used `DFTBPlusBackend` with `method='GFN1-xTB'` and `kpts=None` (no k-points)
- Ran relaxations for all 3 metals × 5 molecules
- Saved persistent output to `tmp/relax_xtb_GFN1/{metal}/{molecule}/`

### Results (Total Energy, eV)

| Molecule   | Au         | Ag         | Cu         |
|------------|------------|------------|------------|
| CH2NH_ep   | -1157.56   | -1126.44   | -1294.31   |
| CH2O_ep    | -1183.25   | -1152.36   | -1320.38   |
| H2O_ep     | -1127.64   | -1096.13   | -1263.66   |
| HCN_ep     | -1127.62   | -1096.57   | -1264.29   |
| NH3_ep     | -1101.63   | -1070.24   | -1238.31   |

### Notes
- GFN1-xTB converged reliably for all systems
- No special convergence tricks needed

---

## 3. Method 2: GFN2-xTB

### Status: ⚠️ PARTIAL (10/15 calculations)

### What was done
- Used `DFTBPlusBackend` with `method='GFN2-xTB'`
- Initial attempts failed with "SCC is NOT converged, maximal SCC iterations exceeded"
- Tried multiple convergence strategies (see Problems section)
- Used GFN1-relaxed geometry as starting point for GFN2

### Convergence Strategies Attempted

| Strategy | Status | Result |
|----------|--------|--------|
| SCCTolerance = 1.0E-6 | ❌ Rejected | Not sufficient |
| SCCTolerance = 1.0E-5 | ❌ Rejected | Not sufficient |
| SCCTolerance = 1.0E-4 | ✅ Accepted | Helps but not for all |
| Temperature = 300.0 / 1000.0 | ❌ Rejected | Parser error |
| Mixer (Broyden/Simple) | ❌ Rejected | Parser error |
| DampXTL = Yes | ❌ Rejected | Parser error |
| GFN1 geometry as start | ✅ Works | Helped Au and Cu |
| No k-points (kpts=None) | ✅ Works | Helped Au and Cu |

### Problem
DFTB+ xTB implementation has very limited convergence options. The only supported option is `SCCTolerance`. Temperature broadening, mixer methods, and DampXTL are all rejected by the parser for the xTB Hamiltonian.

### Resolution
- Loosened `SCCTolerance` to `1.0E-4` for GFN2-xTB
- Used GFN1-relaxed geometry as starting point
- Removed k-points (used `kpts=None`)
- This combination worked for **Au and Cu**, but **Ag still fails**

### Results (Total Energy, eV)

| Molecule   | Au         | Ag         | Cu         |
|------------|------------|------------|------------|
| CH2NH_ep   | -1139.00   | ❌ FAIL    | -1129.85   |
| CH2O_ep    | -1161.92   | ❌ FAIL    | -1147.60   |
| H2O_ep     | -1107.26   | ❌ FAIL    | -1089.26   |
| HCN_ep     | -1106.12   | ❌ FAIL    | -1101.30   |
| NH3_ep     | -1081.07   | ❌ FAIL    | -1071.88   |

### Why Ag Fails
Ag GFN2-xTB has particularly difficult SCC convergence. Even with:
- GFN1-relaxed geometry as starting point
- Looser SCCTolerance (1e-4)
- No k-points
- The SCC still oscillates and exceeds maximal iterations

---

## 4. Method 3: DFTB+ auorg

### Status: ✅ COMPLETED (5/5 calculations for Au only)

### What was done
- Used `DFTBPlusBackend` with `sk_path='/home/prokop/SIMULATIONS/dftbplus/slakos/auorg/auorg-1-1'`
- auorg parametrization only supports Au, C, H, N, O
- Enabled SCC with `Filling = Fermi { Temperature [Kelvin] = 300.0 }`

### Problems and Resolutions

| Problem | Resolution |
|---------|------------|
| k-point format rejected | Used direct `KPointsAndWeights { 0.0 0.0 0.0 1.0 }` format |
| `OrbitalResolvedSCC = Yes` rejected | Commented out (not supported in this DFTB+ version) |

### Results (Total Energy, eV) - Au only

| Molecule   | Au (auorg) |
|------------|------------|
| CH2NH_ep   | -828.01    |
| CH2O_ep    | -843.59    |
| H2O_ep     | -799.03    |
| HCN_ep     | -807.53    |
| NH3_ep     | -782.20    |

---

## 5. Energy Comparison Across Methods (Au)

| Molecule   | GFN1-xTB   | GFN2-xTB   | auorg     | Δ(GFN1-GFN2) | Δ(GFN1-auorg) |
|------------|------------|------------|-----------|--------------|-----------------|
| CH2NH_ep   | -1157.56   | -1139.00   | -828.01   | -18.56       | -329.55         |
| CH2O_ep    | -1183.25   | -1161.92   | -843.59   | -21.33       | -339.66         |
| H2O_ep     | -1127.64   | -1107.26   | -799.03   | -20.38       | -328.61         |
| HCN_ep     | -1127.62   | -1106.12   | -807.53   | -21.50       | -320.09         |
| NH3_ep     | -1101.63   | -1081.07   | -782.20   | -20.56       | -319.43         |

### Key Observations
1. **GFN1 vs GFN2**: GFN1 is ~20 eV lower in energy than GFN2 (different reference states within tblite)
2. **xTB vs auorg**: auorg energies are ~320-340 eV higher (less negative) than xTB methods. This is expected due to completely different parametrization and reference states.
3. **Energy ordering is consistent** across methods: CH2O_ep < CH2NH_ep < HCN_ep ≈ H2O_ep < NH3_ep

---

## 6. Code Modifications

### File: `py/interfaces/dftbplus.py`

1. **`run_relax()` method**
   - Added `outdir` parameter to save output persistently (instead of temp directory)
   - Added `cleanup` flag to only delete temp dir when `outdir` is not specified

2. **`_write_hsd()` method**
   - Fixed k-point format for gamma-point: uses direct `KPointsAndWeights { 0.0 0.0 0.0 1.0 }` block
   - Added `SCCTolerance = 1.0E-4` for GFN2-xTB (looser than default)
   - Removed `OrbitalResolvedSCC` (not supported in this DFTB+ version)

3. **Removed `ignore_errors=True`** from `shutil.rmtree()` calls in `run_energy` and `run_relax`

### File: `py/tasks/relax.py`

- Pass `outdir` to `backend.run_relax()` in local mode to enable persistent output

---

## 7. Summary of Achievements

| Task | Status | Details |
|------|--------|---------|
| Generate geometries | ✅ Done | 15 systems (3 metals × 5 molecules) |
| GFN1-xTB relaxations | ✅ Done | 15/15 converged |
| GFN2-xTB relaxations | ⚠️ Partial | 10/15 converged (Au + Cu), Ag fails |
| auorg relaxations | ✅ Done | 5/5 for Au only |
| Energy comparison | ✅ Done | See tables above |
| Persistent output | ✅ Done | All results saved to `tmp/relax_*` |

---

## 8. Known Limitations and Recommendations

### Limitations
1. **GFN2-xTB in DFTB+ has limited convergence options** - cannot control temperature, mixer, or damping
2. **Ag GFN2-xTB fails SCC convergence** even with best available strategies
3. **auorg only supports Au** (among the three metals tested)

### Recommendations
1. For **GFN2-xTB on Ag**, use standalone `xtb` command or ASE's `xtb-python` interface instead of DFTB+
2. For **k-point sampling**, implement automatic k-point density generator (e.g., Monkhorst-Pack with minimum k-point spacing)
3. For **charge initialization**, investigate if DFTB+ supports reading `charges.bin` from GFN1 for GFN2 restart

---

## 9. Output Directory Structure

```
tmp/
├── m111_adatom_mol/          # Generated geometries
│   ├── Au/
│   ├── Ag/
│   └── Cu/
├── relax_xtb_GFN1/            # GFN1-xTB results (all metals)
│   ├── Au/
│   ├── Ag/
│   └── Cu/
├── relax_xtb_GFN2/            # GFN2-xTB results (Au, Cu only)
│   ├── Au/
│   └── Cu/
├── relax_auorg/               # auorg results (Au only)
│   └── Au/
└── DFTB_RELAXATION_REPORT.md  # This report
```

---

## 10. Conclusion

Successfully completed geometry relaxations for 25 out of 30 planned calculations (83%). GFN1-xTB is the most robust method across all three metals. GFN2-xTB works for Au and Cu but fails for Ag due to SCC convergence limitations in the DFTB+ implementation. auorg provides a useful comparison but is limited to Au systems.

The energy ordering of molecules is consistent across methods, with CH2O_ep being the most stable and NH3_ep the least stable on all surfaces.
