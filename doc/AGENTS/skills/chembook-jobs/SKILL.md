---
name: chembook-jobs
description: Use when creating, baking, or running new QC jobs — wrap them in the ChemBook metadata protocol so every job has provenance, system info, method, and results in a discoverable chembook.json
trigger:
  glob:
    - "**/generate_jobs.py"
    - "**/bake_jobs.py"
    - "**/run_*.py"
    - "**/relax*.py"
    - "**/scan*.py"
    - "**/fukui*.py"
    - "examples/**"
    - "py/tasks/**"
---

## Core Rule: Every Job Gets a `chembook.json`

When you create, bake, or run a QC job (relax, scan, fukui, density, NEB, MD, geometry generation, …), the job directory MUST end up with a `chembook.json` describing what it is, how it was run, and (after completion) what it produced. No bare output folders. This is the protocol that keeps AI-generated campaigns navigable.

Reference: [`doc/ChemBook.chat.md`](../../ChemBook.chat.md) (full design rationale), [`py/chembook/README.md`](../../../py/chembook/README.md) (schema + CLI).

## What ChemBook Is

A filesystem-based metadata system. Each simulation directory is a **node** identified by containing `chembook.json`. No SQL, no GUI, no fixed directory hierarchy — discovery walks the tree looking for `chembook.json` files. Symlinks to external data are recorded (`provenance.real_path` + `provenance.symlink_traversed`).

## The Schema (v0 — `chembook.job.v0`)

Compulsory (enforced by `py/chembook/schema.py`):

| Field | Type | Notes |
|-------|------|-------|
| `chembook.schema` | str | `"chembook.job.v0"` |
| `chembook.id` | str | 12-char hex, collision-checked across the project tree |
| `chembook.created` | str | ISO 8601 with timezone |
| `chembook.status` | str | `pending` / `running` / `done` / `failed` / `pruned` |
| `job.type` | str | e.g. `relax`, `rigid_scan`, `fukui`, `density` (see `RECOMMENDED_JOB_TYPES` in schema.py) |
| `system.n_atoms` | int | Total atom count |
| `system.elements` | dict | `{"H": 2, "O": 1}` |
| `method.code` | str | Lowercase: `dftb+`, `pyscf`, `psi4`, `xtb`, `gpaw`, `ase` |
| `provenance.command` | str | Exact command string that launched the job |

Conditional (compulsory when `status` is `done`/`failed`): `provenance.duration_sec` (float, from `perf_counter_ns`), `provenance.exit_code` (int).

Recommended optional: `system.formula`, `system.charge`, `system.spin`, `system.pbc`, `method.method`, `method.basis`, `method.dispersion`, `method.code_version`, `results.energy_eV`, `results.max_force_eVA`, `results.converged`, `provenance.hostname`, `provenance.cwd`, `provenance.real_path`, `provenance.symlink_traversed`, `provenance.started`, `provenance.finished`, `provenance.git_commit`, `tags`, `notes`.

## Three Ways to Apply It — Pick One

### A. Wrap an external command with the CLI (simplest)

Use when you have an existing script and just want provenance capture:

```bash
python -m py.chembook run --type relax --code dftb+ --n-atoms 3 \
    --elements "H:2,O:1" -- python run_relax.py
```

`chembook run` writes a `pending` skeleton, runs the command, then updates `status`/`duration_sec`/`exit_code`. See `py/chembook/core.py:run_command_and_record()`.

### B. Bake `chembook.json` into generated cluster jobs (use for `bake_jobs.py` workflows)

When generating many jobs from a template (fukui cluster, scan arrays, …), inject ChemBook init + done snippets into the baked script so each job writes its own `chembook.json` at runtime on the compute node. Use the helpers in `py/tasks/bake_jobs.py`:

```python
from py.tasks.bake_jobs import bake_chembook_init_code, bake_chembook_done_code

chembook_id = secrets.token_hex(6)   # generate per-job ID
cb_init = bake_chembook_init_code(chembook_id, n_atoms, elements, code='pyscf',
                                  job_type='fukui', basis='def2-SVP', xc='PBE')
cb_done = bake_chembook_done_code(energy_expr='mf.e_tot', energy_unit='Ha')

script = template.replace('@@CHEMBOOK_INIT@@', cb_init) \
                 .replace('@@CHEMBOOK_DONE@@', cb_done)
```

Reference implementations: `examples/fukui/pyscf_fukui_cluster/generate_jobs.py`, `examples/fukui/gpaw_fukui_cluster/generate_jobs.py`, `examples/fukui/pyscf_relax_hbonds/generate_jobs.py`.

### C. Write `chembook.json` directly in a Python script (geometry-generation, postprocess)

For jobs that don't run a QC code (geometry builders, extractors, plotters), build the dict and write it via `py/chembook/core.py`:

