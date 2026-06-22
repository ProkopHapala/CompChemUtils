# USER

I would like to make some journalling or data management (book keeping, organization) system for computational chemistry and material science. Not sure if I want take off-the shelf solutions or make my own tailored. Generaly I want to solve the problem that with AI I can generate lot of jobs and run them but then I have problem to navigate the results as every time AI save it different (different format, directory structures etc). I need some unified protocol and template following principles of least surprised. So the system is for me locally not to share data on some public server like material project, nomad etc but following similar rules can be useful. I'm not exactly sure what I need and want yet (that's why we need brainstorming). But some ideas:

1) should organize in hierarchical folders with readme.md files (Unstructured description), should contain JSON file following template with compulsory and optional fields 
2) very important is to store info how exactly it was run like bash command with all arguments, settings (producing such JSON should be part of python script running the job) otherwise I have hard time to remember the history how data was created 
3) the essential information (summaris) should bouble up the hierarchy (hierarchical readme summaries)
4) there should be general leveled clean-up mechanism, like different data have different size\value ratio. Like total energy is one number, and very valuable. Checkpoint Files or chgcar from vasp are huge and rather fast to compute. Final relaxed geometry is in the middle very valuable and small, relaxation trajectory is bigger and add only modest debug value on top of final relaxed geom.
We want to have possibility to "lossy conpress" or prune our data. E.g. extract energies along relaxed scan or NEB and delete outcar and wavecars. Or instead of deleting we can copy the extract to different place while preserving the structure.

---

# Gemini

This is a classic "data-avalanche" problem, amplified by AI generation. When you can spin up 100 molecular relaxation loops or NEB calculations in minutes, manual book-keeping shatters.

Your instincts are spot-on: you need something that balances the **human-readability** of flat files (the "Principle of Least Surprise") with the **machine-readability** required to parse, aggregate, and prune data programmatically.

Let’s brainstorm the architecture of this system, which we can call a **Hierarchical Laboratory Information Management System (H-LIMS)** for local simulation data.

---

## 1. Directory Structure & The "Principle of Least Surprise"

To keep it local, easily searchable (via standard tools like `grep`, `find`, or custom Python scripts), and version-control friendly, a strict, self-documenting directory hierarchy is best.

### Proposed Folder Topology

```text
project_root/
│
├── project_meta.json          # High-level project goals, targets
├── README.md                  # Auto-generated/manual top-level summary
│
└── systems/
    └── molecule_A/
        ├── system_meta.json   # SMILES, InChI, total charge, spin multiplicity
        │
        ├── method_PBE_def2-SVP/
        │   ├── method_meta.json  # Functional, basis set, software (VASP/Fireball/Orca)
        │   │
        │   ├── job_001_relax/
        │   │   ├── job_record.json  # COMPULSORY: Executable, bash command, timestamps, status
        │   │   ├── job_results.json # COMPULSORY: Total energy, convergence flag, final geometry
        │   │   ├── README.md        # Auto-generated job summary
        │   │   ├── input/           # Frozen input files
        │   │   ├── output_raw/      # Large raw files (WAVECAR, CHGCAR, OUTCAR) -> Subject to pruning
        │   │   └── output_parsed/   # Extracted trajectory (XYZ), energy curve
        │   │
        │   └── job_002_NEB/
        │
        └── method_B3LYP_6-31G/

```

### Why this works:

* **Decoupling System from Method:** Separating the chemical system (geometry/topology) from the electronic structure method prevents directory spaghetti.
* **The `input/` Sanity Check:** Never run a job directly in the folder where your AI writes scripts. Copy the verified inputs into an `input/` subdirectory so you *know* exactly what touched the binary.

## 2. Unification Protocol: Schema-Driven JSONs

Since your AI generators output different formats, your Python wrapper script (the "Runner") must act as the translation layer. It should enforce a strict JSON schema before and after the binary runs.

### Compulsory Fields (`job_record.json` & `job_results.json`)

* **`provenance`:** * `uuid`: Unique identifier for the job.
* `command_line`: The exact bash command string executed (e.g., `mpirun -np 24 vasp`).
* `environment`: Python environment version, compiler/MPI flags, or git hash of your custom solver.


* **`chemical_identity`:** Formula, charge, multiplicity, constraints.
* **`thermodynamics`:** `total_energy` (in eV or Hartree—pick *one* standard and stick to it strictly), `is_converged` (boolean).
* **`geometry`:** Initial and final coordinates in a standardized internal format (e.g., a flat nested list of `[Element, X, Y, Z]`).

> **💡 Rule of Thumb:** If a script can't parse `job_results.json` to find a single float value for `total_energy`, the job is flagged as "corrupted/incomplete."

---

## 3. "Bubbling Up" Information (Hierarchical Summaries)

You don't want to dig four levels deep to see if a relaxation converged. You need a synchronization script (`hlims-sync`) that traverses the tree backwards.

```text
[Job Level: job_results.json] ──> Extracts Energy/Convergence
          │
          ▼
[Method Level: README.md] ──────> Updates markdown table of all jobs under this method
          │
          ▼
[System Level: README.md] ──────> Updates Pareto front (Energy vs. Functional/Basis)

```

### Mechanism:

* **The Python Crawler:** A local daemon or a command you run manually (`hlims summary`). It looks for `job_results.json` files, reads them, and rewrites the parent folders' `README.md` files using Python's Jinja2 templates.
* **The Markdown API:** The `README.md` can have comment tags like `and`. Your script swaps the text inside, keeping any manual human notes outside the tags intact.

## 4. Multi-Level Clean-up & Data Pruning ("Lossy Compression")

Simulation data has a massive disparity in Value-per-Gigabyte ($V/\text{GB}$). You can implement a tiered data lifecycle utility (`hlims-prune`).

### The Tiered Data Value Scale

| Tier | Data Type | Value/$V/\text{GB}$ | Action Policy |
| --- | --- | --- | --- |
| **Tier 1** | Total Energy, Dipole, Final `.xyz`, `job_record.json` | **Infinite** (Bytes size) | **Archived Forever.** Never delete. Backup to cloud/external. |
| **Tier 2** | Relaxation Trajectory, Forces profile, NEB intermediate images | **High** (Megabytes) | **Keep Compressed.** Store as a single binary file (e.g., NetCDF or compressed Extended XYZ). |
| **Tier 3** | Slurm log, parsed standard output (`OUTCAR`) | **Medium** (Megabytes) | **Prune after 3 months** if Tier 1 data confirms success. |
| **Tier 4** | Wavefunctions, Charge Densities (`WAVECAR`, `CHGCAR`) | **Low** (Gigabytes) | **Immediate Deletion** or "Extract & Kill" within 7 days of successful run. |

### The "Extract & Kill" Pipeline

When you trigger `hlims-prune --level 3`:

1. It verifies `job_results.json` says `is_converged: true`.
2. It checks if the final energy and final geometry are successfully cached in `job_results.json`.
3. It extracts the raw energy profile along the relaxation path into a lightweight JSON array.
4. **It deletes `WAVECAR`, `CHGCAR`, and compresses `OUTCAR` into a `.gz` archive.**

## Off-the-Shelf vs. Custom Tailored?

There are existing frameworks in the Materials Science community, but they might be overkill or too rigid for a local fast-prototyping workflow:

* **AiiDA:** Extremely powerful for provenance tracking, but has a steep learning curve, requires a PostgreSQL database backend, and forces you into their ecosystem.
* **Signac:** Closer to what you want. It manages file-based workflows and data spaces in hierarchical directories, but doesn't specifically cater to your exact "energy bubbling/pruning" needs out of the box.
* **ASE (Atomic Simulation Environment) Databases:** Good for storing molecules and energies in a local SQLite file, but doesn't handle the raw bash/log file tracking very neatly.

### Recommendation: Build a Lightweight Custom Wrapper

Since you need a system that fits your local workflow and handles your specific pruning rules, a custom Python-driven toolset is ideal. It doesn't need to be massive—just a few scripts utilizing standard libraries (`pathlib`, `json`, `pydantic` for schema validation).

How does this structural layout look to you? Would you prefer a purely flat file-system architecture, or would you want a lightweight local database (like SQLite) indexing the folders behind the scenes to allow for fast querying?

---

# ChatGPT 5.5 instant

I think you want **not primarily a workflow engine**, but a **local provenance + journalling protocol** with a few helper scripts. Existing tools are useful inspiration, but probably too heavy if your main pain is “AI generated jobs are saved inconsistently.”

A good compromise:

**Use your own filesystem protocol + JSON schema + small CLI**, but borrow ideas from signac/AiiDA/NOMAD. signac is closest philosophically: file-based storage with indexed metadata; AiiDA is strongest for full provenance graphs; NOMAD is useful as a schema/FAIR reference but too platform-like for your local use. ([Signac Documentation][1])

## Core idea: every directory is a “node”

Each folder has:

```text
project/
  README.md
  index.json
  systems/
  campaigns/
  analysis/
  archive/
```

Every computational job folder has:

```text
000123_relax_NaCl_PTCDA/
  README.md              # human notes
  meta.json              # machine-readable full provenance
  input/                 # copied exact inputs
  run/                   # scripts, command, stdout/stderr
  output_raw/            # OUTCAR, vasprun.xml, logs, trajectories
  extracted/             # energy.json, final.xyz, forces.npy, bands.json
  figures/               # plots
  cleanup.json           # what was removed/compressed/extracted
```

The key rule should be:

> **Raw data may be ugly; extracted data must be beautiful.**

AI scripts can generate whatever, but before the job is accepted into your archive, a `chembook ingest` step normalizes it.

## Minimal `meta.json`

Something like:

```json
{
  "schema": "chembook.job.v0.1",
  "id": "2026-06-22T14-35-10_relax_PTCDA_NaCl",
  "title": "PTCDA on NaCl relaxation",
  "status": "done",
  "created": "2026-06-22T14:35:10+02:00",
  "project": "GridFF_validation",
  "campaign": "PTCDA_NaCl_relax_scan",

  "system": {
    "name": "PTCDA_NaCl_100",
    "formula": "C24H8O6 + NaCl slab",
    "structure_initial": "input/start.xyz",
    "structure_final": "extracted/final.xyz",
    "charge": 0,
    "spin": 1,
    "pbc": [true, true, false]
  },

  "method": {
    "code": "VASP",
    "code_version": "6.x",
    "level": "PBE-D3",
    "basis_or_cutoff": "ENCUT=500 eV",
    "kpoints": [2, 2, 1],
    "settings_file": "input/INCAR"
  },

  "run": {
    "hostname": "luna",
    "workdir": "/path/original/workdir",
    "command": "sbatch run.sh",
    "script": "run/run.sh",
    "git_commit": "abc123",
    "python_env": "env.yml",
    "started": "...",
    "finished": "...",
    "returncode": 0
  },

  "results": {
    "energy_eV": -1234.56789,
    "max_force_eVA": 0.012,
    "converged": true,
    "dipole_D": [0.0, 0.0, 3.1]
  },

  "files": {
    "keep_forever": ["meta.json", "README.md", "extracted/final.xyz", "extracted/energy.json"],
    "valuable": ["output_raw/vasprun.xml", "extracted/trajectory.xyz"],
    "recomputable_large": ["output_raw/WAVECAR", "output_raw/CHGCAR"],
    "trash_after_extract": ["output_raw/OUTCAR"]
  },

  "parents": [],
  "children": [],
  "tags": ["relaxation", "NaCl", "PTCDA", "DFT"]
}
```

## “Bubbling up” summaries

Each directory-level `index.json` is generated, not manually edited:

```json
{
  "schema": "chembook.index.v0.1",
  "path": "campaigns/PTCDA_NaCl_relax_scan",
  "n_jobs": 128,
  "n_done": 121,
  "n_failed": 7,
  "best_energy_eV": -1234.88,
  "representative_jobs": [
    "000042_relax_site_A",
    "000081_relax_site_B"
  ],
  "summary_files": [
    "summary.csv",
    "energy_landscape.png"
  ]
}
```

Then `README.md` can contain human commentary plus an auto-generated block:

```md
# PTCDA / NaCl relaxation scan

Human notes:
- Site A seems most stable.
- Some failures are due to slab atoms drifting.

<!-- CHEMBOOK:SUMMARY:START -->
128 jobs; 121 finished; 7 failed.
Best energy: -1234.88 eV in `000042_relax_site_A`.
Main outputs: `summary.csv`, `energy_landscape.png`.
<!-- CHEMBOOK:SUMMARY:END -->
```

This gives you both **narrative memory** and **machine-searchable state**.

## Cleanup levels

I would define explicit retention levels:

```text
L0 full raw
  keep everything: WAVECAR, CHGCAR, OUTCAR, trajectory, logs

L1 reproducible
  delete huge restart files, keep full text/XML output and inputs

L2 extracted
  keep final geometry, energy, forces, key scalar results, plots, run command

L3 summary only
  keep only one-line result in parent summary plus metadata pointer

L4 tombstone
  keep only meta.json saying what existed and why it was deleted
```

The important part: cleanup must be **recorded as provenance**, not silent deletion.

```json
{
  "cleanup_level": "L2_extracted",
  "date": "2026-06-22",
  "removed": [
    {"file": "output_raw/WAVECAR", "reason": "large_recomputable", "size_GB": 8.4},
    {"file": "output_raw/CHGCAR", "reason": "large_recomputable", "size_GB": 2.1}
  ],
  "preserved_extracts": [
    "extracted/final.xyz",
    "extracted/energy.json",
    "extracted/trajectory_minimal.xyz"
  ]
}
```

## What I would build first

Not a big framework. Just:

```text
chembook init project_name
chembook new-job template.json
chembook capture -- command args...
chembook extract vasp jobdir/
chembook summarize campaign/
chembook cleanup --level L2 jobdir/
chembook find "PTCDA NaCl converged energy < -1234"
```

Internally this can be plain Python + JSON + Markdown + SQLite index. The filesystem remains the source of truth; SQLite is just a fast searchable cache.

## Existing tools: my recommendation

For your case:

**Do not start with AiiDA/atomate2** unless you want to submit and control whole workflows through their ecosystem. AiiDA gives excellent provenance graphs, but it imposes a database/workflow worldview. Atomate2 is powerful for standardized high-throughput materials workflows, especially VASP-like pipelines, but may be too opinionated for your FireCore/DFTB/SPM/AI-generated hybrid workflows. ([AiiDA Documentation][2])

**Look seriously at signac** because it matches your “local folders + metadata” instinct. It stores data directly on the filesystem with metadata and indexing, which is close to what you describe. ([Signac Documentation][1])

**Use NOMAD as a schema inspiration**, not necessarily as the main tool. Its strength is normalization, metadata, parsers, and FAIR materials data conventions. ([Research Data Mainz][3])

My instinct: build **ChemBook**, a thin local protocol, and optionally make it able to export to NOMAD-like/archive formats later.

[1]: https://signac.readthedocs.io/?utm_source=chatgpt.com "Welcome to the signac framework documentation! — signac ..."
[2]: https://aiida.readthedocs.io/projects/aiida-core/en/stable/topics/provenance/concepts.html?utm_source=chatgpt.com "Concepts — AiiDA 2.7.3 documentation"
[3]: https://www.forschungsdaten.uni-mainz.de/wp-content/uploads/sites/281/2025/11/2025-10-30_Mansour-NOMAD-2.pdf?utm_source=chatgpt.com "Research Data Management with FAIRmat and NOMAD"

---

# DeepSeek-V4-flash

This is the exact "data deluge" problem hitting every AI-accelerated computational lab right now. **My strong advice: Do not build a monolithic database (SQL/NoSQL) yet.** That locks you into a schema you’ll hate in 3 months. Instead, build a **"Filesystem Ontology"**—a strict, self-describing folder structure enforced by a lightweight Python CLI. 

Here is a brainstorming blueprint addressing your 4 pillars, borrowing heavily from NOMAD/OPTIMADE but adapted for local "single-player" mode.

### 1. The Atomic Unit: The "Calculation Node"
Every single job lives in its own timestamped or named folder (e.g., `2026-06-22_TiN_bulk_relax/`). 

- **`manifest.json`** (Machine-readable): Enforced via a **Pydantic v2 schema**. If the JSON doesn't validate, your scripts crash immediately (this enforces the "least surprise"). 
- **`README.md`** (Human-readable): Auto-generated from the JSON, but allows manual notes.
- **Crucial addition**: Include a **`schema_version`** field. As your needs evolve, you write migration scripts to bump old nodes to new schemas, avoiding the "legacy mess".

**JSON template brainstorm:**
```json
{
  "schema_version": "1.0",
  "uuid": "unique-folder-hash",
  "calc_type": "vasp_relax | neb | md | single_point",
  "parent_uuid": "null_or_parent_scan_id",
  "input": {"xc": "PBE", "kpoints": [4,4,4], "formula": "TiN"},
  "output_summary": {"final_energy": -123.45, "bandgap": 0.0, "converged": true},
  "runtime_meta": {"host": "gpu01", "walltime": 3600, "exit_code": 0}
}
```

### 2. The "Perfect History" (Your Point 2)
Never trust the user to manually type the command into the JSON. 

- Write a **Python decorator** or **context manager** that wraps your `subprocess.run()`.
- When it executes, it captures `sys.argv`, `os.environ` (filtered for large paths), and the exact CLI string. 
- **Crucial hack**: Store the **Git hash** of your current code repository (if using git) and a **diff** of the input file. This is worth 10x more than the command itself. If you use `ase` or `pymatgen`, dump the `calc.get_incar()` and `calc.get_kpoints()` into a `raw_inputs/` subfolder and symlink them to the manifest.

### 3. The "Bubble Up" Strategy (Hierarchical Summaries)
Don't write custom scripts to parse every subfolder manually. Implement a **"Tree Reducer"**:

