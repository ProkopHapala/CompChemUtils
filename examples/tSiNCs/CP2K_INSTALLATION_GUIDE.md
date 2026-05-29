# CP2K Installation and Usage Guide

## System Information

**Machine:** GTX3090  
**OS:** Ubuntu 24.04.2 LTS  
**CPU:** AMD Zen3 (8 physical cores, 16 threads)  
**GPU:** NVIDIA RTX 3090 (CUDA 12.2 available)  
**Installation Date:** May 28, 2026

## Installation Method Used

### Method: Spack via make_cp2k.sh (NOT RECOMMENDED)

**Installation Command:**
```bash
cd /home/prokop/git_SW/cp2k
./make_cp2k.sh -bd
```

**⚠️ CRITICAL WARNINGS:**

1. **Extremely Time-Consuming:** The Spack-based installation took several hours to complete. All 182 dependencies were built from source, including large packages like PyTorch, DeepMD-kit, and Sirius.

2. **Massive Disk Usage:** The installation consumed significant disk space:
   - Spack dependencies: 8.6 GB
   - Build artifacts: 1.3 GB
   - Spack cache: 740 MB
   - Final installation: 752 MB
   - Total: **~11.4 GB** of disk space

3. **Complex Dependency Chain:** Spack builds a massive dependency tree including:
   - MPICH 5.0.1
   - OpenBLAS, ScaLAPACK
   - FFTW3, HDF5, LibXC
   - ELPA, COSMA, DBCSR
   - PyTorch 2.12.0 (CPU-only)
   - DeepMD-kit 3.1.3
   - Sirius 7.11.1
   - And many more...

4. **Fragile Process:** The initial attempt failed and required rebuilding all dependencies with `-bd` flag.

## Installation Location

**Source:** `/home/prokop/git_SW/cp2k`  
**Binary:** `/home/prokop/git_SW/cp2k/install/bin/cp2k.psmp`  
**Library:** `/home/prokop/git_SW/cp2k/install/lib/libcp2k.so.2026.1`  
**Spack dependencies:** `/home/prokop/git_SW/cp2k/spack/`

## Environment Configuration

Added to `~/.bashrc`:
```bash
# CP2K installation
export CP2K_HOME=/home/prokop/git_SW/cp2k
export PATH=$CP2K_HOME/install/bin:$PATH
export LD_LIBRARY_PATH=$CP2K_HOME/install/lib:$CP2K_HOME/spack/spack/opt/spack/view/lib64:$CP2K_HOME/spack/spack/opt/spack/view/lib:$CP2K_HOME/spack/spack/opt/spack/view/lib/python3.14/site-packages/torch/lib:$CP2K_HOME/spack/spack/opt/spack/view/lib/MiMiC:$LD_LIBRARY_PATH
```

## Usage

### Basic Usage

After sourcing `~/.bashrc` (or opening a new terminal):

```bash
# Check version
cp2k.psmp --version

# Run a calculation
cp2k.psmp input.inp
```

### MPI Parallel Execution

```bash
# Set OpenMP threads per MPI rank
export OMP_NUM_THREADS=2

# Run with 4 MPI ranks
mpiexec -n 4 cp2k.psmp input.inp

# Or use the launch script
launch mpiexec -n 4 cp2k input.inp
```

### Example Test Run

```bash
export OMP_NUM_THREADS=2
launch mpiexec -n 4 cp2k /home/prokop/git_SW/cp2k/benchmarks/CI/H2O-32_md.inp
```

This test completed successfully in ~166 seconds with 0 warnings.

## CP2K Version Information

**Version:** 2026.1 (Development Version)  
**Source revision:** 48c63364e3  
**Compiler:** GCC 13.3.0  
**Build type:** psmp (MPI + OpenMP + Shared)

**Enabled features:**
- omp, libint, fftw3, libxc, pexsi, elpa, parallel, scalapack, mpi_f08
- cosma, ace, deepmd, xsmm, plumed2, spglib, libdftd4, dftd4_v4_2
- mctc-lib, tblite, sirius, libvori, libbqb, libtorch, mimic
- libvdwxc, hdf5, trexio, libfci, libsmeagol, greenx

