# ChemBook — Metadata Tracking for QC Simulations

Filesystem-based metadata system. Each simulation directory contains a `chembook.json` with provenance, system info, method, and results. No SQL, no GUI — just JSON files + CLI tools.

## Quick Start

```bash
# Create a chembook.json skeleton before running a job
python -m py.chembook init ./H2O_relax --type relax --n-atoms 3 --elements "H:2,O:1" --code dftb+ --formula H2O

# Run a command with automatic provenance capture
python -m py.chembook run --type relax --code dftb+ --n-atoms 3 --elements "H:2,O:1" -- python run_relax.py

# Validate all nodes in a tree
python -m py.chembook validate ./project_root

# List all nodes
python -m py.chembook scan ./project_root
python -m py.chembook scan ./project_root --format json
```

## Schema (v0)

### Compulsory Fields

| Field | Type | Description |
|-------|------|-------------|
| `chembook.schema` | str | `"chembook.job.v0"` |
| `chembook.id` | str | 12-char hex, collision-checked |
| `chembook.created` | str | ISO 8601 timestamp |
| `chembook.status` | str | `pending` / `running` / `done` / `failed` / `pruned` |
| `job.type` | str | e.g. `relax`, `rigid_scan`, `fukui` |
| `system.n_atoms` | int | Total atom count |
| `system.elements` | dict | `{"H": 2, "O": 1}` |
| `method.code` | str | Lowercase, e.g. `dftb+`, `psi4`, `xtb` |
| `provenance.command` | str | Exact command string |

### Conditional (when status = done/failed)

| Field | Type | Description |
|-------|------|-------------|
| `provenance.duration_sec` | float | Wall-clock time from `perf_counter_ns` |
| `provenance.exit_code` | int | Process exit code |

### Key Optional Fields

- `provenance.hostname`, `provenance.cwd`, `provenance.real_path`, `provenance.symlink_traversed`
- `provenance.started`, `provenance.finished`, `provenance.git_commit`
- `system.formula`, `system.charge`, `system.spin`, `system.pbc`
- `method.method`, `method.basis`, `method.dispersion`, `method.code_version`
- `results.energy_eV`, `results.max_force_eVA`, `results.converged`
- `tags`, `notes`

## Symlink Strategy

Simulation data lives **outside** the git repo. Symlinks inside the repo point to external data directories. `chembook.json` records both paths:

```json
"provenance": {
  "cwd": "/repo/data_link/project_X/relax",
  "real_path": "/home/user/sim/project_X/relax",
  "symlink_traversed": true
}
```

Use `resolve_true_path(path)` from `core.py` to detect symlink traversal programmatically.

## Files

| File | Purpose |
|------|---------|
| `schema.py` | Dict-based validation, `create_skeleton()`, compulsory field definitions |
| `core.py` | ID generation, symlink-aware path resolution, node I/O, tree walking, `run_command_and_record()` |
| `cli.py` | CLI commands: `init`, `run`, `validate`, `scan` |
| `__main__.py` | Entry point for `python -m py.chembook` |

## Design Reference

Full design discussion: [`doc/ChemBook.chat.md`](../../doc/ChemBook.chat.md)