- At the root, run a script that walks the tree, reads every `manifest.json`, and applies a **user-defined aggregation dictionary** (e.g., `{"min_energy": min, "count": len}`).
- It writes this to a root `summary.json`. 
- Instead of overwriting the `README.md` (to preserve your manual notes), write a `README.generated.md` that contains markdown tables linking child UUIDs to their energies. This "bubbled" summary lets you instantly see if a NEB calculation has a barrier or just noise, without `cd`'ing.

### 4. Tiered Clean-up & Lossy Compression (Your Point 4)
This is your killer feature. Define a **"Value-to-Size Ratio" (VSR) taxonomy**:

- **Tier 0 (Gold)**: `final_energy`, `forces_on_ions` → Stored in JSON.
- **Tier 1 (Silver)**: `OUTCAR` / `vasprun.xml` (semi-structured, large).
- **Tier 2 (Bronze)**: `CHGCAR`, `WAVECAR` (huge, easily recomputed).
- **Tier 3 (Tin)**: `XDATCAR` (trajectories).

**The Pruning Protocol** (run manually or via cron):

1. **Dry-run**: The script scans all nodes and reports potential disk savings.
2. **Extract & Shred**: For Tier 3, use `pymatgen` or `ase.io` to parse the trajectory, save only the **energy vs. step** array into `compressed_trajectory.json` (size: 2KB), and *then* delete the `XDATCAR`.
3. **Move, don't delete (optional)**: Instead of `os.remove()`, move the big files to a separate `./archive_big_files/` symlinked directory. This preserves the folder structure via symlinks. If you need the raw data back, you can untar the archive.

**Implementation trick**: Store a `data_fingerprint` (SHA256 of the input POSCAR) in the manifest. If you delete `WAVECAR`, the manifest still cryptographically proves *which* structure generated it.

### Should you build or buy?

**Buy/Steal**: Use **ASE (Atomic Simulation Environment)** database (`ase.db`) as a **cache**, not the source of truth. Use `pymatgen` for parsing VASP/QE outputs—don't write parsers yourself.

**Build lightly**: Write just **3 CLI tools**:
- `crystalize init` -> Creates the folder with a strict JSON template.
- `crystalize run` -> Executes the job, updates the JSON with runtime args, and calculates the SHA256.
- `crystalize prune --keep-tier 1 --dry-run` -> Handles the lossy compression.

**The secret sauce**: Use **`pydantic`** for the JSON schema and **`rich`** for terminal tables. If the JSON fails validation, the script throws a loud, ugly error immediately—this forces the AI (or you) to conform to the protocol before wasting compute hours.

Start with just **5 manual runs** enforcing this schema. Refine the template. Once it feels frictionless, retroactively write a scraper to brute-force parse your old messy folders and convert them into this new structure. You don't need a server; you just need discipline enforced by Python exceptions.

---

# Kimi 2.6

This is a well-defined problem in computational materials science. The "AI generates jobs faster than I can organize them" bottleneck is real. Let me break this down into a concrete architecture you can iterate on.

## Philosophy: Local-First FAIR with Least Surprise

Your system should behave like a **filesystem-native database**: directories are records, JSON files are queryable metadata, and READMEs are human-readable views. The principle of least surprise means:
- A directory name tells you what calculation it is
- `README.md` always exists and always has the same sections
- `meta.json` always exists and always has the same schema
- Moving a directory never breaks internal references (use relative paths)

## 1. Directory & File Protocol

### Hierarchical Structure
```
project/
├── README.md                 # Project-level summary
├── meta.json                 # Project metadata (tags, description)
├── 01_bulk_optimization/
│   ├── README.md
│   ├── meta.json
│   ├── 01_vasp_pbe/
│   │   ├── README.md
│   │   ├── meta.json
│   │   ├── INCAR
│   │   ├── POSCAR
│   │   ├── KPOINTS
│   │   ├── POTCAR.spec
│   │   ├── run_vasp.py       # Your launcher script
│   │   ├── raw/              # Symlink or actual run directory
│   │   │   ├── OUTCAR
│   │   │   ├── WAVECAR
│   │   │   └── ...
│   │   └── extracted.json    # Small, precious extracted data
│   └── 02_vasp_hse/
│       └── ...
└── 02_surface_calculations/
    └── ...
```

### The `meta.json` Schema (Compulsory + Optional)

Every directory at every level must contain a `meta.json`. Use a strict JSON Schema to enforce this.

**Compulsory fields (every level):**
```json
{
  "schema_version": "1.0.0",
  "uuid": "auto-generated-uuid",
  "created": "2026-06-22T08:54:00Z",
  "name": "VASP PBE Bulk Optimization",
  "description": "Short human description",
  "level": "calculation",
  "status": "completed",
  "provenance": {
    "command": "python run_vasp.py --encut 520 --kpoints 8x8x8",
    "working_directory": "/absolute/path/at/runtime",
    "environment": {
      "vasp_version": "6.4.2",
      "python_version": "3.11.0",
      "git_commit": "a1b2c3d"
    },
    "input_files": {
      "INCAR": "md5:abc123...",
      "POSCAR": "md5:def456..."
    }
  }
}
```

**Level-dependent fields:**
- **Project level**: `tags`, `authors`, `publication_target`
- **Study level**: `parent_uuid`, `hypothesis`
- **Calculation level**: `code`, `exchange_correlation`, `ecut`, `kpoints`, `structure_uuid`, `extracted_data_ref`

**Key design decision:** The `provenance.command` field must be captured **automatically** by your launcher script, never typed by hand after the fact.

## 2. The Job Runner: Provenance as a Side Effect

Your Python launcher should be a **wrapper**, not just a submitter. It should:

1. **Generate the directory structure** before running
2. **Write `meta.json` and `README.md` skeletons** before execution
3. **Capture the exact command** via `sys.argv` and `subprocess`
4. **Hash input files** (for integrity checks later)
5. **Update status** (`running` → `completed`/`failed`)

### Minimal Launcher Template

```python
#!/usr/bin/env python3
# run_vasp.py
import sys, json, hashlib, uuid, datetime, subprocess, os, shutil
from pathlib import Path

def file_hash(filepath):
    return hashlib.md5(open(filepath, 'rb').read()).hexdigest()[:16]

def create_calculation_dir(base_dir, name, params):
    calc_dir = Path(base_dir) / name
    calc_dir.mkdir(parents=True, exist_ok=False)  # Fail if exists = least surprise
    
    # Write input files based on params (INCAR, POSCAR, etc.)
    # ...
    
    meta = {
        "schema_version": "1.0.0",
        "uuid": str(uuid.uuid4()),
        "created": datetime.datetime.now().isoformat(),
        "name": name,
        "level": "calculation",
        "status": "pending",
        "provenance": {
            "command": " ".join(sys.argv),
            "working_directory": str(Path.cwd().absolute()),
            "environment": {
                "vasp_version": get_vasp_version(),  # You implement this
                "git_commit": get_git_commit(),      # You implement this
            },
            "input_files": {
                f.name: f"md5:{file_hash(f)}" 
                for f in calc_dir.iterdir() 
                if f.is_file() and f.suffix in ['.json', '.md']
            }
        },
        "parameters": params,  # The actual scientific parameters
        "results": None
    }
    
    with open(calc_dir / "meta.json", 'w') as f:
        json.dump(meta, f, indent=2)
    
    # Write skeleton README
    readme = f"""# {name}

## Description
{params.get('description', 'TBD')}

## Status
Pending

## Parameters
```json
{json.dumps(params, indent=2)}
```

## Results
TBD
"""
    (calc_dir / "README.md").write_text(readme)
    
    return calc_dir

def run_job(calc_dir, vasp_cmd):
    # Update status
    update_meta(calc_dir, {"status": "running"})
    
    # Run VASP
    result = subprocess.run(vasp_cmd, cwd=calc_dir / "raw", capture_output=True)
    
    # Parse results and update
    if result.returncode == 0:
        extracted = parse_vasp_results(calc_dir / "raw")  # Your parser
        update_meta(calc_dir, {
            "status": "completed",
            "results": extracted
        })
        update_readme_results(calc_dir, extracted)
    else:
        update_meta(calc_dir, {"status": "failed", "error": result.stderr.decode()})
    
    return result.returncode
```

**Critical point:** The `meta.json` is written *before* execution. If the job fails, you still know exactly what was attempted.

---

## 3. Hierarchical Bubble-Up Summaries

You want information to "bubble up" so you can understand a project without opening every leaf directory.

### Automated README Generation

Create a CLI tool (call it `labjournal sync` or similar) that traverses the tree bottom-up:

```python
def bubble_up_summary(directory: Path):
    """Aggregate child meta.json files into parent README"""
    meta_path = directory / "meta.json"
    if not meta_path.exists():
        return
    
    meta = json.loads(meta_path.read_text())
    
    # If this is a leaf (calculation), just ensure README is consistent with meta.json
    if meta.get("level") == "calculation":
        sync_readme_from_meta(directory)
        return
    
    # If this is a branch, collect children
    children = []
    for subdir in directory.iterdir():
        if subdir.is_dir() and (subdir / "meta.json").exists():
            child_meta = json.loads((subdir / "meta.json").read_text())
            children.append({
                "name": subdir.name,
                "uuid": child_meta["uuid"],
                "status": child_meta["status"],
                "key_result": extract_key_result(child_meta)  # e.g., final energy
            })
    
    # Update parent README with table of children
    update_parent_readme(directory, children)
    update_parent_meta(directory, children)  # Aggregate stats
```

### Parent README Template

```markdown
# 01_bulk_optimization

## Summary
| Subdirectory | Status | Final Energy (eV) | UUID |
|-------------|--------|-------------------|------|
| 01_vasp_pbe | ✅ completed | -1234.56 | `uuid-here` |
| 02_vasp_hse | ⏳ running | — | `uuid-here` |

## Description
Optimizing bulk structure with different functionals.

## Child Studies
- [01_vasp_pbe](./01_vasp_pbe)
- [02_vasp_hse](./02_vasp_hse)
```

This gives you **navigability at a glance**. The `labjournal sync` command should be run after every batch of jobs completes.

## 4. Tiered Data Lifecycle & Pruning

This is the most sophisticated part. You need a **value-density-aware storage policy**.

### Define Data Tiers

For a typical VASP workflow:

| Tier | Data | Size | Value | Retention Policy |
|------|------|------|-------|------------------|
| **T0** | `extracted.json`, final `CONTCAR` | KB | **Critical** | Keep forever |
| **T1** | `OUTCAR` (full) | MB-GB | High (debug, restart) | Keep for 30 days |
| **T2** | `WAVECAR`, `CHGCAR` | GB | Medium (restart) | Delete after success |
| **T3** | Trajectory frames (if MD) | GB | Low (visualization) | Keep every Nth frame |
| **T4** | `PROCAR`, `DOSCAR` (if not needed) | MB | Low | Delete immediately |

### The Pruning Protocol

Implement this as a **declarative policy file** at project root:

```json
// prune_policy.json
{
  "default": {
    "T0": {"action": "keep", "location": "local"},
    "T1": {"action": "keep", "location": "local", "max_age_days": 30},
    "T2": {"action": "delete_after_verify", "verify": "extracted.json exists"},
    "T3": {"action": "compress", "tool": "gzip", "keep_original": false},
    "T4": {"action": "delete"}
  },
  "overrides": {
    "02_surface_calculations/*": {
      "T2": {"action": "keep"}  // Keep WAVECARs for surface work
    }
  }
}
```

### Pruning Operations

Your tool should support **lossy compression** operations specific to computational chemistry:

```python
def prune_calculation(calc_dir: Path, policy: dict):
    raw_dir = calc_dir / "raw"
    extracted = calc_dir / "extracted.json"
    
    if not extracted.exists():
        print(f"WARNING: No extracted data in {calc_dir}, skipping prune")
        return
    
    # 1. Extract and compress trajectory
    if policy["trajectory"] == "compress":
        outcar = raw_dir / "OUTCAR"
        if outcar.exists():
            frames = parse_trajectory(outcar)  # Your parser
            # Save sparse trajectory (every 10th frame + first + last)
            sparse = [frames[0]] + frames[::10] + [frames[-1]]
            with gzip.open(calc_dir / "trajectory_sparse.json.gz", 'wt') as f:
                json.dump(sparse, f)
    
    # 2. Extract NEB/scan energies
    if policy["neb"] == "extract_energies":
        # Parse OUTCAR for NEB images, write to extracted.json
        pass
    
    # 3. Safe deletion with verification
    if policy["wavecar"] == "delete":
        wavecar = raw_dir / "WAVECAR"
        if wavecar.exists():
            size_gb = wavecar.stat().st_size / 1e9
            wavecar.unlink()
            log_prune_action(calc_dir, "deleted WAVECAR", size_gb)
    
    # 4. Update meta.json to reflect pruning
    update_meta(calc_dir, {
        "pruned": True,
        "prune_date": datetime.now().isoformat(),
        "available_data": list_remaining_data(calc_dir)
    })
```

**Key principle:** Never delete anything until `extracted.json` is verified to contain the scientifically essential results. The `meta.json` should always truthfully report what data is actually present.

## 5. Off-the-Shelf vs. Custom: A Hybrid Recommendation

You mentioned uncertainty about build-vs-buy. Here's my assessment:

| Solution | Fit for Your Problem | Verdict |
|----------|---------------------|---------|
| **AiiDA** | Excellent provenance, but heavy, PostgreSQL required, steep learning curve | **Probably overkill** for personal local use |
| **ASE Database** | Lightweight SQLite, good for structures+energies, no hierarchy | **Use as library**, not as full solution |
| **NOMAD Oasis** | Can run locally, follows FAIR, but complex deployment | **Consider later** when you want to share/scale |
| **DVC + Git** | Good for versioning, bad for binary scientific data | **Partial fit** |
| **Custom (this proposal)** | Exactly your workflow, but requires maintenance | **Recommended for now** |

**My recommendation:** Build a **minimal custom system** (the protocol above) that is **JSON-schema driven**. You can later migrate to NOMAD Oasis or AiiDA by writing export adapters, because your data will already be structured and self-describing.

## 6. Implementation Roadmap

### Phase 1: The Protocol (Week 1)
1. Define your JSON Schema (use `pydantic` for validation)
2. Write the `run_vasp.py` wrapper template
3. Establish the directory naming convention

### Phase 2: Navigation (Week 2)
1. Build `labjournal sync` to auto-generate READMEs
2. Build `labjournal status` to show a tree view of running/completed jobs
3. Add a simple search: `labjournal find --energy-range -10,-5`

### Phase 3: Pruning (Week 3)
1. Write extractors for your most common job types (relaxation, NEB, MD)
2. Implement the `prune_policy.json` system
3. Add `labjournal prune --dry-run` and `--execute`

### Phase 4: AI Integration (Ongoing)
1. Modify your AI job generator to output directories following this protocol
2. Add a `meta.json` template generator to your AI prompt chain
3. The AI should never write raw files directly—only through the launcher

## 7. Concrete Example: NEB Calculation

Here's how a pruned NEB directory might look after Phase 3:

```
01_neb_diffusion/
├── README.md
├── meta.json
├── extracted.json          # T0: Barrier, energies, final structures
├── structures/
│   ├── initial.cif
│   ├── final.cif
│   └── transition_state.cif
├── raw/
│   └── OUTCAR              # T1: Kept for 30 days, then deleted
└── pruning.log
```

`extracted.json`:
```json
{
  "barrier_forward_eV": 0.82,
  "barrier_reverse_eV": 0.34,
  "max_force_ev_ang": 0.01,
  "n_images": 7,
  "image_energies_eV": [-100.0, -99.5, -99.2, -99.18, -99.5, -99.8, -99.9],
  "converged": true,
  "transition_state_image": 3
}
```

After pruning, `meta.json` is updated:
```json
{
  "pruned": true,
  "prune_date": "2026-06-22T10:00:00Z",
  "available_data": ["extracted.json", "structures/*.cif"],
  "deleted": ["WAVECAR", "CHGCAR", "PROCAR"]
}
```

## Open Questions for You

To refine this further:
1. **Which codes?** VASP only, or also QE, LAMMPS, Gaussian? (Each needs its own extractor.)
2. **How do you currently generate jobs with AI?** (Python script, LLM chat, specific framework?) This determines how to hook in the `meta.json` generation.
3. **Do you use Git for input files?** If so, the `git_commit` field in provenance becomes very powerful.
4. **What's your typical data volume?** (10 jobs? 10,000? This affects whether SQLite or JSON files are sufficient.)

Would you like me to elaborate on any of these sections, or start drafting the actual Python skeleton for the launcher + sync tool?

---

# Mistral

Your vision is **excellent**—you're identifying a very real pain point in computational science: *reproducibility at scale with AI-generated workflows*. The principles you've outlined (hierarchical structure, execution provenance, bubbling summaries, and value-based pruning) are solid. Let's break this down into a **concrete, implementable system** you can build incrementally.

## 🧠 **Core Philosophy: The "Lab Notebook" Metaphor**
Think of your system as a **digital lab notebook** where:
- Every "experiment" (calculation) is a self-contained entry
- The notebook is **hierarchical** (projects → subprojects → calculations)
- Each entry has **metadata** (JSON) + **narrative** (README.md)
- You can **zoom out** to see summaries at any level
- You can **prune** low-value data while preserving insights

## 🏗️ **Proposed System Architecture**

### **1. Directory Structure (Hierarchical)**
```
workspace/
├── project_1/                    # e.g., "Li-ion battery cathode"
│   ├── README.md                 # Project-level summary (auto-generated)
│   ├── meta.json                 # Project metadata
│   ├── subproject_a/             # e.g., "DFT relaxations"
│   │   ├── README.md             # Subproject summary
│   │   ├── meta.json
│   │   ├── job_001/              # Individual calculation
│   │   │   ├── README.md         # Human notes, observations
│   │   │   ├── meta.json         # Machine-readable metadata
│   │   │   ├── inputs/           # Input files (POSCAR, INCAR, etc.)
│   │   │   ├── outputs/          # Raw outputs (OUTCAR, vasprun.xml, etc.)
│   │   │   └── extracted/        # Pruned/extracted data (energies, geometries)
│   │   └── job_002/
│   │       └── ...
│   └── subproject_b/             # e.g., "NEB pathways"
│       └── ...
└── project_2/
    └── ...
```

