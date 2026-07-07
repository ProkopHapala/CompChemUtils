# hbond

Build, relax, and rigid-scan hydrogen-bonded dimers from e-pair oriented monomer XYZ files.

- **relax_dimer.py** — `geom_engine.build_hbond_dimer()` (acceptor lp along `+axis`, donor O–H toward acceptor) + `py.tasks.relax` via xTB / DFTB+
- **scan_dimer.py** — rigid acceptor-O ··· donor-O scan from relaxed geometry (`make_scan_grid_geometric` + `make_rigid_shift_frames` + `rigid_scan`)

Monomers must include dummy `E` electron-pair atoms ([`../add_epairs.py`](../add_epairs.py)). Homodimer by default; `--mol2` for heterodimers. Dummy `E` atoms are stripped during dimer construction.

## Usage

```bash
# xTB: build + relax
python relax_dimer.py --mol data/xyz/H2O.xyz --backend xtb --outdir tmp/H2O_dimer_xtb

# Rigid distance scan from relaxed geometry (~39 grid points: 0.1 Å near r_eq, geometric coarsening, 1 Å / 5 Å far)
python scan_dimer.py --geom tmp/H2O_dimer_xtb/relaxed.xyz --backend xtb --outdir tmp/H2O_dimer_scan_xtb

# DFTB+ (plain SCC if binary lacks s-dftd3)
python relax_dimer.py --mol data/xyz/H2O.xyz --backend dftb --method-dftb none --sk-set mio/mio-1-1 --outdir tmp/H2O_dimer_dftb
python scan_dimer.py --geom tmp/H2O_dimer_dftb/relaxed.xyz --backend dftb --method-dftb none --outdir tmp/H2O_dimer_scan_dftb

# Heterodimer
python relax_dimer.py --mol data/xyz/HCOOH.xyz --mol2 data/xyz/NH3.xyz --backend xtb --outdir tmp/mixed
```

SK paths: `machine_config.yaml` → `sk_dir` + `--sk-set` (default `mio/mio-1-1` for H/C/N/O).

## Outputs

| File | Script | Content |
|------|--------|---------|
| `start.xyz` | relax | Initial e-pair oriented dimer |
| `relaxed.xyz` | relax | Optimized geometry |
| `scan.xyz` | scan | Grid frames (pre-energy) |
| `scan_out.xyz` | scan | Frames with energies in comment line |
| `scan.dat` | scan | r, E_tot, E_bind columns |
| `scan.png` | scan | E_bind vs distance |
| `distances.dat` | scan | Grid distances (Å) |

## Reference checks (H₂O homodimer)

| Backend | O···O at minimum | E_bind min | Notes |
|---------|------------------|------------|-------|
| GFN2-xTB | ~2.84 Å | ~−0.22 eV | Dispersion + H-bond in xTB |
| DFTB+ SCC (no D3) | ~2.90 Å | ~−0.11 eV | Shallow well without dispersion |

See [`/doc/topical_audit.md`](/doc/topical_audit.md) (Water dimer) and [`/doc/AGENTS/protocols/domain/noncovalent_interactions.md`](/doc/AGENTS/protocols/domain/noncovalent_interactions.md).