```python
from py.chembook import core, schema

node = schema.create_skeleton(
    id=core.generate_id(root_dir=project_root),
    job_type='geometry_generation', n_atoms=len(es), elements=elements,
    code='ase', command=' '.join(sys.argv), name=f'{metal}_111_bare',
    status='done', hostname=socket.gethostname(),
    cwd=logical, real_path=real, symlink_traversed=sym,
)
node['system']['formula'] = f'{metal}{len(es)}'
node['method']['builder'] = 'MetalTips.build_fcc111_adatom'
node['results'] = {'converged': True}
core.write_node(out_dir, node)
```

See `examples/MetalTip_Molecule_interaction/generate_metal_geometries.py` for a worked example with both `meta.json` (system-level) and `chembook.json` (job-level) patterns.

## Procedure When Creating a New Job

1. **Decide the node directory.** A node = any folder that will hold `chembook.json`. Layout is flexible; recommended grouping is `system/method/basis/job_type` or `system/job_type/variant` (see `doc/ChemBook.chat.md` §"Revised ChemBook Design"). The tool discovers by `chembook.json`, NOT by path — so the name is for humans.
2. **Pick the application mode (A/B/C above)** based on whether the job runs an external command, is baked for a cluster, or is a pure-Python producer.
3. **Fill compulsory fields before the run** (`status='pending'`). This captures failed attempts too — never write the file only after success.
4. **Set `job.type` to a value from `RECOMMENDED_JOB_TYPES`** in `schema.py`. Unknown types are tolerated with a warning, but prefer the standard vocabulary so `chembook scan`/`find` queries stay consistent.
5. **Record provenance at launch time**: `provenance.command` (exact argv), `provenance.hostname`, `provenance.cwd`, `provenance.real_path`, `provenance.symlink_traversed`, `provenance.git_commit` (use `core.get_git_commit()`).
6. **Update to `done`/`failed` after the run** with `duration_sec` (from `time.perf_counter_ns()`), `exit_code`, `started`/`finished` ISO timestamps. Use `core.update_node_status()`.
7. **Fill `results.*`** with the scalar outputs that matter for downstream queries: `energy_eV`, `max_force_eVA`, `converged`. Heavy arrays go in separate files (csv/npz) listed under a `files` block, not in the JSON.
8. **Validate**: run `python -m py.chembook validate <project_root>` after a campaign. Fix every ERROR; warnings about unknown `job.type` are acceptable only if you intentionally added a new type.

## Querying / Inspecting

```bash
python -m py.chembook scan ./project_root              # table of all nodes
python -m py.chembook scan ./project_root --format json
python -m py.chembook validate ./project_root          # check all nodes
python -m py.chembook init <dir> --type relax --n-atoms 3 --elements "H:2,O:1" --code dftb+
```

For ad-hoc queries across many nodes, `chembook scan --format json | jq ...` or `rg --files -g 'chembook.json' | xargs jq` are the intended tools. SQLite index (`chembook index`) is planned but not yet implemented.

## Hard Rules

- **No job directory without `chembook.json`.** If you create a folder that holds simulation outputs, it is a node — write the file.
- **Write `pending` BEFORE running.** Never retroactively fabricate provenance.
- **Use `perf_counter_ns` for timing.** Wall-clock only; convert to seconds with `/1e9`.
- **`method.code` is lowercase.** `dftb+`, `pyscf`, `psi4`, `xtb`, `gpaw`, `ase` — not `DFTB+`/`PySCF`.
- **IDs are 12-char hex** from `secrets.token_hex(6)`, collision-checked via `core.generate_id(root_dir=...)`.
- **Don't bloat the JSON.** Compulsory + a few recommended fields. Arrays → files listed in `files.*`.
- **Symlinks to external data are first-class.** Always record both `cwd` (logical) and `real_path` (physical) when the data lives outside the repo.

## What Is NOT Yet Implemented (planned in chat)

`extract` (parse QC outputs → `results.*`), `sync` (regenerate README summaries bottom-up), `find` (fast query, optional SQLite), `convert` (csv↔npz), `plot`, `prune --dry-run`/`--level`, `migrate`, `index`. If a task needs one of these, flag it — do not silently reinvent.

## STOP Triggers

- About to write a script that produces simulation outputs and there is no `chembook.json` plan → STOP, pick application mode A/B/C.
- About to invent a new metadata format / ad-hoc `meta.json` schema → STOP, check whether `chembook.job.v0` covers it; extend `schema.py` if needed (and bump `SCHEMA_VERSION`).
- About to hard-code a `/home/...` path into `provenance` → STOP, use `core.resolve_true_path()` so the JSON stays machine-portable.
- About to write timing with `time.time()` → STOP, use `time.perf_counter_ns()`.
- About to delete a node folder → STOP, pruning must go through a logged `chembook prune` step (not yet implemented — for now, mark `chembook.status='pruned'` and keep the tombstone JSON).