### **2. The `meta.json` Template**
Every directory (project, subproject, job) has a `meta.json` with **compulsory** and **optional** fields:

```json
{
  // === Compulsory ===
  "id": "job_001",                          // Unique identifier
  "type": "dft_relaxation",                // Calculation type (enum)
  "timestamp": "2026-06-22T12:00:00Z",     // Creation time
  "parent": "../",                          // Parent directory (for hierarchy)
  "command": "mpirun -np 8 vasp_std",       // Exact command used
  "inputs": {                               // Input files (hashes + paths)
    "POSCAR": { "path": "inputs/POSCAR", "sha256": "abc123..." },
    "INCAR": { "path": "inputs/INCAR", "sha256": "def456..." }
  },
  "code": {                                 // Software provenance
    "name": "VASP",
    "version": "6.4.2",
    "settings": { "ENCUT": 500, "ISMEAR": 1 }  // Key parameters
  },

  // === Optional ===
  "description": "Relaxation of LiCoO2 structure",  // Human-readable
  "tags": ["dft", "relaxation", "licoo2"],         // For filtering
  "dependencies": ["job_000"],                     // Upstream jobs
  "status": "completed",                           // pending/running/failed/completed
  "duration_seconds": 3600,                       // Wall time
  "hardware": { "node": "gpu01", "gpus": 2 },      // Where it ran

  // === Extracted Results (auto-filled by scripts) ===
  "results": {
    "total_energy": -1234.567,              // eV
    "final_structure": "extracted/POSCAR",  // Path to pruned output
    "convergence": { "electronic": true, "ionic": true }
  },

  // === Data Value Classification ===
  "data_value": {
    "total_energy": { "size_bytes": 8, "value": "high", "prune": false },
    "final_structure": { "size_bytes": 512, "value": "high", "prune": false },
    "trajectory": { "size_bytes": 1024000, "value": "low", "prune": true },
    "wavecar": { "size_bytes": 50000000, "value": "none", "prune": true }
  }
}
```

### **3. Hierarchical README.md (Auto-Generated)**
Each `README.md` is **dynamically generated** from `meta.json` files below it. Example for `subproject_a/README.md`:

```markdown
# DFT Relaxations (subproject_a)
**Parent:** [../project_1](..)
**Last updated:** 2026-06-22T14:30:00Z
**Jobs:** 42 (38 completed, 2 running, 2 failed)

## Summary
- **Total energy range:** -1234.567 to -1230.123 eV
- **Average duration:** 1.2 hours
- **Success rate:** 90.5%

## Recent Jobs
| ID       | Type            | Energy (eV) | Status     | Duration  |
|----------|-----------------|--------------|------------|-----------|
| job_042  | dft_relaxation  | -1234.567    | completed  | 1h 15m    |
| job_041  | dft_relaxation  | -1233.890    | completed  | 58m       |
| job_040  | dft_static      | -1232.123    | failed     | 2m        |

## Key Files
- [All energies (CSV)](extracted/energies.csv)
- [Final structures (tar.gz)](extracted/structures.tar.gz)

*Generated by `labnotebook summarize`*
```

**Key feature:** The `README.md` at any level **aggregates** data from all child `meta.json` files. You can **drill down** or **zoom out** seamlessly.

### **4. Value-Based Pruning System**
Implement a **tiered storage** system with these rules:

| **Data Type**          | **Size**       | **Value** | **Action**                          | **Storage Class** |
|------------------------|---------------|-----------|-------------------------------------|-------------------|
| Total energy           | ~8 bytes      | Critical  | Keep forever                        | `core`            |
| Final structure        | ~512 bytes    | High      | Keep forever                        | `core`            |
| Forces/stresses        | ~1-10 KB      | Medium    | Keep for 1 year                      | `standard`        |
| Trajectory (XDATCAR)   | ~1-100 MB     | Low       | Extract key frames, then prune     | `archive`         |
| WAVECAR/CHGCAR         | ~100MB-10GB   | None      | Delete after extraction             | `ephemeral`       |
| OUTCAR                 | ~10-100 MB    | Medium    | Parse → extract → delete            | `standard`        |

**Implementation:**
```python
# Example pruning script
def prune_job(job_dir, mode="aggressive"):
    meta = load_json(f"{job_dir}/meta.json")

    if mode == "aggressive":
        # Delete all ephemeral data
        safe_delete(f"{job_dir}/outputs/WAVECAR")
        safe_delete(f"{job_dir}/outputs/CHGCAR")

        # Extract and compress trajectory
        extract_key_frames(f"{job_dir}/outputs/XDATCAR", f"{job_dir}/extracted/trajectory.xyz")

    elif mode == "moderate":
        # Keep WAVECAR for now, but move to slow storage
        move_to_archive(f"{job_dir}/outputs/WAVECAR")

    # Always keep core data
    ensure_exists(f"{job_dir}/extracted/results.json")
```

**Pruning Modes:**
- **`conservative`**: Keep everything, just organize
- **`moderate`**: Delete only the largest files (WAVECAR, CHGCAR)
- **`aggressive`**: Keep only `core` + `standard` data
- **`archive`**: Move low-value data to cold storage (external HDD, cloud archive)

### **5. Workflow Integration**
Your Python scripts should **automatically** generate `meta.json` and `README.md`:

```python
# Example: Running a VASP job
import json
import hashlib
from datetime import datetime

def run_vasp(poscar_path, incar_path, output_dir):
    # 1. Create job directory
    job_dir = f"jobs/job_{get_next_id()}"
    os.makedirs(f"{job_dir}/inputs", exist_ok=True)

    # 2. Copy inputs and hash them
    shutil.copy(poscar_path, f"{job_dir}/inputs/POSCAR")
    shutil.copy(incar_path, f"{job_dir}/inputs/INCAR")

    inputs = {
        "POSCAR": hash_file(f"{job_dir}/inputs/POSCAR"),
        "INCAR": hash_file(f"{job_dir}/inputs/INCAR")
    }

    # 3. Run the job
    command = "mpirun -np 8 vasp_std"
    subprocess.run(command, cwd=f"{job_dir}/inputs", shell=True)

    # 4. Generate meta.json
    meta = {
        "id": os.path.basename(job_dir),
        "type": "dft_relaxation",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "command": command,
        "inputs": inputs,
        "code": {"name": "VASP", "version": get_vasp_version()},
        "results": extract_results(f"{job_dir}/outputs"),  # Parse OUTCAR, etc.
        "data_value": classify_data(f"{job_dir}/outputs")
    }

    with open(f"{job_dir}/meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    # 5. Update parent README.md
    update_readme(os.path.dirname(job_dir))

    return job_dir
```

### **6. CLI Tools (Build These)**
Create a CLI to manage the system:

```bash
# Initialize a new project
labnotebook init project_1 --description "Li-ion cathode study"

# Run a job (auto-generates meta.json)
labnotebook run vasp --poscar POSCAR --incar INCAR --output job_001

# Summarize a directory (regenerate README.md)
labnotebook summarize project_1/subproject_a

# Prune data in a directory
labnotebook prune project_1 --mode aggressive

# Search for jobs by metadata
labnotebook search "type=dft_relaxation AND results.total_energy < -1000"

# Export a project (with pruning)
labnotebook export project_1 --prune-mode moderate --output project_1_archive.tar.gz
```

### **7. Off-the-Shelf vs. Custom: Decision Matrix**

| **Feature**               | **Custom System** | **NOMAD** | **Materials Project** | **AiiDA** | **FireWorks** |
|---------------------------|-------------------|-----------|----------------------|-----------|---------------|
| Local-only                | ✅ Yes            | ❌ No     | ❌ No                | ✅ Yes    | ✅ Yes        |
| Hierarchical structure    | ✅ Yes            | ⚠️ Partial | ⚠️ Partial          | ✅ Yes    | ✅ Yes        |
| Execution provenance      | ✅ Yes            | ✅ Yes    | ✅ Yes               | ✅ Yes    | ✅ Yes        |
| Value-based pruning       | ✅ Yes            | ❌ No     | ❌ No                | ❌ No     | ❌ No         |
| README.md summaries       | ✅ Yes            | ❌ No     | ❌ No                | ❌ No     | ❌ No         |
| Extensible schema         | ✅ Yes            | ⚠️ Limited| ⚠️ Limited          | ✅ Yes    | ✅ Yes        |
| Learning curve            | ⚠️ Medium         | ❌ High   | ❌ High              | ❌ High   | ❌ High       |

**Recommendation:**
- If you **only need provenance + search**, use **AiiDA** (but it’s complex).
- If you **want full control + simplicity**, **build your own** (your requirements are very specific).
- **Hybrid approach:** Use your system for **daily work**, and periodically **export** to NOMAD/Materials Project for sharing.

### **8. Incremental Implementation Plan**

| **Phase** | **Goal**                          | **Deliverables**                          | **Time Estimate** |
|-----------|-----------------------------------|------------------------------------------|-------------------|
| 1         | Core structure                    | Directory template, `meta.json` schema   | 1-2 days          |
| 2         | Auto-generation                   | Python scripts to create `meta.json`     | 2-3 days          |
| 3         | README.md aggregation             | Script to generate hierarchical READMEs  | 1-2 days          |
| 4         | Pruning system                    | `prune_job()` function, CLI               | 2-3 days          |
| 5         | Search & query                    | Simple grep/jq-based search               | 1 day             |
| 6         | Advanced features                 | Value-based auto-pruning, export/import   | 3-5 days          |

## 🎯 **Next Steps for You**
1. **Start small**: Implement the directory structure + `meta.json` for **one project** manually. See how it feels.
2. **Automate generation**: Modify **one** of your existing scripts to auto-generate `meta.json`.
3. **Test pruning**: Write a script to extract energies from an OUTCAR and delete the OUTCAR.
4. **Decide on CLI vs. Python API**: Do you prefer `labnotebook run vasp ...` or `from labnotebook import run_vasp`?
5. **Name your system**: Gives it identity (e.g., `chem-lab`, `mat-scribe`, `quantum-notebook`).

**Question for you:**
- Should we **dive deeper into the `meta.json` schema** (define all possible fields for your use case)?
- Or would you prefer a **starter Python package** with the basic structure (directory setup, meta.json generation, README aggregation)?
- Or do you want to **compare with AiiDA** in more detail to see if it can be adapted?

---

# Grok

**Great idea.** Managing the explosion of computational jobs (especially AI-generated ones) is a common pain point in comp chem/materials science. A personal, local "lab notebook + data lake" that enforces consistency while remaining flexible is very valuable.

I'll outline a practical, extensible system following your principles (least surprise, hierarchical, provenance-first, value-aware pruning). We can iterate on it.

### Core Philosophy
- **One canonical way to represent a "Job/Experiment"**: Every computation lives in its own directory with a fixed structure.
- **Provenance is sacred**: The JSON + run script must allow full reproduction (or at least understanding) months later.
- **Hierarchy for navigation & summarization**: Top-level folders aggregate summaries.
- **Value tiers**: Data has explicit "keep levels" so pruning is safe and scriptable.
- **AI-friendly**: Easy for LLMs to generate compliant jobs (templates + validators).

### Proposed Directory Structure (Hierarchical)
```
MyCompChemLab/
├── projects/
│   └── project_name/
│       ├── README.md                  # High-level project goals, links to key results
│       ├── metadata.json              # Project-level info
│       ├── calculations/              # Or "jobs/", "simulations/"
│       │   ├── 2026-06-22_relaxed_slab_Cu111_O2/   # Job dir, ISO date + descriptive name
│       │   │   ├── README.md          # Job-specific narrative
│       │   │   ├── job_metadata.json  # Core structured data (compulsory + optional)
│       │   │   ├── input/             # Input files (POSCAR, INCAR, etc.)
│       │   │   ├── output/            # Raw outputs, logs
│       │   │   ├── results/           # Extracted high-value data (energies, geometries, summaries)
│       │   │   ├── scripts/           # The exact runner script used
│       │   │   ├── provenance/        # Environment (software versions, git hash, etc.)
│       │   │   └── archives/          # Optional compressed raw data
│       │   └── ... (many more job dirs)
│       ├── summaries/                 # Auto-generated or curated overviews
│       └── figures/                   # Plots, etc.
├── templates/                         # Reusable job templates
├── tools/                             # Validation, pruning, summary scripts
└── archive/                           # Old projects or pruned data
```

**Naming convention** (least surprise): `YYYY-MM-DD_short_description_uniqueid` (e.g., add a short hash or counter). This makes `ls` and searches predictable.

### The job_metadata.json Template
This is the heart. Make it versioned (`"schema_version": "1.0"`).

**Compulsory fields**:
```json
{
  "schema_version": "1.0",
  "job_id": "2026-06-22_relaxed_slab_Cu111_O2",
  "project": "project_name",
  "timestamp_start": "2026-06-22T10:15:00Z",
  "timestamp_end": "2026-06-22T10:45:00Z",
  "software": {
    "package": "VASP",
    "version": "6.4.2",
    "calculator": "ase.Vasp"   // or pymatgen, etc.
  },
  "command": {
    "full_command": "python run_relax.py --poscar POSCAR --encut 520 ...",
    "script_path": "scripts/run_relax.py",
    "arguments": { ... },      // parsed args
    "environment": { "VASP_PP_PATH": "...", ... }
  },
  "input_summary": {
    "structure": { "formula": "Cu8O2", "natoms": 10, ... },
    "calculation_type": "relaxation",  // or "static", "neb", "md", "phonon", etc.
    "parameters": { "encut": 520, "kpoints": [6,6,1], ... }
  },
  "status": "completed",  // or failed, running, etc.
  "key_results": { ... }   // see below
}
```

**Key results** (high-value, small data — always extracted):
```json
"key_results": {
  "final_energy": -123.456,          // eV or whatever
  "energy_per_atom": -12.3456,
  "final_structure": { "poscar": "string or path", "xyz_path": "results/final.xyz" },
  "forces_max": 0.0012,
  "converged": true,
  "runtime_seconds": 1800,
  "extra_metrics": { ... }           // band gap, magnetic moment, etc. — calculation_type specific
}
```

Optional fields can be added freely (e.g., `notes`, `ai_prompt_used`, `references`, `tags`).

**How to generate it**: Your Python runner script (ASE, pymatgen, etc.) should dump this JSON at the end (or incrementally). Use `json` + `subprocess` to capture the exact command.

### Summarization & Bubbling Up
- Every job's `README.md` starts with a structured summary section (markdown table or YAML frontmatter).
- A `tools/summarize.py` script walks the hierarchy and generates/updates parent READMEs with tables like:

| Job | Type | Formula | Final E (eV) | Converged? | Link |
|-----|------|---------|--------------|------------|------|
| ... | ...  | ...     | ...          | Yes        | ...  |

This can be git-friendly and human-readable. For more power, generate a small SQLite or DuckDB index.

### Value-Aware Cleanup / Pruning
Define **tiers** in `job_metadata.json`:

```json
"data_tiers": {
  "tier1_essential": ["results/final.xyz", "job_metadata.json", "key_results summary"],
  "tier2_valuable": ["OUTCAR", "relaxation trajectory summary"],
  "tier3_bulk": ["WAVECAR", "CHGCAR", "full trajectory", "checkpoints"]
}
```

**Pruning scripts** (`tools/prune.py --level 2 --dry-run`):
- Tier 1: Never delete.
- Tier 2: Keep summaries/extracted data, compress or delete raw.
- Tier 3: Delete or move to `archives/` with `tar.zst` (very good compression).

For scans/NEB: Always extract energy/path images to `results/` before pruning.

This lets you keep "lossy compressed" versions that preserve scientific value.

### Tooling Recommendations
1. **Core scripts** (Python):
   - Job template generator.
   - Validator (`jsonschema` or pydantic).
   - Summarizer + hierarchy updater.
   - Pruner.
   - Search/indexer (e.g., `ripgrep` on JSONs + `sqlite`).

2. **Version control**: Git for metadata/scripts. Use `.gitignore` for large files. Consider `git-lfs` or `dvc` for big data pointers if needed (but keep simple initially).

3. **Off-the-shelf inspiration / partial solutions**:
   - **NOMAD/Materials Project** schemas (study their JSON schemas for calculations).
   - **AiiDA** (very powerful provenance, but heavier — good for inspiration).
   - **ASE** + custom database.
   - Simple: **Signac** or **Flow** frameworks (they have job management).
   - For local search: **Obsidian** vault on top of your folders + Dataview plugin for queries.

4. **AI integration**: Prompt your AI coder with the schema: "Generate a VASP relaxation script that outputs compliant job_metadata.json".

### Next Steps / Brainstorm Questions
- What packages do you use most (VASP, Quantum ESPRESSO, ASE, CP2K, ORCA, etc.)?
- How much data volume? (TB? Just GBs?)
- Do you want a lightweight GUI/web UI later (e.g., Streamlit or Gradio on top)?
- Should the system also track "derived" data (e.g., post-processing scripts that depend on multiple jobs)?
- Preference for database vs pure filesystem? (I lean filesystem-first for simplicity + portability.)

Would you like me to:
- Write the initial `job_metadata.json` schema (as JSON Schema)?
- Prototype some Python scripts (template generator, validator, pruner)?
- Sketch a sample runner script for ASE/VASP?
- Research specific existing tools/schemas?

Let's iterate — this can evolve into something you love using daily.

---

# Kimi 2.6 / devin / meta-analysis

# Meta-Analysis of [ChemBook.chat.md](cci:7://file:///home/prokophapala/git/CompChemUtils/doc/ChemBook.chat.md:0:0-0:0)

## Good Ideas (Consensus Winners)

