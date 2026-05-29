# Phonon Benchmark Toolkit

CLI scripts to download reference phonon data, set up ALAMODE+LAMMPS calculations,
and overlay/benchmark phonon dispersion curves for bulk Si and diamond.

## Files

| File | Purpose |
|------|---------|
| `phonon_config.json` | Tool and potential path configuration (edit for your system) |
| `download_phonon_refs.py` | Download phonon data from MP, phonondb, Mendeley Data |
| `setup_alamode_phonon.py` | Generate ALAMODE + LAMMPS input files |
| `setup_dftb_phonon.py` | Generate DFTB+ + phonopy input files |
| `plot_phonon_benchmark.py` | Overlay and benchmark phonon dispersions |
| `experimental_phonon_data.json` | Reference INS data points (Si & diamond) |

## Quick Start

### 0. Configure tool paths

Copy or edit `phonon_config.json` to point to your installed tools:

```json
{
  "tools": {
    "lammps_bin": "/path/to/lammps/src/lmp_serial",
    "dftb_bin": "/path/to/dftb+/dftb+",
    "slakos_dir": "/path/to/slakos",
    "phonopy_bin": "phonopy",
    "alamode_displace": "displace.py",
    "alamode_extract": "extract.py",
    "alamode_alm": "alm",
    "alamode_anphon": "anphon"
  },
  "potentials": {
    "si_sw": "/path/to/Si.sw",
    "si_tersoff": "/path/to/SiCGe.tersoff",
    "c_tersoff": "/path/to/SiC.tersoff"
  }
}
```

Alternatively, set environment variables (scripts will use config file if present):
- `LAMMPS_BIN`
- `DFTB_BIN`
- `SLAKOS_DIR`
- `PHONOPY_BIN`

### 1. Install dependencies

```bash
pip install mp-api pyyaml numpy matplotlib
```

### 2. Download reference data

**Materials Project** (computed DFT phonons — free API key required):
```bash
# Get API key from https://materialsproject.org/api
python download_phonon_refs.py mp --api-key YOUR_KEY --material-id mp-149 --outfile si_mp.json
python download_phonon_refs.py mp --api-key YOUR_KEY --material-id mp-66  --outfile diamond_mp.json
```

**phonondb** (Atsushi Togo's phonon database):
```bash
python download_phonon_refs.py phonondb --material-id mp-149 --outdir ./phonondb_si
python download_phonon_refs.py phonondb --material-id mp-66  --outdir ./phonondb_diamond
```

**Mendeley Data** (MTP machine-learning potential for Si/diamond):
```bash
python download_phonon_refs.py mendeley --doi 10.17632/6tjhd74t5r --outdir ./mtp_data
```

### 3. Set up calculations

**DFTB+ + phonopy** (recommended if DFTB+ is available):
```bash
python setup_dftb_phonon.py --material Si --supercell 2 2 2 --outdir dftb_si_2x2x2
python setup_dftb_phonon.py --material diamond --supercell 2 2 2 --outdir dftb_diamond_2x2x2
```

**ALAMODE + LAMMPS** (requires ALAMODE installation):
```bash
# Note: Your LAMMPS binary must have MANYBODY package for SW/Tersoff, or MEAM package for MEAM
python setup_alamode_phonon.py --material Si --potential sw --supercell 2 2 2
python setup_alamode_phonon.py --material Si --potential tersoff --supercell 2 2 2
python setup_alamode_phonon.py --material diamond --potential tersoff --supercell 2 2 2
python setup_alamode_phonon.py --material Si --potential mtp --mtp-file ./mtp_data/Si_diamond.mtp --supercell 2 2 2
```

This generates:
- `<prefix>.lammps` — LAMMPS structure file
- `<prefix>_force.in` — LAMMPS input template
- `<prefix>.alamode.in` — ALAMODE `alm` input
- `<prefix>.anphon.in` — ALAMODE `anphon` input
- `run_displace.sh`, `run_lammps_forces.sh`, `run_extract.sh`, `run_alamode.sh` — workflow scripts

For DFTB+ + phonopy, this generates:
- `dftb_in.hsd` — DFTB+ input file
- `band.conf` — phonopy band structure configuration
- `run_phonopy.sh` — Master script for the phonopy + DFTB+ workflow

### 4. Run calculations

**DFTB+ + phonopy:**
```bash
cd dftb_si_2x2x2
bash run_phonopy.sh
```

**ALAMODE + LAMMPS:**
```bash
cd Si_sw_2x2x2
bash run_alamode.sh
```

Follow the generated `run_alamode.sh` script. The typical steps are:

```bash
# 1. Generate displaced structures
bash run_displace.sh

# 2. Run LAMMPS on displaced structures, then extract forces
bash run_lammps_forces.sh
bash run_extract.sh

# 3. Compute force constants
alm Si_sw_2x2x2.alamode.in

# 4. Compute phonon dispersion
anphon Si_sw_2x2x2.anphon.in
```

The `anphon` output is typically `Si_sw_2x2x2.band.dat`.

### 5. Plot benchmark

```bash
python plot_phonon_benchmark.py \
    --material Si \
    --dftb dftb_band.yaml \
    --alamode Si_sw_2x2x2.band.dat \
    --mp si_mp.json \
    --phonondb ./phonondb_si/mp-149/band.yaml \
    --experimental experimental_phonon_data.json \
    --output si_benchmark.png
```

This overlays all curves and prints RMS errors against the experimental points.

## Recommended Methods & Potentials

| Code | Method | Best cheap option | Notes |
|------|--------|-------------------|-------|
| **DFTB+** | `matsci-0-3` or `pbc-0-3` SK tables | Free, tested for solids | Use with phonopy |
| **LAMMPS** | Lenosky MEAM (Si) | Best classical Si phonons | From NIST repo |
| **LAMMPS** | Tersoff (Si, C) | Fast but overestimates | Built into LAMMPS |
| **LAMMPS** | MTP (Si/diamond) | ML accuracy, open data | Download from Mendeley DOI 10.17632/6tjhd74t5r |

## Experimental Data Sources

The `experimental_phonon_data.json` contains approximate inelastic neutron scattering
(INS) reference points:
- **Si**: Dolling (1963) + Nilsson & Nelin (1972)
- **Diamond**: Warren et al. (1967) + Kulda et al.

These are approximate values for benchmarking. For publication-quality work, consult
the original papers and neutron scattering databases (e.g., IAEA EXFOR for some
cross-section data, though phonon dispersions are primarily in the literature).

## Notes

- **Materials Project**: The `mp-api` client is the official Python interface. An API key
  is free with registration.
- **phonondb**: The original Kyoto University website is closed. This script uses the
  WMD-group GitHub mirror, which scrapes the 2018-04-17 snapshot.
- **Mendeley Data**: Public datasets can be accessed via the REST API without authentication
  for metadata; file downloads may require a token if the dataset is restricted.
- **ALAMODE**: Must be installed separately. See https://alamode.readthedocs.io/
- **phonopy**: Must be installed for DFTB+ phonon calculations and for reading phonondb data.
- **LAMMPS packages**: Ensure your LAMMPS binary has the required packages:
  - MANYBODY package for Stillinger-Weber and Tersoff potentials
  - MEAM package for MEAM potentials
  - Rebuild LAMMPS with appropriate packages if needed