## Recommendations for Future Installations

### ⚠️ STRONGLY RECOMMENDED: Use Precompiled Binaries

**Why avoid Spack installation:**
- Takes several hours to build
- Consumes 20-35 GB of disk space
- Complex dependency management
- High chance of build failures
- Difficult to reproduce across systems

### Alternative Installation Methods

#### 1. Conda (Recommended)

```bash
# Install CP2K via conda-forge
conda create -n cp2k_env -c conda-forge cp2k
conda activate cp2k_env

# Or install with specific dependencies
conda install -c conda-forge cp2k libxc
```

**Advantages:**
- Precompiled binaries (minutes vs hours)
- Minimal disk usage
- Easy to reproduce across systems
- Automatic dependency management
- Easy to update/remove

#### 2. Precompiled Binaries from CP2K

Download precompiled binaries from: https://github.com/cp2k/cp2k/releases

**Advantages:**
- Optimized for specific architectures
- No compilation required
- Smaller footprint than Spack

#### 3. System Package Manager

On some systems, CP2K may be available via:
- `apt` (Ubuntu/Debian)
- `yum`/`dnf` (RHEL/CentOS/Fedora)
- Homebrew (macOS)

## What to Expect on Other Computers

### Hardware Requirements

**Minimum:**
- CPU: x86_64 with AVX2 support
- RAM: 8 GB (16+ GB recommended for larger calculations)
- Disk: 5 GB free space (for precompiled binaries)

**Recommended:**
- CPU: Modern x86_64 (Zen3/Zen4, Skylake+, or newer)
- RAM: 32+ GB
- Disk: 15+ GB (if building from source)
- GPU: NVIDIA/AMD for GPU-accelerated features (optional)

### Software Requirements

**For precompiled binaries (Conda):**
- Python 3.8+
- conda or mamba
- MPI implementation (optional, for parallel runs)

**For building from source (NOT recommended):**
- GCC 10+ or Intel oneAPI
- CMake 3.27+
- MPI (MPICH or OpenMPI)
- Fortran compiler
- Python 3.11+
- Several hours of build time
- 12-15 GB free disk space

### Installation Time Comparison

| Method | Time | Disk Space | Difficulty |
|--------|------|------------|------------|
| Conda | Unknown* | Unknown* | Easy |
| Precompiled binary | Unknown* | Unknown* | Easy |
| Spack build | Several hours | 11.4 GB | Hard |

*Note: Conda and precompiled binary installation times/disk usage not benchmarked on this system

## Troubleshooting

### Library Path Issues

If you get "cannot open shared object file" errors:
```bash
# Ensure LD_LIBRARY_PATH is set
echo $LD_LIBRARY_PATH

# Source bashrc if needed
source ~/.bashrc
```

### MPI Issues

If MPI commands are not found:
```bash
# Check MPI installation
which mpiexec

# Install MPI if needed (Ubuntu)
sudo apt install mpich
```

### Performance Tuning

For optimal performance:
```bash
# Set OpenMP threads to match physical cores per socket
export OMP_NUM_THREADS=8  # Adjust based on your CPU

# Use appropriate number of MPI ranks
# Usually: total_cores / OMP_NUM_THREADS
```

## Regression Testing

To run CP2K regression tests:
```bash
cd /home/prokop/git_SW/cp2k
./tests/do_regtest.py /home/prokop/git_SW/cp2k/install/bin psmp
```

## References

- CP2K Manual: https://manual.cp2k.org
- CP2K Website: https://www.cp2k.org
- CP2K GitHub: https://github.com/cp2k/cp2k
- Conda-forge CP2K: https://conda-forge.org/

## Summary

**Installation on GTX3090:**
- Method: Spack via make_cp2k.sh (painful, not recommended)
- Time: Several hours
- Disk: 11.4 GB (8.6 GB spack + 1.3 GB build + 752 MB install + 740 MB cache)
- Status: Working successfully

**Recommendation for other systems:**
- Use Conda precompiled binaries
- Much simpler and more reliable than Spack build
- Actual installation time and disk usage should be benchmarked on target system