- **Filesystem as source of truth**: Every LLM converged on this. It avoids lock-in, works with `grep`/`find`, and is version-control friendly.
- **Dual human/machine interface**: `README.md` for narrative + `meta.json` for structured queryable data. This is the core insight.
- **Provenance capture**: automatic command/environment/input hashing, not manual entry after the fact.
- **Tiered value-based pruning**: classifying data by value-per-GB and making deletion a recorded, reversible operation rather than silent cleanup.
- **Schema enforcement via Pydantic/JSON Schema**: fail loudly if AI-generated jobs don't conform, preventing the "different formats" problem.
- **Bubble-up summaries**: auto-generated aggregated views so you don't `cd` four levels deep to check convergence.

## Innovative & Interesting Highlights

| Idea | Source | Why it stands out |
|------|--------|-------------------|
| **"Extract & Kill" with provenance logging** | ChatGPT | Cleanup is recorded as provenance, not silent deletion. This prevents the "where did my WAVECAR go?" problem. |
| **Data fingerprint (SHA256 of inputs)** | DeepSeek | Even after deleting a 10 GB WAVECAR, the manifest cryptographically proves *which* structure generated it. |
| **Value-to-Size Ratio (VSR) taxonomy** | DeepSeek | Quantifies the intuition that `total_energy` is worth infinite $/GB while `WAVECAR` is near zero. |
| **Obsidian vault + Dataview** | Grok | Using a local markdown knowledge base as the search/query layer on top of the raw folders is genuinely creative and requires zero code. |
| **`chembook ingest` gate** | ChatGPT | AI can generate anything, but a normalization step enforces the protocol before acceptance. |
| **Declarative `prune_policy.json` with path overrides** | Kimi | A project-level policy file with wildcards (e.g., keep WAVECARs for surface work) makes pruning safe and configurable. |
| **Schema versioning with migrations** | DeepSeek | Acknowledges reality: the schema *will* evolve. Planning for migration avoids a legacy mess. |
| **`data_value` classification inside meta.json** | Mistral | Per-file metadata about whether something is `core`/`ephemeral` makes pruning scriptable at the file level. |

## Where LLMs Agree

- **AiiDA is overkill** for a personal local system. Everyone agrees.
- **Build custom, not buy**, at least for the core protocol. Signac is the closest off-the-shelf match.
- **Every directory is a "node"** with both `meta.json` and `README.md`.
- **Input files must be hashed/copied** before execution.
- **Pruning should be tiered** (T0/T1/T2 or L0-L4) with extraction before deletion.
- **The system should be AI-friendly** via templates and strict schemas.

## Where LLMs Disagree (Design Tensions)

### 1. Directory Topology
- **Gemini**: `systems/molecule_A/method_PBE/job_001/` — decouples system from method. Good for systematic comparisons, bad for deep nesting.
- **Kimi**: `project/01_bulk_optimization/01_vasp_pbe/` — study-first hierarchy.
- **Grok**: `projects/project_name/calculations/YYYY-MM-DD_name/` — flat, date-prefixed jobs under project.
- **ChatGPT**: `project/systems/` + `project/campaigns/` — separates systems from calculation campaigns.

### 2. Single vs. Multiple JSONs
- **Gemini**: splits into `job_record.json` (provenance) and `job_results.json` (science).
- **ChatGPT**: `meta.json` + `cleanup.json` + `index.json`.
- **Kimi/DeepSeek/Mistral/Grok**: single `meta.json` per node.

### 3. Index/Search Backend
- **ChatGPT/Grok**: SQLite or DuckDB as a fast searchable cache (filesystem remains truth).
- **Gemini/DeepSeek/Kimi/Mistral**: pure filesystem + `grep`/`jq`.

### 4. README Generation Strategy
- **Gemini**: Jinja2 templates rewriting sections between HTML comment markers.
- **ChatGPT**: auto-generated blocks inside `README.md` between `<!-- CHEMBOOK:SUMMARY:START/END -->`.
- **DeepSeek**: separate `README.generated.md` to avoid overwriting human notes.
- **Kimi**: `labjournal sync` regenerates READMEs bottom-up.

### 5. Pruning Levels Naming
Complete Babylon: T0-T4, L0-L4, Tier 1-4, core/standard/archive/ephemeral, gold/silver/bronze/tin. No consensus on semantics either (is L0 full or is L0 summary?).

## Open Design Questions Requiring Your Decision

1. **Hierarchy depth**: System/method/job (deep, systematic) vs. project/campaign/flat jobs (shallow, flexible)? How do you actually browse your data today?
2. **Single `meta.json` or split files?** A single file is simpler; splitting avoids rewriting large JSONs when only status changes.
3. **SQLite index or pure filesystem?** Do you need `chembook find "energy < -1234"` to be fast across 10k jobs?
4. **Job directory naming**: date-prefixed (`2026-06-22_name`) or sequential (`job_001`) or semantic (`relax_NaCl_PTCDA`)?
5. **How many codes?** VASP only, or also Fireball, ORCA, QE, LAMMPS? Each needs an extractor.
6. **AI integration**: Should the AI generate the *folder and meta.json*, or should a `chembook ingest` gate normalize after the fact?
7. **Derived data tracking**: Post-processing scripts that depend on multiple jobs (e.g., a PES scan plot from 20 relaxations) — how are these represented?
8. **GUI later?** Streamlit/Gradio web UI, or Obsidian, or pure CLI?
9. **Git strategy**: Git-track metadata+scripts, `.gitignore` raw outputs? Or use DVC?
10. **Schema strictness**: Fail loudly (script crashes) or warn and continue? Given your scientific computing background, I know the answer, but the AI wrappers need to handle this gracefully.

## My Recommendations

Based on your existing codebase (`CompChemUtils`), your scientific computing discipline (fail loudly, debuggability, minimal Python orchestration), and the requirement that AI must generate compliant jobs, here is what I would build:

### Architecture: "ChemBook" — Flat Project, Hierarchical Campaigns

```text
project_name/
├── meta.json
├── README.md
├── prune_policy.json
├── campaigns/
│   └── PTCDA_NaCl_relax_scan/
│       ├── meta.json
│       ├── README.md
│       ├── 000042_relax_site_A/
│       │   ├── meta.json
│       │   ├── README.md
│       │   ├── input/
│       │   ├── raw/
│       │   └── extracted/
│       └── 000081_relax_site_B/
└── systems/
    └── PTCDA_NaCl_100/
        ├── structure.xyz
        └── meta.json
```

**Why this topology**: It separates the canonical chemical system (in `systems/`) from the computational campaign (in `campaigns/`), but avoids the excessive nesting of `system/method/job`. You can browse campaigns by *what you were trying to do*, not by *what the molecule was*.

### Single `meta.json` Per Node

Use **Pydantic v2** for a single, versioned `meta.json`. Include `schema_version`, `uuid`, `provenance`, `system_ref` (UUID pointer), `method`, `results`, `data_tiers`, `pruning_log`, `parents[]`, `children[]`. One file is simpler and keeps everything atomically consistent.

### Filesystem-First, SQLite as Optional Cache

Don't build a database-first system. Use `ripgrep` + `jq` initially. Add a `chembook index` command that builds an SQLite cache from the filesystem for fast queries. The filesystem is the truth; SQLite is a disposable accelerator.

### Naming Convention

Use `NNN_short_description/` for jobs within a campaign (e.g., `042_relax_site_A`). The numeric prefix gives chronological order in `ls`. Use ISO dates for campaign directories if they span days.

### Pruning: Declarative Policy + Provenance Audit

Adopt Kimi's `prune_policy.json` at project root with path overrides. Adopt ChatGPT's cleanup logging: every deletion writes to `meta.json["pruning_log"]`. Support ChatGPT's L0-L4 levels (L0=full raw, L4=tombstone). Make `chembook prune --dry-run` mandatory before any destructive operation.

### README Strategy: Generated Blocks Inside README.md

Use ChatGPT's `<!-- CHEMBOOK:SUMMARY:START/END -->` marker approach. It preserves human narrative while allowing automated updates. One command: `chembook sync`.

### AI Integration: Template-Driven Generation

Provide the AI with a **Pydantic schema** and a `job_template.json` in its prompt context. The AI should generate the *inputs* and a `meta.json` skeleton, but `chembook run` (your wrapper) is the only thing that executes, captures provenance, and finalizes the metadata. The AI never writes raw files directly — only through the launcher.

### Schema Versioning

Follow DeepSeek's advice: include `"schema_version": "0.1.0"` in every `meta.json`. Write a `chembook migrate` command early. You *will* change the schema.

### Implementation Priority

1. **Week 1**: Pydantic schema + `meta.json` validation + `chembook init`.
2. **Week 2**: `chembook run` wrapper that captures `sys.argv`, git hash, input hashes, and writes `meta.json`.
3. **Week 3**: `chembook sync` to regenerate README summaries bottom-up.
4. **Week 4**: `chembook prune --dry-run` + extractors for your most common job types (relax, NEB, MD).
5. **Later**: `chembook find` with optional SQLite backend; export adapters for NOMAD/AiiDA if needed.

This keeps the system lightweight, fail-loud, debuggable, and AI-compatible — matching both your requirements and your existing coding philosophy.

---

# USER

Several things should be clarified

1) you can read about chemistry programs/software I'm using here@Prokop_Desktop_GTX3090.md @CompChem_software_quick_cheatsheet.md 
/home/prokophapala/git/CompChemUtils/py/interfaces

2) wer should distinguis two things 
a) fomat of the database, which should be quite permissive, and with only few compulasary fileld
b) tooling, which should be quite comprehensive, 
In general we should not enfroce to many requirements, and intrduce some junk file or vague unnecessary json field if they do not have clear purpose and utility, but we should provoide tools wirten in python which allow efficient navigation, quarry and datamining, book keeping, cleanup and reorganization of this data, the system should be quite flexibla and many things optional, but compulasary filed may singinficantly improve automatization and allow easy reorganization later 

3) we should distinguies two things 
a) hard rules which can be automatized (deterministic algorithms in python)
b) soft quidelines recomanding AI how it should so it like SKILL.md, and templated of README.md, the readme.md is not machine processable, and it is nor compulsary, it it recomanded that AI write README.md according to guuidelines based on the results, but machine generated files (by determinsitc algorothm not by AI) should be the json

4) I do not enforce given directroy structure and hierarchy, it should be flexible, but it is true that often it is usefull if method and system is in the folder name or if it is nested, this depends case by case and we should be handle both 

5) for some jobs we will have specific datafiles/format - for example relaxed scans, or other energy scans may be producing .xyz and data table e.g. distance, angle, energy, as ascii or .csv (human readable) or binary npy/npz, we should distinguish human readable format and fast binary format (prefereble npy/npz), and interconvert between them automatically. We do not need to have all. Also I found interactive plots in .tml using p5.js are quite sefull often to compare lot of different plots. These overview plots are very importaint for fast navigation. Here maybe some gui/explored can be usefull.

Other
- yes, ommit SQL, we can do later, GUI is also not relevant now
- I would perhsp prefer to have isnlge json, but we should specify what is compulsary - I would prefer not too many, also we should review exsiting codes/software so see what files and ouptu they can produce so our format is prepared for it. Discussion of json template we have to do in details, do not overcomplicate it, just usefull fields no fluf or samoucelna buzerace a formalism


---

# Kimi 2.6 / devin 





# Revised ChemBook Design

Based on your clarifications and the software you actually use (`doc/EVIROMENTS_AND_MACHINES/Prokop_Desktop_GTX3090.md:1-472`, `doc/CompChem_software_quick_cheatsheet.md:1-500`, `py/interfaces/_base.py:1-103`), here is a tightened proposal.

## 1. Core Principle: Minimal Format, Rich Tools

- **The format (`chembook.json`) is permissive.** Few compulsory fields. No junk metadata.
- **The tooling is deterministic Python.** It navigates, extracts, mines, reorganizes, cleans up, and plots — but it does not *require* a specific folder layout.
- **No SQL, no GUI now.** Filesystem is the database; CLI is the interface. Static HTML plots with p5.js are fine because they are just files.

## 2. Hard Rules vs. Soft Guidelines

| Hard rules (Python enforces) | Soft guidelines (AI follows via `SKILL.md`/templates) |
|------------------------------|----------------------------------------------------------|
| A node directory must contain `chembook.json` with compulsory fields. | `README.md` is recommended but not required. |
| `chembook.uuid` must be unique within a project. | Directory naming convention (`NNN_description` or `YYYY-MM-DD_description`). |
| `chembook.status` must be one of `pending/running/failed/done/pruned`. | Suggested directory layouts (`systems/`, `campaigns/`, `archive/`). |
| Parent links must resolve if present. | How to write human-readable `README.md` sections. |
| `csv` ↔ `npz` pairs must be kept consistent by `chembook convert`. | What optional metadata to add for a scan/NEB/phonon job. |
| Pruning is logged in `chembook.json["pruning_log"]`. | When to keep WAVECAR/CHGCAR vs. delete them. |

## 3. The Single `chembook.json` Schema

Only the **bold** fields are compulsory. Everything else is optional.

```json
{
  "chembook": {
    "schema_version": "0.1.0",
    "uuid": "uuid4",
    "created": "2026-06-22T22:00:00Z",
    "status": "done",
    "parent": "../relax_scan",
    "level": "job"
  },
  "provenance": {
    "command": "python run.py --input H2O.xyz --method PBE",
    "workdir": "/home/prokop/SIMULATIONS/ase/project_X",
    "hostname": "luna",
    "started": "2026-06-22T22:00:00Z",
    "finished": "2026-06-22T22:10:00Z",
    "exit_code": 0,
    "git_commit": "abc123"
  },
  "system": {
    "name": "water molecule",
    "formula": "H2O",
    "charge": 0,
    "spin": 1,
    "pbc": [false, false, false],
    "initial_structure": "input/H2O.xyz",
    "final_structure": "output/H2O_opt.xyz"
  },
  "method": {
    "code": "dftb+",
    "code_version": "24.1",
    "level": "SCC-DFTB",
    "basis": "3ob-3-1",
    "dispersion": "D3"
  },
  "results": {
    "energy": {"value": -1234.5, "unit": "eV"},
    "converged": true,
    "max_force": {"value": 0.01, "unit": "eV/Angstrom"}
  },
  "files": {
    "input": ["input/dftb_in.hsd", "input/geo.gen"],
    "output": ["output/detailed.out", "output/results.tag"],
    "extracted": ["extracted/energy.csv", "extracted/final.xyz"]
  },
  "tags": ["relaxation", "dftb", "test"],
  "notes": "human-readable note"
}
```

**Compulsory only:** `chembook.schema_version`, `chembook.uuid`, `chembook.created`, `chembook.status`, `provenance.command`, and one of `system.formula` or `system.name`.

This is enough for indexing, search, and reorganization. Everything else is bonus.

## 4. Directory Structure Is Optional

A directory becomes a **node** only by containing `chembook.json`. Otherwise it is just a folder. You can nest, flatten, or mix layouts as needed.

**Default convention (not enforced):**

```text
project/
├── chembook.json
├── README.md
├── systems/
│   └── H2O/
│       ├── chembook.json
│       └── structure.xyz
└── campaigns/
    └── relax_scan/
        ├── chembook.json
        ├── README.md
        ├── 001_H2O_PBE/
        │   ├── chembook.json
        │   ├── README.md
        │   ├── input/
        │   ├── output/
        │   └── extracted/
        └── 002_H2O_B3LYP/
            └── ...
```

**Alternative valid layouts:**

- Flat jobs: `project/001_relax_H2O_PBE/`
- Method-first: `project/PBE/H2O/job_001/`
- System-first: `project/H2O/PBE/job_001/`

The tool discovers nodes by walking and reading `chembook.json`, not by expecting a fixed path.

## 5. Scan, Trajectory, and Plot Data

For relaxed scans, NEB, PES scans, etc., store **paired human-readable + binary formats** plus an optional interactive plot.

```text
extracted/
├── scan.csv          # human-readable ASCII table
├── scan.npz          # binary NumPy arrays (fast load)
├── trajectory.xyz    # geometries
├── plot.html         # p5.js interactive overview
└── plot.json         # data snapshot for p5.js
```

Example `scan.csv`:

```csv
step, distance_A, angle_deg, energy_eV, max_force_eVA
0, 0.900, 104.50, -1234.50, 0.45
1, 0.925, 104.50, -1235.10, 0.12
...
```

**Tooling:**

- `chembook convert extracted/scan.csv` → creates/updates `scan.npz`
- `chembook convert extracted/scan.npz` → creates/updates `scan.csv`
- `chembook plot extracted/scan.csv --x distance_A --y energy_eV` → generates `plot.html`
- `chembook plot` scans all nodes with `extracted/*.csv` and rebuilds overview plots

The p5.js HTML is static — no server required. It is just another file in the project.

## 6. Software Coverage: Extractor Plugins

From your setup, the codes you actually run are:

| Code | Typical input files | Typical output files | Extractor priority |
|------|---------------------|----------------------|-------------------|
| **DFTB+** | `dftb_in.hsd`, `geo.gen` | `results.tag`, `detailed.out`, `band.out`, `hessian.out` | High |
| **Psi4** | `*.in` or Python | `output.dat`, `timer.dat`, `*.xyz` | High |
| **xtb** | `*.xyz` | `xtb.out`, `xtbopt.xyz`, `*.charges`, `*.wbo` | High |
| **ORCA** | `*.inp` | `*.out`, `*.gbw`, `*.hess`, `*.xyz` | High |
| **pySCF** | Python script | stdout, `.chk`, `.molden` | High |
| **GPAW** | Python script | `.gpw`, `.txt`, `.cube` | Medium |
| **CP2K** | `*.inp` | `*.out`, `*.restart`, `*.xyz` | Medium |
| **LAMMPS** | `in.*`, data files | `log.lammps`, `dump.*` | Medium |
| **MOPAC** | `*.mop` | `*.out`, `*.arc`, `*.aux` | Low |
| **QUICK** | `*.inp` | `*.out` | Low |
| **ALAMODE** | `*.in` | phonon bands, DOS | Low |

The extractor is chosen by `method.code`. A missing extractor is not a hard failure — the job just stays in `status: "done"` with empty `results`.

## 7. Proposed CLI Tooling

```text
chembook init <project_dir>              # create chembook.json + README skeleton
chembook run <command...>              # run command, capture provenance, write chembook.json
chembook extract <code> <dir>            # parse outputs, write results + extracted files
chembook sync <dir>                      # regenerate README.md summaries bottom-up
chembook find <query>                    # grep/jq over chembook.json files
chembook convert <file.csv|file.npz>     # keep csv/npz pair consistent
chembook plot <file.csv> [options]       # generate p5.js plot.html
chembook prune --dry-run <dir>           # preview cleanup
chembook prune --level <relaxed|minimal> <dir>  # execute cleanup with logging
chembook migrate                         # bump old chembook.json to new schema_version
```

## 8. Remaining Design Decisions

1. **Field name for the JSON file**: `chembook.json` or `meta.json`? `chembook.json` is explicit and searchable, but `meta.json` is more generic.
2. **Job naming**: sequential `001_` prefix, date `2026-06-22_`, or freeform?
3. **Result energy key**: `results.energy` with a `unit` subfield, or `results.energy_eV` flat? I recommend `results.energy.value + .unit` for generality.
4. **Pruning level names**: `core/valuable/bulk` or `L0-L4`? I recommend simple names, not numbered tiers.
5. **Should `chembook.json` be written before or after the run?** I recommend writing a skeleton with `status: pending` before execution, then updating to `done/failed` after. This captures failed attempts.

If you approve this direction, the next step is to draft the `SKILL.md` for the AI and a minimal Python skeleton for `chembook.json` validation + `chembook run` + `chembook extract`.

---

# USER

few things
1) we should insist to measure time of calculation, but quite precisely (fraction o second) we often run fast jobs (especially localyy), and optimization of speed is importnant for us
2) udid is generated how? how we ensure it is unique? maybe we should use some random-hash like on github
3) what means git_commit ? I do not plan push data to git
4) what is good "parent:../relax_scan" seems redudant to me, what is "level:job" ? But what we sould definitely add is task/job types (relaxed scan, AFM,STM, fukui, single point etc tasks, read what is inside those file are here /home/prokophapala/git/CompChemUtils/py/tasks )
5) for performance bechmarking we should aslo mention number of atoms of each element (like summary formula), code and method, job type, number of atoms should be compulsory
6) not sure what is schema good for, but perhaps good for rigor

ad 'Directory naming convention (NNN_description or YYYY-MM-DD_description).'
our tools should hanlde any names or hierarchy, but we should suggest some suitable, definitely date is not usefull in name, 
perhaps ti should by by system, then method, then basis, not sure if first should be name of system or type-of-job, purpose or something like that. This is guideline not hard rule, ubut consistent naming policy is important yet not settled not obvious

---

# Kimi 2.6 devin

You are right on all points. Here are my answers and the revised design decisions.

## 1. Timing precision
Use `time.perf_counter_ns()` (or `time.perf_counter()`), which gives sub-microsecond precision. Store `duration_seconds` as a float.

```json
"provenance": {
  "started": "2026-06-22T22:00:00.123456Z",
  "finished": "2026-06-22T22:00:01.234567Z",
  "duration_seconds": 1.111111
}
```

## 2. UUID generation
Generate a random 8-character hex/digits (à la GitHub short SHA) at creation. The tool checks against all existing `chembook.json` files in the project on write and fails loudly if a collision is found. For extra robustness, include a few characters from the SHA-1 of the creation time + workdir + random bytes.

**Compulsory fields are now**:
- `chembook.schema_version`
- `chembook.uuid`
- `chembook.created`
- `chembook.status`
- `provenance.command`
- `provenance.duration_seconds`
- one of `system.formula` or `system.name`
- `system.elements` (atom count per element, for performance benchmarking)

## 3. git_commit
Drop `git_commit` as compulsory. Make it optional under `provenance`. If a repo is present, the tool can auto-fill it; if not, it is omitted.

## 4. parent/level, task/job type
You are right. Drop `parent` and `level`. Add `job.type` as the key field, read from your existing tasks in `py/tasks/scan.py:1`, `py/tasks/relax.py:1`, `py/tasks/interaction_energy.py:1` and `py/interfaces/_base.py:12-75`.

Allowed `job.type` values:
- `single_point`
- [relax](cci:1://file:///home/prokophapala/git/CompChemUtils/py/tasks/relax.py:12:0-36:89)
- [rigid_scan](cci:1://file:///home/prokophapala/git/CompChemUtils/py/tasks/scan.py:102:0-133:64)
- [relaxed_scan](cci:1://file:///home/prokophapala/git/CompChemUtils/py/tasks/scan.py:136:0-206:109)
- `vibrations`
- `phonons`
- `density`
- `esp`
- `fukui`
- `resp`
- [interaction_energy](cci:1://file:///home/prokophapala/git/CompChemUtils/py/tasks/interaction_energy.py:41:0-151:102)
- `neb`
- `afm`
- `stm`
- `md`

## 5. Performance benchmarking
Add a compulsory `system.elements` field:

```json
"system": {
  "formula": "H2O",
  "elements": {"H": 2, "O": 1},
  "n_atoms": 3
}
```

This makes it trivial to query time per atom, time per element, code scaling, etc.

## 6. Schema
The schema is useful for validation and rigor, but not for over-engineering. Use Pydantic for fast validation. Keep it minimal and versioned (`schema_version`).

## Revised minimal `chembook.json`

```json
{
  "chembook": {
    "schema_version": "0.1.0",
    "uuid": "a1b2c3d4",
    "created": "2026-06-22T22:00:00.123456Z",
    "status": "done"
  },
  "job": {
    "type": "relaxed_scan",
    "name": "H2O_dftb3_scan"
  },
  "provenance": {
    "command": "python run.py --input H2O.xyz --method PBE",
    "hostname": "luna",
    "started": "2026-06-22T22:00:00.123456Z",
    "finished": "2026-06-22T22:00:01.234567Z",
    "duration_seconds": 1.234567,
    "exit_code": 0,
    "git_commit": "abc123"
  },
  "system": {
    "name": "water molecule",
    "formula": "H2O",
    "elements": {"H": 2, "O": 1},
    "n_atoms": 3,
    "charge": 0,
    "spin": 1,
    "pbc": [false, false, false]
  },
  "method": {
    "code": "dftb+",
    "code_version": "24.1",
    "level": "SCC-DFTB",
    "basis": "3ob-3-1",
    "dispersion": "D3"
  },
  "results": {
    "energy": {"value": -1234.5, "unit": "eV"},
    "converged": true
  },
  "files": {
    "input": ["input/dftb_in.hsd"],
    "output": ["output/detailed.out"],
    "extracted": ["extracted/scan.csv", "extracted/scan.npz"]
  },
  "tags": ["relaxation", "dftb", "test"],
  "notes": "human-readable note"
}
```

## Directory naming
No date in the name. Keep it flexible but suggest these soft patterns:

```text
project/
├── systems/H2O/
├── H2O/
│   ├── DFTB3/
│   │   ├── relax/
│   │   └── scan/
│   └── PBE/
└── campaigns/
    └── H2O_dftb3_scan/
```

The rule is: **tools discover by `chembook.json`, not by path**. The README/AI guideline can recommend `system/method/basis/job_type` or `system/job_type/method/basis`, but the tool must handle any name.

Do you want me to:
1. Apply these revised decisions to [doc/ChemBook.chat.md](cci:7://file:///home/prokophapala/git/CompChemUtils/doc/ChemBook.chat.md:0:0-0:0),
2. Draft `doc/ChemBook/SKILL.md` for the AI,
3. Create a minimal Python skeleton (`py/chembook/`) with validation, `chembook run`, and `chembook extract`?

Also, I noticed that `py/tasks/scan.py:21`, `py/tasks/relax.py:10`, and `py/interfaces/pyscf.py:11` import from `py/tasks/base.py`, but that file does not exist. Should I create it as part of the skeleton, or is it elsewhere?

---

# Gemini

This is shaping up into a highly pragmatic, low-overhead system. Dropping the forced directory hierarchy in favor of a flexible, node-based discovery system (where `chembook.json` acts as the anchor) is exactly the right move. It prevents "samoucelna buzerace" (pointless bureaucracy) while giving you the exact hooks needed to query and prune data.

Let's drill down into the specific mechanics of the protocol and the Python tooling, particularly how to implement this efficiently within your existing `CompChemUtils` repository.

### 1. The Protocol: UUIDs and Pydantic Rigor

**Generating Unique IDs locally:**
You don't need a central server or database to ensure uniqueness. We can use a deterministic hash combined with entropy.
When `chembook run` or `chembook init` is called, it generates an 8-character hex string.

```python
import time
import os
import hashlib

def generate_short_uuid():
    # Combines nanosecond timestamp, current directory path, and random bytes
    raw_str = f"{time.time_ns()}_{os.getcwd()}_{os.urandom(4)}"
    return hashlib.sha256(raw_str.encode('utf-8')).hexdigest()[:8]

```

*Why this works:* It mimics the GitHub short SHA. If the tool detects a collision (by checking existing `chembook.json` files in the current project tree), it just rolls again.

**Enforcing the Schema (The Rigor):**
To keep the `chembook.json` schema rigorous but flexible, use **Pydantic**. Pydantic will enforce the compulsory fields (job type, element counts, exact timings) and ignore or optionally accept the rest.

```python
from pydantic import BaseModel, Field
from typing import Dict, Optional, List

class SystemMeta(BaseModel):
    n_atoms: int = Field(..., description="Total number of atoms")
    elements: Dict[str, int] = Field(..., description="E.g., {'C': 6, 'H': 6}")
    formula: Optional[str] = None

class ProvenanceMeta(BaseModel):
    command: str
    duration_seconds: float = Field(..., description="High precision timing from perf_counter")
    hostname: str
    # git_commit omitted as requested, or left purely optional

class ChemBookNode(BaseModel):
    schema_version: str = "0.1.0"
    uuid: str = Field(default_factory=generate_short_uuid)
    status: str
    job_type: str # 'relaxed_scan', 'afm', 'stm', 'fukui', etc.
    system: SystemMeta
    provenance: ProvenanceMeta
    results: Dict = Field(default_factory=dict)

```

### 2. The Tooling: Transparent Wrapping

Because you are optimizing for speed—especially running fast jobs locally on your GTX 3090—the `chembook` tool must add virtually zero overhead.

The most important command will be `chembook run`. It should act as a transparent wrapper around whatever script you are executing, injecting the timing and provenance tracking automatically.

**Workflow for `chembook run`:**
If your normal command is: `python py/tasks/relax.py config.json`
You run: `chembook run --type relax -- python py/tasks/relax.py config.json`

Behind the scenes, the Python CLI does this:

1. Records `start_time = time.perf_counter_ns()`.
2. Uses `subprocess.run()` to execute the rest of the arguments.
3. Records `end_time = time.perf_counter_ns()`.
4. Calculates precise duration.
5. Dumps the compulsory fields into a `chembook.json` in that directory.

### 3. File Formats & The Missing `base.py`

You noted that `.npz` and `.csv` pairs are essential for fast loading vs. human readability, and that overview plots (p5.js HTML) are critical for navigation.

To standardize this across all your tasks (scans, relaxations, etc.), we should address the missing `py/tasks/base.py` mentioned in your notes. This file should define an abstract `Task` class that automatically handles the `.csv` <-> `.npz` conversion.

```python
# py/tasks/base.py (Proposed Skeleton)
import numpy as np
import pandas as pd

class BaseTask:
    def __init__(self, workdir="."):
        self.workdir = workdir

    def run(self):
        raise NotImplementedError
        
    def extract_to_csv(self):
        raise NotImplementedError

    def csv_to_npz(self, csv_path, npz_path):
        """Standardized fast binary conversion"""
        df = pd.read_csv(csv_path)
        np.savez_compressed(npz_path, **{col: df[col].values for col in df.columns})

```

### 4. Directory Naming Guidelines (Soft Rules)

Since the Python tools will traverse the tree searching for `chembook.json` files, the directory names literally do not matter to the machine.

For the AI (`SKILL.md`), we should recommend a layout that groups by the physical system first, as the system is usually the most immutable part of a study, while methods and basis sets are variables being tested:

`project_root / {system_formula_or_name} / {job_type} / {method}_{basis} /`
*Example:* `project / C60 / relaxed_scan / pbe_def2-svp /`

To get this off the ground, where should we focus the actual coding effort first: Should we draft the `py/chembook/cli.py` to get the transparent `chembook run` wrapper working, or do you want to flesh out that missing `py/tasks/base.py` to ensure the task parsers behave correctly?


---

# Gemini

This is shaping up into a highly pragmatic, low-overhead system. Dropping the forced directory hierarchy in favor of a flexible, node-based discovery system (where `chembook.json` acts as the anchor) is exactly the right move. It prevents "samoucelna buzerace" (pointless bureaucracy) while giving you the exact hooks needed to query and prune data.

Let's drill down into the specific mechanics of the protocol and the Python tooling, particularly how to implement this efficiently within your existing `CompChemUtils` repository.

### 1. The Protocol: UUIDs and Pydantic Rigor

**Generating Unique IDs locally:**
You don't need a central server or database to ensure uniqueness. We can use a deterministic hash combined with entropy.
When `chembook run` or `chembook init` is called, it generates an 8-character hex string.

```python
import time
import os
import hashlib

def generate_short_uuid():
    # Combines nanosecond timestamp, current directory path, and random bytes
    raw_str = f"{time.time_ns()}_{os.getcwd()}_{os.urandom(4)}"
    return hashlib.sha256(raw_str.encode('utf-8')).hexdigest()[:8]

```

*Why this works:* It mimics the GitHub short SHA. If the tool detects a collision (by checking existing `chembook.json` files in the current project tree), it just rolls again.

**Enforcing the Schema (The Rigor):**
To keep the `chembook.json` schema rigorous but flexible, use **Pydantic**. Pydantic will enforce the compulsory fields (job type, element counts, exact timings) and ignore or optionally accept the rest.

```python
from pydantic import BaseModel, Field
from typing import Dict, Optional, List

class SystemMeta(BaseModel):
    n_atoms: int = Field(..., description="Total number of atoms")
    elements: Dict[str, int] = Field(..., description="E.g., {'C': 6, 'H': 6}")
    formula: Optional[str] = None

class ProvenanceMeta(BaseModel):
    command: str
    duration_seconds: float = Field(..., description="High precision timing from perf_counter")
    hostname: str
    # git_commit omitted as requested, or left purely optional

class ChemBookNode(BaseModel):
    schema_version: str = "0.1.0"
    uuid: str = Field(default_factory=generate_short_uuid)
    status: str
    job_type: str # 'relaxed_scan', 'afm', 'stm', 'fukui', etc.
    system: SystemMeta
    provenance: ProvenanceMeta
    results: Dict = Field(default_factory=dict)

```

### 2. The Tooling: Transparent Wrapping

Because you are optimizing for speed—especially running fast jobs locally on your GTX 3090—the `chembook` tool must add virtually zero overhead.

The most important command will be `chembook run`. It should act as a transparent wrapper around whatever script you are executing, injecting the timing and provenance tracking automatically.

**Workflow for `chembook run`:**
If your normal command is: `python py/tasks/relax.py config.json`
You run: `chembook run --type relax -- python py/tasks/relax.py config.json`

Behind the scenes, the Python CLI does this:

1. Records `start_time = time.perf_counter_ns()`.
2. Uses `subprocess.run()` to execute the rest of the arguments.
3. Records `end_time = time.perf_counter_ns()`.
4. Calculates precise duration.
5. Dumps the compulsory fields into a `chembook.json` in that directory.

### 3. File Formats & The Missing `base.py`

You noted that `.npz` and `.csv` pairs are essential for fast loading vs. human readability, and that overview plots (p5.js HTML) are critical for navigation.

To standardize this across all your tasks (scans, relaxations, etc.), we should address the missing `py/tasks/base.py` mentioned in your notes. This file should define an abstract `Task` class that automatically handles the `.csv` <-> `.npz` conversion.

```python
# py/tasks/base.py (Proposed Skeleton)
import numpy as np
import pandas as pd

class BaseTask:
    def __init__(self, workdir="."):
        self.workdir = workdir

    def run(self):
        raise NotImplementedError
        
    def extract_to_csv(self):
        raise NotImplementedError

    def csv_to_npz(self, csv_path, npz_path):
        """Standardized fast binary conversion"""
        df = pd.read_csv(csv_path)
        np.savez_compressed(npz_path, **{col: df[col].values for col in df.columns})

```

### 4. Directory Naming Guidelines (Soft Rules)

Since the Python tools will traverse the tree searching for `chembook.json` files, the directory names literally do not matter to the machine.

For the AI (`SKILL.md`), we should recommend a layout that groups by the physical system first, as the system is usually the most immutable part of a study, while methods and basis sets are variables being tested:

`project_root / {system_formula_or_name} / {job_type} / {method}_{basis} /`
*Example:* `project / C60 / relaxed_scan / pbe_def2-svp /`

To get this off the ground, where should we focus the actual coding effort first: Should we draft the `py/chembook/cli.py` to get the transparent `chembook run` wrapper working, or do you want to flesh out that missing `py/tasks/base.py` to ensure the task parsers behave correctly?

---

# Chat GPT 5.5

Yes — the important correction is: **ChemBook should not be a strict “database format”; it should be a tolerant local scientific ledger.** The strictness belongs mostly in tooling, not in the data format. Your notes explicitly separate permissive `chembook.json`, deterministic Python tooling, optional `README.md`, flexible hierarchy, CSV/NPZ conversion, static p5.js plots, cleanup/pruning, timing precision, UUID design, and compulsory benchmarking fields such as atom counts, code, method, and job type. 

Below is a more specific design.

# 1. Design philosophy

## Main rule

A directory becomes a ChemBook node only if it contains:

```text
chembook.json
```

Everything else is optional.

There is no mandatory global hierarchy. The tool walks the filesystem, finds all `chembook.json` files, validates the few hard fields, and builds navigation/search/summary from those files.

So these are all valid:

```text
H2O/DFTB3/relax/
DFTB3/H2O/relax/
campaigns/water_scan/001/
random_tests/old_job_17/
```

The path is useful but not trusted. The JSON is trusted more than the path.

## Two-layer system

### Layer A: protocol

Minimal, permissive, stable.

It answers:

```text
What is this?
What system?
What method/code?
What task type?
How was it run?
How long did it take?
Where are the useful files?
What are the key results?
What was deleted/pruned?
```

### Layer B: tooling

Comprehensive, deterministic Python.

It does:

```text
discover
validate
extract
summarize
query
convert csv<->npz
plot static html
benchmark
cleanup/prune
reorganize/copy
compare jobs
```

The protocol should be boring and small. The tooling can be rich.

# 2. Hard rules vs soft AI guidelines

This distinction is essential.

## Hard rules: deterministic Python

These can be validated automatically.

```text
1. If chembook.json exists, it must be valid JSON.
2. It must contain a small required core.
3. status must be from a known list.
4. job.type must be from a known or at least recognized vocabulary.
5. system.n_atoms and system.elements must be consistent if both exist.
6. duration_sec must be numeric if the job has run.
7. files listed in files.keep / files.input / files.output / files.extracted should exist, unless marked missing.
8. cleanup actions must be logged.
9. UUID collision inside one project is an error.
10. csv/npz pairs generated by ChemBook must include enough metadata to check consistency.
```

## Soft rules: `SKILL.md`, templates, README style

These guide AI and humans but are not enforced.

```text
1. Write a useful README.md.
2. Use meaningful directory names.
3. Prefer system/method/task nesting for large campaigns.
4. Prefer task/system/method for task-focused benchmarking.
5. Keep extracted/ clean and human-readable.
6. Generate overview plots for scans and image stacks.
7. Explain failed jobs in README.md when possible.
8. Do not invent metadata fields unless they are useful.
```

The AI may write `README.md`; deterministic Python writes `chembook.json`.

That is a very good rule.

# 3. Recommended required fields

I would make **slightly fewer fields compulsory** than the Kimi draft, but keep the performance-critical ones you mentioned.

Required:

```json
{
  "chembook": {
    "schema": "chembook.job.v0",
    "id": "c4a91f2b",
    "created": "2026-06-23T12:31:05.123456+02:00",
    "status": "done"
  },
  "job": {
    "type": "relax"
  },
  "system": {
    "n_atoms": 42,
    "elements": {"C": 24, "H": 8, "O": 6, "Na": 2, "Cl": 2}
  },
  "method": {
    "code": "dftb+"
  },
  "run": {
    "command": "dftb+ > stdout.log 2> stderr.log",
    "duration_sec": 1.234567
  }
}
```

This is enough for:

```text
find all DFTB+ relax jobs
plot duration vs n_atoms
compare method/code/job type
detect failed jobs
organize by system composition
benchmark performance
```

I would not require `system.name` or `formula` if `elements` and `n_atoms` are present. The formula can be generated deterministically from `elements`.

Also, `run.duration_sec` should be required only after the job attempted to run. For `status: "created"` or `status: "pending"`, it can be absent.

# 4. Revised `chembook.json` template

A practical compact version:

```json
{
  "chembook": {
    "schema": "chembook.job.v0",
    "id": "c4a91f2b",
    "created": "2026-06-23T12:31:05.123456+02:00",
    "status": "done"
  },

  "job": {
    "type": "relaxed_scan",
    "name": "PTCDA_NaCl_height_scan",
    "purpose": "compare adsorption energy vs height"
  },

  "system": {
    "name": "PTCDA_on_NaCl",
    "formula": "C24H8O6Na32Cl32",
    "elements": {"C": 24, "H": 8, "O": 6, "Na": 32, "Cl": 32},
    "n_atoms": 102,
    "charge": 0,
    "spin": 1,
    "pbc": [true, true, false],
    "structure": {
      "initial": "input/start.xyz",
      "final": "extracted/final.xyz"
    }
  },

  "method": {
    "code": "dftb+",
    "code_version": "24.1",
    "method": "SCC-DFTB",
    "basis": "3ob-3-1",
    "dispersion": "D3"
  },

  "run": {
    "command": "python run_scan.py --system PTCDA_NaCl.xyz --zmin 2.5 --zmax 6.0",
    "hostname": "Prokop_Desktop_GTX3090",
    "cwd": "/home/prokophapala/git/CompChemUtils/examples/PTCDA_scan",
    "started": "2026-06-23T12:31:05.123456+02:00",
    "finished": "2026-06-23T12:31:06.358023+02:00",
    "duration_sec": 1.234567,
    "timer": "time.perf_counter_ns",
    "exit_code": 0
  },

  "results": {
    "energy": {"value": -1234.567, "unit": "eV"},
    "converged": true,
    "max_force": {"value": 0.023, "unit": "eV/A"}
  },

  "data": {
    "tables": ["extracted/scan.csv"],
    "arrays": ["extracted/scan.npz"],
    "structures": ["extracted/trajectory.xyz", "extracted/final.xyz"],
    "plots": ["plots/scan_energy.html"]
  },

  "files": {
    "input": ["input/dftb_in.hsd", "input/geo.gen"],
    "raw": ["raw/detailed.out", "raw/results.tag"],
    "keep": ["chembook.json", "extracted/final.xyz", "extracted/scan.npz"],
    "large": ["raw/WAVECAR", "raw/CHGCAR"]
  },

  "cleanup": {
    "level": "full",
    "log": []
  },

  "tags": ["NaCl", "PTCDA", "scan", "surface"]
}
```

This is not too formal, but enough to mine.

# 5. Field-by-field decisions

## `chembook.schema`

Keep it. It is useful.

But do not make it a bureaucratic monster. It simply means:

```text
which validator/migrator should read this file?
```

Use:

```json
"schema": "chembook.job.v0"
```

Rather than:

```json
"schema_version": "0.1.0"
```

because later you may also have:

```text
chembook.project.v0
chembook.campaign.v0
chembook.system.v0
chembook.job.v0
```

But you do not need `level: job`; the schema name already says what kind of node it is.

## `chembook.id`

Do not call it UUID if it is short.

Use:

```json
"id": "c4a91f2b"
```

Generation:

```python
secrets.token_hex(4)  # 8 hex chars = 32 random bits
```

But 32 bits is a bit collision-prone if you create tens of thousands of jobs. Better:

```python
secrets.token_hex(6)  # 12 hex chars = 48 random bits
```

Example:

```text
a13f92c08b7e
```

This is GitHub-like, short, readable, copyable.

Collision strategy:

```text
1. Generate random 12-hex id.
2. Walk project and collect existing ids.
3. If collision, regenerate.
4. If writing inside unknown standalone folder, no problem; collision only matters inside one project tree.
```

Do not derive it from path, date, formula, or command. Those can change. ID should be opaque.

## `git_commit`

Make optional.

Better name:

```json
"source": {
  "script": "run_scan.py",
  "git_commit": "abc123",
  "git_dirty": true
}
```

But it should be absent if irrelevant. Many jobs are not from a git-controlled script.

## `parent`

I agree it is usually redundant and fragile.

Instead of parent pointers, use filesystem ancestry plus optional campaign IDs.

For grouping, use:

```json
"campaign": "PTCDA_NaCl_scan_v1"
```

or:

```json
"job": {
  "type": "relaxed_scan",
  "campaign": "PTCDA_NaCl_scan_v1"
}
```

Parent links are only needed for true derivation/provenance:

```json
"derived_from": [
  {"id": "9a8b7c6d1234", "path": "../relax/final.xyz", "role": "initial_geometry"}
]
```

That is more meaningful than `parent: ../relax_scan`.

# 6. Job type vocabulary

Use job types as a controlled-but-extensible vocabulary.

Hard validator should warn, not fail, on unknown job types.

Initial list:

```text
single_point
relax
rigid_scan
relaxed_scan
neb
md
vibrations
phonons
normal_modes
afm
stm
iets
density
esp
charges
fukui
resp
bond_order
interaction_energy
fragment_scan
conformer_search
adsorption_search
firecore_basin_hopping
gridff_fit
ml_dataset_generation
benchmark
postprocess
plot
```

For your tools, I would especially distinguish:

```text
afm
stm
gridff
ppafm
firecore_search
interaction_energy
fukui
density
esp
```

because these will have very different extracted result files.

Example:

```json
"job": {
  "type": "afm",
  "subtype": "ppafm_forcefield_scan"
}
```

or:

```json
"job": {
  "type": "interaction_energy",
  "subtype": "rigid_fragment_scan"
}
```

Do not over-normalize too early.

# 7. Timing and benchmarking

For local fast jobs, store both wall time and maybe CPU/GPU timing if available.

Required:

```json
"duration_sec": 0.013742
```

Optional:

```json
"timing": {
  "wall_sec": 0.013742,
  "cpu_user_sec": 0.041,
  "cpu_sys_sec": 0.002,
  "gpu_kernel_sec": 0.0061,
  "n_steps": 128,
  "step_per_sec": 9314.2,
  "ns_per_atom_step": 105.0
}
```

For benchmark analysis, compulsory dimensions should be:

```json
"system": {
  "elements": {"C": 24, "H": 8, "O": 6},
  "n_atoms": 38
},
"method": {
  "code": "FireCore",
  "method": "GridFF"
},
"job": {
  "type": "relax"
},
"run": {
  "duration_sec": 0.034521
}
```

Then `chembook bench` can produce:

```text
duration vs n_atoms
duration per atom
duration per step
duration grouped by code/method/job.type
failed fraction by code/method
```

For timing implementation:

```python
t0_ns = time.perf_counter_ns()
...
t1_ns = time.perf_counter_ns()
duration_sec = (t1_ns - t0_ns) * 1e-9
```

Store ISO timestamps separately for human chronology, but use `perf_counter_ns()` for duration. Wall-clock timestamps can jump; perf counter is monotonic.

# 8. Results: flat or nested?

For common scalar results, I recommend **flat canonical keys with units in the key** for mining speed:

```json
"results": {
  "energy_eV": -1234.567,
  "max_force_eVA": 0.023,
  "converged": true,
  "dipole_D": [0.0, 0.0, 3.1]
}
```

This is less elegant than:

```json
"energy": {"value": ..., "unit": ...}
```

but much easier for grep, jq, plotting, pandas, and AI.

For unusual quantities, use nested objects.

Good compromise:

```json
"results": {
  "energy_eV": -1234.567,
  "max_force_eVA": 0.023,
  "converged": true,
  "extra": {
    "homo_eV": -5.1,
    "lumo_eV": -2.3
  }
}
```

Avoid too much unit abstraction. In computational chemistry, you mostly know the canonical internal units:

```text
energy_eV
force_eVA
distance_A
angle_deg
charge_e
dipole_D
time_sec
frequency_cm1
```

This is practical.

# 9. Data products by job type

This is probably where ChemBook becomes genuinely useful.

## `single_point`

```text
extracted/
  final.xyz              optional if structure copied
  energy.json
  charges.csv
  orbitals.npz           optional
  density.cube           optional large
```

Canonical results:

```json
"results": {
  "energy_eV": -123.4,
  "converged": true,
  "homo_eV": -5.2,
  "lumo_eV": -2.1,
  "gap_eV": 3.1
}
```

## `relax`

```text
extracted/
  final.xyz
  relax.csv              step, energy_eV, max_force_eVA, rms_force_eVA
  trajectory.xyz
  relax.npz
  relax.html
```

## `rigid_scan` / `relaxed_scan`

```text
extracted/
  scan.csv
  scan.npz
  trajectory.xyz
  best.xyz
plots/
  E_vs_coordinate.html
  overview.html
```

`scan.csv`:

```csv
i,x_A,y_A,z_A,angle_deg,distance_A,energy_eV,max_force_eVA,converged
0,0.0,0.0,2.5,0.0,2.5,-123.0,0.10,true
```

## `neb`

```text
extracted/
  neb.csv                image, reaction_coordinate_A, energy_eV, force_tangent_eVA
  images.xyz
  barrier.json
plots/
  neb_profile.html
```

Canonical results:

```json
"results": {
  "barrier_forward_eV": 0.72,
  "barrier_backward_eV": 0.41,
  "deltaE_eV": -0.31,
  "n_images": 8
}
```

## `afm`

```text
extracted/
  afm_meta.json
  force_z.npy / force_z.npz
  height_map.npy
  slices/
  preview.png
plots/
  afm_viewer.html
```

Canonical results:

```json
"results": {
  "grid_nx": 256,
  "grid_ny": 256,
  "grid_nz": 64,
  "dx_A": 0.1,
  "dy_A": 0.1,
  "dz_A": 0.1
}
```

## `stm`

```text
extracted/
  stm_current.npy
  ldos.npy
  bias_scan.csv
plots/
  stm_viewer.html
```

## `fukui`

```text
extracted/
  fukui_atoms.csv
  fukui_grid.cube
  charges_neutral.csv
  charges_plus.csv
  charges_minus.csv
plots/
  fukui_atoms.html
```

Canonical results:

```json
"results": {
  "fukui_max_atom": 17,
  "fukui_max_value": 0.18
}
```

## `interaction_energy`

```text
extracted/
  interaction.csv
  interaction.npz
  best_geometry.xyz
plots/
  interaction_map.html
```

Canonical columns:

```csv
i,dx_A,dy_A,dz_A,rx_deg,ry_deg,rz_deg,E_total_eV,E_elst_eV,E_pauli_eV,E_disp_eV
```

# 10. Human-readable vs binary files

Use this rule:

```text
CSV/XYZ/JSON = inspection, portability, debugging
NPY/NPZ = fast mining, plotting, ML, large arrays
HTML = fast visual navigation
```

Do not require both. But when ChemBook generates both, it should record the relation.

Example:

```json
"data": {
  "tables": [
    {
      "path": "extracted/scan.csv",
      "binary": "extracted/scan.npz",
      "kind": "scan_table",
      "columns": ["z_A", "energy_eV", "max_force_eVA"]
    }
  ]
}
```

For consistency checking, write small metadata into NPZ:

```python
np.savez(
    "scan.npz",
    z_A=z,
    energy_eV=E,
    max_force_eVA=F,
    _columns=np.array(["z_A", "energy_eV", "max_force_eVA"]),
    _source_csv=np.array("scan.csv"),
    _chembook_id=np.array("c4a91f2b")
)
```

# 11. Cleanup/pruning design

Do not just delete. Always transform:

```text
raw bulky output -> extracted compact result -> log deletion
```

Recommended cleanup classes:

```text
full       keep everything
safe       delete only obvious scratch/temp files
compact    keep raw text logs, delete restart/wavefunction/grid bulk
minimal    keep only extracted results + inputs + chembook.json
summary    keep only chembook.json + summary plots/tables
tombstone  keep only chembook.json with deletion log
```

Example:

```json
"cleanup": {
  "level": "compact",
  "log": [
    {
      "time": "2026-06-23T13:10:01.222+02:00",
      "action": "delete",
      "path": "raw/WAVECAR",
      "size_bytes": 8123412312,
      "reason": "large_recomputable_wavefunction",
      "extracts_preserved": ["extracted/final.xyz", "extracted/energy.json"]
    }
  ]
}
```

`chembook prune --dry-run` should print:

```text
Would remove:
  raw/WAVECAR   8.1 GB   large_recomputable_wavefunction
  raw/CHGCAR    2.2 GB   large_recomputable_density
Would keep:
  extracted/final.xyz
  extracted/scan.npz
  raw/OUTCAR
Estimated saving: 10.3 GB
```

Pruning should be conservative by default.

# 12. Tooling architecture

No SQL now. Use filesystem scan + JSON + optional generated cache.

Python package:

```text
py/chembook/
  __init__.py
  cli.py
  schema.py
  ids.py
  scan.py
  validate.py
  run.py
  extract/
    __init__.py
    dftb.py
    xtb.py
    orca.py
    psi4.py
    pyscf.py
    gpaw.py
    firecore.py
    ppafm.py
    lammps.py
  convert.py
  plot.py
  prune.py
  summarize.py
  query.py
  reorganize.py
  formats/
    xyz.py
    csv_npz.py
    formula.py
```

CLI:

```text
chembook init
chembook new
chembook run
chembook wrap
chembook extract
chembook scan
chembook validate
chembook find
chembook table
chembook bench
chembook convert
chembook plot
chembook summarize
chembook prune
chembook copy-minimal
chembook rename-suggest
```

Important commands:

## `chembook scan`

Walk tree and list nodes:

```bash
chembook scan .
```

Output:

```text
id            status  type          code     n_atoms  duration  path
a13f92c08b7e  done    relax         dftb+    102      1.23 s    PTCDA/DFTB/relax
b81aa90019cc  failed  relaxed_scan  xtb      102      0.44 s    PTCDA/xTB/scan_01
```

## `chembook table`

Create CSV summary:

```bash
chembook table . --out summary.csv
```

Columns:

```text
id,path,status,job_type,system_name,formula,n_atoms,code,method,basis,energy_eV,max_force_eVA,duration_sec
```

## `chembook bench`

```bash
chembook bench . --group code,job.type --x n_atoms --y duration_sec
```

## `chembook find`

Simple query syntax, not SQL:

```bash
chembook find . "status=done code=dftb+ type=relax n_atoms>100 energy_eV<-500"
```

Internally this can just parse into Python predicates.

## `chembook copy-minimal`

This is important for your “lossy compression but preserve structure” idea:

```bash
chembook copy-minimal project/ project_minimal/ --level minimal
```

It copies only:

```text
chembook.json
README.md
extracted/
plots/
selected input files
```

and preserves relative paths.

# 13. Directory naming guidelines

Hard rule: tools do not depend on names.

Soft recommendation: avoid dates at the front.

Useful naming dimensions:

```text
system
method/code
basis/parameterization
job_type
short purpose/index
```

For system-focused projects:

```text
PTCDA_NaCl/
  DFTB_3ob_D3/
    relax/
    scan_height/
    afm/
  xTB_GFN2/
    relax/
```

For benchmark-focused projects:

```text
benchmark_relax/
  H2O/
    dftb_3ob/
    xtb_gfn2/
    psi4_pbe/
  benzene/
    dftb_3ob/
    xtb_gfn2/
```

For campaign-focused projects:

```text
PTCDA_adsorption_scan/
  site_A_dftb/
  site_B_dftb/
  site_C_dftb/
```

For generated many-job folders:

```text
j0001_siteA_z2.5/
j0002_siteA_z2.6/
j0003_siteB_z2.5/
```

I would avoid:

```text
2026-06-23_test1/
new/
final/
final_final/
tmp_good/
```

Date belongs in `chembook.json`, not in the directory name.

# 14. Extractor plugin principle

Every code extractor should return the same generic object:

```python
{
    "system": {...},
    "method": {...},
    "results": {...},
    "data": {...},
    "files": {...}
}
```

Extractor should not care where the folder is located.

Detection:

```text
dftb+     dftb_in.hsd, detailed.out, results.tag
xtb       xtb.out, xtbopt.xyz
orca      *.inp, *.out, *.gbw
psi4      output.dat, timer.dat
pyscf     Python script + stdout + chk/molden
gpaw      *.gpw, *.txt
cp2k      *.inp, *.out, *-pos-*.xyz
lammps    log.lammps, dump.*
firecore  FireCore-specific logs, xyz trajectories, grid/scan outputs
ppafm     params.ini, OutFz.xsf/cube/npy, df images
```

The extractor should be allowed to partially succeed:

```text
found energy
did not find final geometry
found timing
could not determine basis
```

No silent lies.

# 15. AI `SKILL.md` guideline

The AI instruction should say roughly:

```text
When generating a computational chemistry job:
1. Create or update chembook.json.
2. Fill only fields you actually know.
3. Do not invent code version, basis, convergence, or energy.
4. Always capture command, cwd, host, start/finish time, duration_sec, exit_code.
5. Always record n_atoms and elements if a structure is available.
6. Write README.md only as human explanation; do not rely on it for machine data.
7. Save compact extracted results in extracted/.
8. Prefer CSV for small tables and NPZ for large arrays.
9. Generate static HTML plots for scans/maps when useful.
10. Log every cleanup/deletion in chembook.json.
```

This is where “soft” policy belongs.

# 16. My recommended minimal v0.1

Do **not** implement everything first.

Implement in this order:

## Phase 1: ledger

```text
chembook init
chembook scan
chembook validate
chembook run
chembook table
```

## Phase 2: extraction

```text
extract xyz/formula/elements
extract DFTB+
extract xTB
extract simple generic logs
extract FireCore/scan CSV if easy
```

## Phase 3: data products

```text
csv <-> npz
plot.html for scan.csv
summary.csv over project
```

## Phase 4: cleanup

```text
prune --dry-run
prune --level compact
copy-minimal
```

This will already solve 80% of the pain.

# 17. Important design correction to previous draft

I would remove these as compulsory:

```text
parent
level
git_commit
README.md
fixed directory structure
created date in folder name
```

I would keep these compulsory for completed/attempted jobs:

```text
chembook.schema
chembook.id
chembook.created
chembook.status
job.type
system.n_atoms
system.elements
method.code
run.command
run.duration_sec
```

For pending jobs, allow missing `duration_sec`.

For non-job nodes such as project/campaign/system summaries, use different schema:

```json
{
  "chembook": {
    "schema": "chembook.project.v0",
    "id": "e21a09ccf712",
    "created": "...",
    "status": "active"
  },
  "project": {
    "name": "PTCDA_NaCl_screening"
  }
}
```

So the validator knows not to require `run.duration_sec` for a project node.

# 18. One compact final v0 schema

```json
{
  "chembook": {
    "schema": "chembook.job.v0",
    "id": "a13f92c08b7e",
    "created": "2026-06-23T12:31:05.123456+02:00",
    "status": "done"
  },
  "job": {
    "type": "relax",
    "name": "PTCDA_NaCl_DFTB_relax"
  },
  "system": {
    "name": "PTCDA_NaCl",
    "elements": {"C": 24, "H": 8, "O": 6, "Na": 32, "Cl": 32},
    "n_atoms": 102,
    "formula": "C24H8O6Na32Cl32",
    "charge": 0,
    "spin": 1,
    "pbc": [true, true, false]
  },
  "method": {
    "code": "dftb+",
    "method": "SCC-DFTB",
    "basis": "3ob-3-1",
    "dispersion": "D3"
  },
  "run": {
    "command": "dftb+ > stdout.log 2> stderr.log",
    "cwd": "/home/prokophapala/sim/PTCDA_NaCl/DFTB/relax",
    "hostname": "Prokop_Desktop_GTX3090",
    "started": "2026-06-23T12:31:05.123456+02:00",
    "finished": "2026-06-23T12:31:06.358023+02:00",
    "duration_sec": 1.234567,
    "timer": "perf_counter_ns",
    "exit_code": 0
  },
  "results": {
    "energy_eV": -1234.567,
    "max_force_eVA": 0.023,
    "converged": true
  },
  "data": {
    "structures": ["extracted/final.xyz"],
    "tables": ["extracted/relax.csv"],
    "arrays": ["extracted/relax.npz"],
    "plots": ["plots/relax.html"]
  },
  "files": {
    "input": ["input/dftb_in.hsd", "input/geo.gen"],
    "raw": ["raw/detailed.out", "raw/results.tag"],
    "keep": ["chembook.json", "extracted/final.xyz", "extracted/relax.npz"]
  },
  "cleanup": {
    "level": "full",
    "log": []
  },
  "tags": ["surface", "NaCl", "PTCDA"]
}
```

This is already enough to build powerful local navigation without becoming NOMAD/AiiDA bureaucracy.

---

# DeepSeek-V4-flash

We’re now at the point where we can lock down a concrete design. Based on your clarifications, I’ll give you the finalised schema, the tooling plan, and the integration strategy with your existing `CompChemUtils`. I’ll also address every point you raised.

## 1. Finalised `chembook.json` Schema

Only the **bold** fields are compulsory. Everything else is optional – but **strongly encouraged** when applicable.

```json
{
  "chembook": {
    "schema_version": "0.2.0",
    "uuid": "a1b2c3d4",
    "created": "2026-06-22T22:00:00.123456Z",
    "status": "done"
  },
  "job": {
    "type": "relaxed_scan",
    "name": "H2O_dftb3_scan"
  },
  "provenance": {
    "command": "python run.py --input H2O.xyz --method PBE",
    "hostname": "luna",
    "started": "2026-06-22T22:00:00.123456Z",
    "finished": "2026-06-22T22:00:01.234567Z",
    "duration_seconds": 1.234567,
    "exit_code": 0,
    "git_commit": "abc123"   // optional, auto-filled if git repo present
  },
  "system": {
    "name": "water molecule",
    "formula": "H2O",
    "elements": {"H": 2, "O": 1},
    "n_atoms": 3,
    "charge": 0,
    "spin": 1,
    "pbc": [false, false, false],
    "initial_structure": "input/H2O.xyz",  // optional
    "final_structure": "output/H2O_opt.xyz"
  },
  "method": {
    "code": "dftb+",
    "code_version": "24.1",
    "level": "SCC-DFTB",
    "basis": "3ob-3-1",
    "dispersion": "D3"
  },
  "results": {
    "energy": {"value": -1234.5, "unit": "eV"},
    "converged": true,
    "max_force": {"value": 0.01, "unit": "eV/Å"}
  },
  "files": {
    "input": ["input/dftb_in.hsd"],
    "output": ["output/detailed.out"],
    "extracted": ["extracted/scan.csv", "extracted/scan.npz"]
  },
  "tags": ["relaxation", "dftb", "test"],
  "notes": "human-readable note"
}
```

### Compulsory Fields (minimum)

| Field | Why |
|-------|-----|
| `chembook.schema_version` | For future migrations (rigour). |
| `chembook.uuid` | Unique ID for cross‑referencing. |
| `chembook.created` | Timestamp of node creation. |
| `chembook.status` | `pending` / `running` / `done` / `failed` / `pruned`. |
| `provenance.command` | Exact command that launched the job (reproducibility). |
| `provenance.duration_seconds` | Wall‑clock time in seconds (float) – precise to sub‑ms. |
| One of `system.name` or `system.formula` | Human‑friendly identification. |
| `system.elements` | Atom counts per element – **compulsory** for performance benchmarking. |
| `system.n_atoms` | Total atoms – also compulsory. |

Everything else is optional, but tools will fill as much as they can.

## 2. UUID Generation & Uniqueness

- **Generation**: use `secrets.token_hex(4)` → 8‑character random hex string (e.g., `a1b2c3d4`). Collision probability is negligible for a local project (<100k nodes).
- **Uniqueness check**: when creating a new node, the tool scans all existing `chembook.json` files in the project root (via `glob`) and raises an error if the generated UUID already exists. If it does, it regenerates.
- **Alternative**: you can base it on a short hash of `created` + `command` + random salt, but random is fine.

## 3. Timing Precision

We use `time.perf_counter_ns()` to get start and end times, then convert to seconds with nanosecond precision.

```python
start_ns = time.perf_counter_ns()
... run job ...
end_ns = time.perf_counter_ns()
duration_seconds = (end_ns - start_ns) / 1e9
```

Store as a float with full precision (Python’s float can handle ~1e‑9 relative). This allows you to benchmark fast jobs (e.g., 0.002 s) accurately.

## 4. Job Types – Based on Your Existing `py/tasks/`

We drop `parent` and `level` – they are redundant and not needed. Instead, we add `job.type` with allowed values from your existing task modules:

| Value | Source |
|-------|--------|
| `single_point` | (generic) |
| `relax` | `py/tasks/relax.py` |
| `rigid_scan` | `py/tasks/scan.py` |
| `relaxed_scan` | `py/tasks/scan.py` |
| `vibrations` | (to be added) |
| `phonons` | (to be added) |
| `density` | (e.g., for charge density) |
| `esp` | (electrostatic potential) |
| `fukui` | (Fukui indices) |
| `resp` | (Restrained ESP) |
| `interaction_energy` | `py/tasks/interaction_energy.py` |
| `neb` | (nudged elastic band) |
| `afm` | (atomic force microscopy) |
| `stm` | (scanning tunneling microscopy) |
| `md` | (molecular dynamics) |
| `custom` | fallback for anything else |

These are stored as strings. The tool does not enforce a controlled vocabulary but your `SKILL.md` will recommend using these exact names.

---

## 5. Performance Benchmarking: `system.elements` & `n_atoms`

We make `system.elements` (dictionary) and `system.n_atoms` (int) **compulsory**. This lets you query:

- Time per atom: `duration_seconds / n_atoms`
- Time per element type: group by `elements` and aggregate.
- Scaling of different methods.

This is invaluable for optimising your workflows. The tool will auto‑fill `elements` from the input structure if possible (e.g., via `ase` or `pymatgen`), otherwise you must provide it.

## 6. Directory Structure: Flexible, with Guidelines

**Hard rule**: A directory becomes a node **only** if it contains `chembook.json`. Otherwise it’s just a folder. This means you can have arbitrary nesting – flat, system‑first, method‑first, or campaign‑based.

**Soft guidelines** (for AI and human users, documented in `SKILL.md`):

- Prefer descriptive names (no dates).
- Suggest hierarchy by **system** → **method** → **basis** → **job type**, e.g.:
  ```
  project/
  ├── H2O/
  │   ├── DFTB3/
  │   │   ├── relax/
  │   │   │   └── chembook.json
  │   │   └── scan/
  │   │       └── chembook.json
  │   └── PBE/
  │       └── ...
  └── campaigns/
      └── H2O_dftb3_scan_2026/
          └── chembook.json
  ```

- Alternatively, **type‑first**:
  ```
  project/
  ├── relax/
  │   ├── H2O_DFTB3/
  │   └── H2O_PBE/
  └── scan/
      └── ...
  ```

The tools never depend on the path; they discover by walking and reading JSON. You can even mix layouts in one project.

## 7. Tooling: CLI Commands Overview

The Python package will provide the following commands (via `click` or `argparse`):

| Command | Description |
|---------|-------------|
| `chembook init <project_dir>` | Create a skeleton project (root `chembook.json` + README). |
| `chembook run <command...>` | Run a command, capture start/end time, write `chembook.json` with `status: pending` before, update to `done`/`failed` after. |
| `chembook extract <dir> [--code]` | Parse output files of the specified code (or auto‑detect) and fill `results`, `files.extracted`, etc. |
| `chembook sync <dir>` | Walk tree, aggregate summaries into each directory’s `README.md` (bottom‑up). |
| `chembook find <query>` | Search all `chembook.json` files via `jq`‑like syntax (e.g., `--filter 'results.energy.value < -1000'`). |
| `chembook convert <file.csv\|file.npz>` | Convert between CSV and NPZ; keep both in sync. |
| `chembook plot <file.csv> [--x ...] [--y ...]` | Generate an interactive `plot.html` (p5.js) for quick visual overview. |
| `chembook prune --dry-run <dir>` | Show what would be deleted/compressed. |
| `chembook prune --tier <gold\|silver\|bronze\|tin> <dir>` | Delete/compress files based on tier. Logs action in `chembook.json["pruning_log"]`. |
| `chembook migrate <dir>` | Update old `chembook.json` to the latest schema version. |

---

## 8. Extractor Architecture

Each software code has a dedicated parser that reads its output files and returns a dictionary matching the JSON schema (or a subset). The extractor is chosen by `method.code` (if present) or by inspecting file extensions.

From your environment, we prioritise:

| Code | Input files | Output files | Extractor priority |
|------|-------------|--------------|--------------------|
| **DFTB+** | `dftb_in.hsd`, `geo.gen` | `results.tag`, `detailed.out`, `band.out`, `hessian.out` | High |
| **Psi4** | `*.in`, `*.py` | `output.dat`, `timer.dat`, `*.xyz` | High |
| **xtb** | `*.xyz` | `xtb.out`, `xtbopt.xyz`, `*.charges`, `*.wbo` | High |
| **ORCA** | `*.inp` | `*.out`, `*.gbw`, `*.hess`, `*.xyz` | High |
| **pySCF** | Python script | stdout, `.chk`, `.molden` | High |
| **GPAW** | Python script | `.gpw`, `.txt`, `.cube` | Medium |
| **CP2K** | `*.inp` | `*.out`, `*.restart`, `*.xyz` | Medium |
| **LAMMPS** | `in.*`, data files | `log.lammps`, `dump.*` | Medium |
| **MOPAC** | `*.mop` | `*.out`, `*.arc`, `*.aux` | Low |
| **QUICK** | `*.inp` | `*.out` | Low |
| **ALAMODE** | `*.in` | phonon bands, DOS | Low |

The extractor will:

- Parse energy, forces, convergence status.
- Extract any relevant arrays (e.g., scan steps) and write them to `extracted/` as both `.csv` and `.npz`.
- Fill the `results` and `files` sections.

If no extractor is available, the job still runs, but `results` remains empty (you can manually add notes).

## 9. Scan / Trajectory Data Handling

For `rigid_scan`, `relaxed_scan`, `neb`, `md`, etc., we produce:

- `extracted/scan.csv`: human‑readable ASCII table with columns like `step, distance, angle, energy_eV, max_force`.
- `extracted/scan.npz`: binary NumPy archive for fast loading.
- `extracted/trajectory.xyz`: concatenated geometries (if many frames).

**Conversion** is bidirectional:

```bash
chembook convert extracted/scan.csv   # creates scan.npz
chembook convert extracted/scan.npz   # creates scan.csv
```

**Plotting**: generates a standalone `plot.html` using p5.js (embedded JSON data). No server needed. The plot can be interactive (zoom, select, hover). The tool can also generate overview plots that aggregate data from multiple nodes (e.g., energy vs. step for all scans in a directory).

## 10. Pruning Strategy (Tiers)

Define tiers based on **value‑to‑size** ratio:

| Tier | Contents | Example files | Action |
|------|----------|---------------|--------|
| **Gold** | Final energy, forces, converged structure | `chembook.json`, `final.xyz` | Keep forever. |
| **Silver** | Detailed log, semi‑structured output | `OUTCAR`, `detailed.out`, `vasprun.xml` | Keep unless disk pressure. |
| **Bronze** | Large, recomputable | `CHGCAR`, `WAVECAR`, `*.restart` | Delete after extraction. |
| **Tin** | Trajectory dumps | `XDATCAR`, `trajectory.xyz` | Extract energy vs. step to JSON, then delete. |

`chembook prune --tier bronze <dir>` will:

1. Scan all nodes.
2. For each, check `files.output` and delete files matching tier patterns.
3. Write a log entry under `pruning_log` (list of deleted files, date, tier).
4. Update `status` to `pruned` if all files are gone (optional).

A `--dry-run` flag previews actions without deleting.

## 11. Hard Rules vs. Soft Guidelines (for AI)

**Hard Rules (enforced by Python)**:

- `chembook.json` must have compulsory fields and valid JSON.
- UUID uniqueness is checked.
- `status` must be one of the allowed values.
- `job.type` should be one of the predefined names (but not strictly enforced – a warning is emitted).
- `convert` keeps CSV and NPZ consistent (timestamp).

**Soft Guidelines (documented in `SKILL.md` and README templates)**:

- How to write `README.md`: sections for purpose, method, results, and comments.
- Suggested directory naming patterns (no dates, use system/method/job_type).
- When to create `extracted/` and what files to put there.
- Recommended tags for easy searching.
- The AI is encouraged to follow these guidelines but is not required – the tools will still work.

## 12. Integration with Your `CompChemUtils`

- The `chembook` package will live under `py/chembook/`.
- It will import from your existing `py/interfaces/` (for structure manipulation) and `py/tasks/` (to know job types).
- The missing `py/tasks/base.py` should be created – it will define the `Task` base class and the list of allowed job types. This is a trivial file.

- The `chembook run` command can wrap your existing `run.py` or directly use the task classes. It will:
  - Write a skeleton `chembook.json` with `status: pending` before execution.
  - Execute the task (capturing stdout/stderr).
  - On success, update with `duration_seconds`, `status: done`, and call `extract` automatically.
  - On failure, set `status: failed` and `exit_code`.

- This way, your existing workflows remain unchanged but gain automatic metadata capture.

## 13. Next Steps

1. **Implement `py/chembook/` skeleton**:
   - `schema.py` – Pydantic models for validation.
   - `core.py` – functions to read/write, walk directories, generate UUIDs.
   - `cli.py` – commands `init`, `run`, `extract`, `sync`, `find`, `convert`, `plot`, `prune`, `migrate`.
   - `extractors/` – plugins for each code.

2. **Create `py/tasks/base.py`** with job type enumeration and a base class for tasks.

3. **Write `doc/ChemBook/SKILL.md`** – the AI guideline document, covering directory naming, README structure, and best practices.

4. **Write migration script** to retroactively convert old projects: scan for known output files, guess method, and generate `chembook.json` skeletons.

5. **Test** on a few of your existing calculations to refine the extractors.

## 14. Answers to Your Specific Questions

> **1) Timing** – We use `perf_counter_ns()` and store `duration_seconds` as float.

> **2) UUID** – 8‑char random hex, collision check across project.

> **3) git_commit** – Optional, auto‑filled if a `.git` directory exists (not compulsory).

> **4) parent/level** – Removed. `job.type` is the main categorisation.

> **5) Performance** – `system.elements` and `n_atoms` are compulsory.

> **6) schema** – Kept for validation and future migrations (rigour without bloat).

> **Directory naming** – No date; guidelines suggest `system/method/job` or `system_job_method` – flexible, tools ignore names.

This design gives you a **minimal but extensible format**, **powerful CLI tools**, and a clear separation between machine‑enforced rules and AI‑friendly guidelines. It’s tailored to your existing codes and workflows, and it avoids over‑engineering.

If you’re happy with this, we can start implementing the skeleton – I’ll draft the Pydantic models and the first CLI commands. Would you like me to do that now, or do you want to iterate on any part?

---

# Kimi 2.6

I'll synthesize all your clarifications into a concrete, detailed specification. This is substantial design work, so I'll save it as a structured document you can reference and iterate on.
I've synthesized everything into a comprehensive specification document. Let me summarize the key decisions and architecture, then point you to the full document.

## Summary of the ChemBook Design

### Core Philosophy: Minimal Format, Maximal Tools

The system has two layers:

1. **Hard Rules (Python-enforced):** A single `chembook.json` per directory with ~12 compulsory fields. No SQL, no fixed directory structure. The filesystem is the database.
2. **Soft Guidelines (AI SKILL.md):** README templates, naming conventions, pruning advice. These are recommendations, not requirements.

### The 12 Compulsory Fields in `chembook.json`

| Section | Fields | Why |
|---------|--------|-----|
| `chembook` | `schema_version`, `uuid` (8-char), `created`, `status` | Identity & versioning |
| `job` | `type` (from your tasks), `name` | Extractor dispatch |
| `provenance` | `command`, `hostname`, `started`, `finished`, `duration_seconds`, `exit_code` | **Reproducibility & benchmarking** |
| `system` | `formula`, `elements` dict, `n_atoms` | Performance normalization |
| `method` | `code` (lowercase) | Extractor selection |

**Key decisions from your feedback:**
- **Timing:** `time.perf_counter_ns()` → `duration_seconds` with 6+ decimal places. Essential for sub-millisecond local jobs.
- **UUID:** 8-character base32-ish (no ambiguous chars like `i`, `l`, `1`, `0`). Collision-checked against all existing nodes.
- **No `parent`/`level`:** Dropped as redundant. Directory structure is implicit.
- **No `git_commit`:** Optional only, not compulsory.
- **`job.type`:** Maps directly to your `py/tasks/` (relax, rigid_scan, relaxed_scan, interaction_energy, fukui, afm, stm, etc.)

### Data Tiers for Pruning

| Tier | Examples | Default Fate |
|------|----------|-------------|
| **T0 Core** | `chembook.json`, extracted CSV/NPZ, final XYZ | Never delete |
| **T1 Valuable** | `OUTCAR`, `detailed.out` | Keep 90d, then compress |
| **T2 Useful** | `WAVECAR`, `CHGCAR`, full trajectory | Compress, delete after 30d |
| **T3 Bulk** | MD dump every step, `PROCAR` | Delete after extraction verified |
| **T4 Debug** | Scratch files, temp restarts | Delete immediately |

Pruning is **declarative** via `prune_policy.json` (optional) and **safe** via dry-run + verification that T0 data exists before deleting anything.

### File Formats

- **CSV + NPZ pairs** for all tabular data (scans, NEB, MD). `chembook convert` keeps them in sync.
- **p5.js HTML** for interactive plots. Static files, no server.
- **XYZ** as universal structure format. `.gen` for DFTB+, `.cif` for crystals.

### CLI Tooling (`chembook` command)

```bash
chembook init <dir>              # Create node with pending status
chembook run --type relax -- <cmd>  # Capture provenance, run, update status
chembook extract <dir>           # Auto-detect code, parse outputs
chembook find --formula H2O --duration-lt 0.5  # Query across all nodes
chembook sync --readme          # Regenerate READMEs from JSON
chembook prune --dry-run        # Preview cleanup
chembook stats --by-code        # Benchmark: time/atom, success rates
chembook convert scan.csv       # CSV <-> NPZ sync
chembook plot scan.csv --html   # Generate p5.js plot
```

### Software Coverage

Extractors planned for all your codes: **DFTB+** (primary), xtb, Psi4, ORCA, pySCF, GPAW, CP2K, LAMMPS, MOPAC, QUICK, ALAMODE. Plus a generic regex fallback.

### Open Questions for You

1. **UUID length:** 8 chars (typable) or 12 (safer for >10k jobs)?
2. **`provenance.working_directory`:** Optional or compulsory? Helps debugging but may leak paths.
3. **Results typing:** Strict Pydantic per `job.type` (more maintenance, better queries) or loose dict (flexible, less validation)?
4. **Multi-step workflows:** A `workflow` tag in `chembook.json`, or a separate `workflow.json` at campaign level?
5. **Directory naming preference:** System-first (`H2O/DFTB3/relax`) or campaign-first (`campaigns/H2O_benchmark/001_...`)?

The full specification is here: **[ChemBook_Specification_v0.1.md](sandbox:///mnt/agents/output/ChemBook_Specification_v0.1.md)**

This document covers:
- Complete JSON schema (compulsory + optional fields)
- UUID generation algorithm
- Nanosecond timing capture
- All 15 job types mapped to your tasks
- Results schemas for each job type
- CSV/NPZ format specification
- p5.js plot generation approach
- Data tier system and pruning policy
- Full Python package architecture
- Pydantic models
- Extractor interface
- Complete CLI specification with examples
- AI SKILL.md guidelines
- Software coverage matrix for all 11 codes
- 8-week implementation roadmap
- Open design decisions

Let me know which of the open decisions you'd like to resolve, and I can start drafting the Python skeleton (Pydantic models + `chembook init`/`run`/`check`) next.

---

# USER

read @[doc/ChemBook.chat.md] again from 1630 and make another round of meta-analysis, we should wrap up, suggest a reasonable synthesis of these suggestions, and finish the design with just few open questions (design decisions)

---

# Kimi 2.6 / devin

# Round 2: Final Meta-Analysis and Synthesis

## What is now solid consensus

The discussion converged on a minimal-permissive-format-plus-rich-tooling design. The following points are agreed among all participating models:

- **Hard vs. soft split.** `chembook.json` is machine-written and minimally validated; `README.md` is optional human explanation; `SKILL.md` guides AI behavior.
- **Filesystem as source of truth.** A directory becomes a node only by containing `chembook.json`. No fixed global hierarchy.
- **Single JSON per node.** No SQL, no central database, no GUI now.
- **Few compulsory fields.** Identity (`id`/`uuid`), creation time, status, job type, command, timing, and system composition are required.
- **Nanosecond timing.** Use `time.perf_counter_ns()` and store `duration_sec`/`duration_seconds` as a float.
- **Short opaque random hash.** 8-12 hex characters, collision-checked against all existing nodes in the project tree.
- **Drop `parent` and `level`.** Use filesystem ancestry or optional `campaign`/`derived_from` for grouping.
- **Drop compulsory `git_commit`.** Make it optional only if a `.git` directory is present.
- **Add `job.type`.** Maps directly to your existing `py/tasks/` and `py/interfaces/_base.py` capabilities.
- **Compulsory performance fields.** `system.n_atoms` and `system.elements` (atom count per element) are required.
- **CSV + NPZ pairs.** Tabular data lives in both human-readable CSV and binary NPZ, kept consistent by `chembook convert`.
- **Static interactive plots.** `plot.html` with embedded p5.js + JSON data snapshot, no server.
- **Pruning is logged.** Every deletion/compression is recorded in `chembook.json` under a `cleanup`/`pruning_log` section.
- **No dates in directory names.** Use descriptive names; dates belong in the JSON.
- **Flexible directory naming.** Suggested dimensions: system, method/code, basis/parameterization, job type, short purpose/index.
- **Extractor plugins.** One per code (DFTB+, xtb, Psi4, ORCA, pySCF, GPAW, CP2K, LAMMPS, MOPAC, QUICK, ALAMODE). Missing extractor does not fail the node.
- **Schema version.** Kept for migration/validation, but not over-engineered.

## Where the LLMs still disagree (and my synthesis)

| Topic | Options | Synthesis |
|-------|---------|-----------|
| ID field name | `chembook.uuid` vs `chembook.id` | Use `chembook.id`. The value is short (8-12 hex), GitHub-like, and "UUID" is misleading for a non-128-bit identifier. |
| ID length | 8 hex (32 bits) vs 12 hex (48 bits) | Use **12 hex characters** (`c4a91f2b8a7e`). Negligible typing cost, safe for >10k nodes. |
| Schema identifier | `schema_version: "0.1.0"` vs `schema: "chembook.job.v0"` | Use `chembook.schema = "chembook.job.v0"`. The schema name encodes both the kind of node and the version, so future non-job nodes (project, campaign, system) do not need a separate `level` field. |
| Timing section name | `provenance` vs `run` | Use `provenance` for the command/host/duration/exit code block. The word is slightly more accurate; `run` is a verb. |
| Duration key | `duration_sec` vs `duration_seconds` | Use `duration_sec`. Shorter, unambiguous, and common in your scientific code. |
| Result units | `energy.value`+`unit` vs `energy_eV` flat | Use **flat canonical keys with units in the key** (`energy_eV`, `max_force_eVA`). Easier for grep, jq, pandas, and plotting. Reserve nested `{value, unit}` only for rare or ambiguous quantities. |
| Job type enforcement | strict enum vs warn-only | **Warn, not fail.** The vocabulary should be recommended in `SKILL.md`, but the format must tolerate new tasks. |
| Directory naming preference | system-first vs method-first vs task-first | No hard rule. **Soft guideline**: use `system / method / job_type` for system-focused studies, `campaign / job_type / system` for campaign-focused studies, and `benchmark / system / method` for benchmark-focused studies. |
| Pruning tier names | core/valuable/bulk vs gold/silver/bronze/tin vs T0-T4 | Use **tier names with clear meaning**: `core`, `logs`, `recomputable`, `scratch`. The `core` tier is protected; `logs` are kept; `recomputable` bulk is deletable after extraction; `scratch` is temporary. |
| Results schema | strict Pydantic per `job.type` vs loose dict | Use a **loose dict with a small set of canonical scalar keys**. The validator only checks that canonical keys use the correct unit suffix. Per-job-type strict schemas are too much maintenance for v0. |
| Should `py/tasks/base.py` be created? | Yes, as a minimal task registry | Yes. Create `py/tasks/base.py` with a small `TaskType` enum/string registry and the result dataclasses (`ScanResult`, `RelaxResult`, `InteractionEnergyResult`) that are currently imported from a missing file. |
| Initial implementation order | CLI first vs schema/extractors first | Start with `schema.py` + `core.py` + `cli.py init/run/validate/scan`, then DFTB+/xtb extractors, then CSV/NPZ conversion and plotting. |

## Final v0.1 design decisions

### Compulsory fields (job nodes)

```json
{
  "chembook": {
    "schema": "chembook.job.v0",
    "id": "c4a91f2b8a7e",
    "created": "2026-06-23T12:31:05.123456+02:00",
    "status": "done"
  },
  "job": {
    "type": "relax",
    "name": "PTCDA_NaCl_DFTB_relax"
  },
  "system": {
    "n_atoms": 102,
    "elements": {"C": 24, "H": 8, "O": 6, "Na": 32, "Cl": 32}
  },
  "method": {
    "code": "dftb+"
  },
  "provenance": {
    "command": "dftb+ > stdout.log 2> stderr.log",
    "duration_sec": 1.234567,
    "exit_code": 0
  }
}
```

Everything else is optional. For `status: "pending"` or `"running"`, `duration_sec` and `exit_code` may be absent.

### Recommended optional fields

```json
{
  "system": {
    "name": "PTCDA_on_NaCl",
    "formula": "C24H8O6Na32Cl32",
    "charge": 0,
    "spin": 1,
    "pbc": [true, true, false],
    "structure": {
      "initial": "input/start.xyz",
      "final": "extracted/final.xyz"
    }
  },
  "method": {
    "code_version": "24.1",
    "method": "SCC-DFTB",
    "basis": "3ob-3-1",
    "dispersion": "D3"
  },
  "provenance": {
    "hostname": "Prokop_Desktop_GTX3090",
    "cwd": "/home/prokophapala/sim/PTCDA_NaCl/DFTB/relax",
    "started": "2026-06-23T12:31:05.123456+02:00",
    "finished": "2026-06-23T12:31:06.358023+02:00",
    "timer": "perf_counter_ns",
    "git_commit": "abc123"
  },
  "results": {
    "energy_eV": -1234.567,
    "max_force_eVA": 0.023,
    "converged": true
  },
  "data": {
    "structures": ["extracted/final.xyz"],
    "tables": ["extracted/relax.csv"],
    "arrays": ["extracted/relax.npz"],
    "plots": ["plots/relax.html"]
  },
  "files": {
    "input": ["input/dftb_in.hsd", "input/geo.gen"],
    "raw": ["raw/detailed.out", "raw/results.tag"],
    "core": ["chembook.json", "extracted/final.xyz", "extracted/relax.npz"]
  },
  "cleanup": {
    "level": "full",
    "log": []
  },
  "tags": ["surface", "NaCl", "PTCDA"],
  "notes": "short human note"
}
```

### Job type vocabulary

```text
single_point
relax
rigid_scan
relaxed_scan
neb
md
vibrations
phonons
afm
stm
iets
density
esp
charges
fukui
resp
bond_order
interaction_energy
fragment_scan
conformer_search
adsorption_search
benchmark
postprocess
plot
```

Validator warns on unknown values; SKILL.md recommends these exact names.

### Pruning tiers

| Tier | Meaning | Examples |
|------|---------|----------|
| `core` | Must be preserved | `chembook.json`, extracted CSV/NPZ, final XYZ, input files |
| `logs` | Human-readable text logs | `detailed.out`, `OUTCAR`, `xtb.out` |
| `recomputable` | Large, recomputable bulk | `WAVECAR`, `CHGCAR`, `*.restart` |
| `scratch` | Temporary files | `tmp/`, `*.tmp`, `scratch/` |

`chembook prune --dry-run` and `--tier recomputable` log every action in `cleanup.log`.

### Directory naming guidelines (soft)

No hard rule. Use whichever dimension is most stable for the study:

- System-focused: `system / method / job_type`
- Benchmark-focused: `benchmark / system / method`
- Campaign-focused: `campaign / job_type / system` or `campaign / site_method`
- Generated many jobs: `j0001_siteA_z2.5/`

Avoid: dates, `new/`, `final/`, `tmp_good/`.

### CLI v0.1 priority

```text
chembook init
  chembook run --type <jobtype> -- <cmd>
  chembook scan
  chembook validate
  chembook table
  chembook extract
  chembook convert
  chembook plot
  chembook prune --dry-run
  chembook migrate
```

### Extractor priority

High: DFTB+, xtb, Psi4, ORCA, pySCF
Medium: GPAW, CP2K, LAMMPS
Low: MOPAC, QUICK, ALAMODE

Generic fallback: parse any plain text log for energy and timing.

### Files to create now

1. `py/chembook/schema.py` – Pydantic models for the v0 schema.
2. `py/chembook/core.py` – read/write `chembook.json`, walk nodes, id collision check.
3. `py/chembook/cli.py` – `init`, `run`, `scan`, `validate`, `table`, `extract`, `convert`, `plot`, `prune`, `migrate`.
4. `py/chembook/extractors/` – start with `dftb.py`, `xtb.py`, and a generic fallback.
5. `py/chembook/formats/csv_npz.py` – bidirectional conversion with metadata.
6. `py/chembook/formats/plot.py` – p5.js HTML generation.
7. `py/tasks/base.py` – fix the missing `base.py` import; define `ScanResult`, `RelaxResult`, `InteractionEnergyResult`, and `VibResult`.
8. `doc/ChemBook/SKILL.md` – AI guidelines.

## Open design decisions (only these remain)

1. **ID length**: 12 hex characters is recommended; do you want 8 (more typable) or 16 (more future-proof)?
2. **Working directory in JSON**: include `provenance.cwd` by default? It helps debugging but embeds local paths.
3. **Schema strictness**: should the validator warn or fail on unknown `job.type` and unknown top-level keys? I recommend warn.
4. **First implementation focus**: do you want me to start with the `chembook init`/`run`/`scan`/`validate` CLI skeleton, or with the DFTB+/xtb extractors?