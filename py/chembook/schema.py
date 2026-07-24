"""
ChemBook v0 schema — dict-based validation, no external dependencies.

Compulsory fields are minimal. Everything else is optional.
The validator returns (errors, warnings); errors mean the node is non-compliant,
warnings mean something looks suspicious but is tolerated.
"""
import re

SCHEMA_VERSION = "chembook.job.v0"

VALID_STATUSES = {"pending", "running", "done", "failed", "pruned"}

RECOMMENDED_JOB_TYPES = {
    "single_point", "relax", "rigid_scan", "relaxed_scan", "neb", "md",
    "vibrations", "phonons", "afm", "stm", "iets", "density", "esp",
    "charges", "fukui", "resp", "bond_order", "interaction_energy",
    "fragment_scan", "conformer_search", "adsorption_search",
    "benchmark", "postprocess", "plot",
}

ID_PATTERN = re.compile(r'^[0-9a-f]{8,16}$')

COMPULSORY_FIELDS = {
    "chembook.schema":     "Schema identifier, e.g. 'chembook.job.v0'",
    "chembook.id":         "12-char hex unique identifier",
    "chembook.created":    "ISO 8601 timestamp with timezone",
    "chembook.status":     "One of: " + ", ".join(sorted(VALID_STATUSES)),
    "job.type":            "Job type string (see RECOMMENDED_JOB_TYPES)",
    "system.n_atoms":      "Total number of atoms (int)",
    "system.elements":     "Dict of element->count, e.g. {'H': 2, 'O': 1}",
    "method.code":         "QC code name (lowercase), e.g. 'dftb+'",
    "provenance.command":  "Exact command that launched the job",
}

# Fields compulsory only when status is done or failed
COMPULSORY_WHEN_FINISHED = {
    "provenance.duration_sec":  "Wall-clock time in seconds (float, from perf_counter_ns)",
    "provenance.exit_code":     "Process exit code (int)",
}


def _get_nested(d, dotted_key):
    parts = dotted_key.split(".")
    v = d
    for p in parts:
        if not isinstance(v, dict) or p not in v:
            return None, False
        v = v[p]
    return v, True


def _has_nested(d, dotted_key):
    _, found = _get_nested(d, dotted_key)
    return found


def validate(data):
    """
    Validate a chembook.json dict.
    Returns (errors: list[str], warnings: list[str]).
    """
    errors = []
    warnings = []

    if not isinstance(data, dict):
        return ["Top-level value must be a JSON object"], []

    # Check compulsory fields
    for field, desc in COMPULSORY_FIELDS.items():
        if not _has_nested(data, field):
            errors.append(f"Missing compulsory field: {field} — {desc}")

    # Check conditional compulsory fields (when finished)
    status_val, status_found = _get_nested(data, "chembook.status")
    if status_found and status_val in ("done", "failed"):
        for field, desc in COMPULSORY_WHEN_FINISHED.items():
            if not _has_nested(data, field):
                errors.append(f"Missing field {field} (required when status='{status_val}'): {desc}")

    # Validate chembook.schema
    schema_val, schema_found = _get_nested(data, "chembook.schema")
    if schema_found and schema_val != SCHEMA_VERSION:
        warnings.append(f"chembook.schema is '{schema_val}', expected '{SCHEMA_VERSION}'. Run chembook migrate.")

    # Validate chembook.id format
    id_val, id_found = _get_nested(data, "chembook.id")
    if id_found and not ID_PATTERN.match(str(id_val)):
        errors.append(f"chembook.id '{id_val}' does not match hex pattern {ID_PATTERN.pattern}")

    # Validate chembook.status
    if status_found and status_val not in VALID_STATUSES:
        errors.append(f"chembook.status '{status_val}' not in {VALID_STATUSES}")

    # Validate job.type (warn, not fail)
    job_type, jt_found = _get_nested(data, "job.type")
    if jt_found and job_type not in RECOMMENDED_JOB_TYPES:
        warnings.append(f"job.type '{job_type}' not in recommended vocabulary. Consider using one of: {sorted(RECOMMENDED_JOB_TYPES)}")

    # Validate system.n_atoms is int
    n_atoms, na_found = _get_nested(data, "system.n_atoms")
    if na_found:
        if not isinstance(n_atoms, int) or n_atoms <= 0:
            errors.append(f"system.n_atoms must be a positive integer, got {n_atoms}")

    # Validate system.elements is dict of str->int
    elements, el_found = _get_nested(data, "system.elements")
    if el_found:
        if not isinstance(elements, dict):
            errors.append(f"system.elements must be a dict, got {type(elements).__name__}")
        else:
            for k, v in elements.items():
                if not isinstance(v, int) or v <= 0:
                    errors.append(f"system.elements['{k}'] must be a positive integer, got {v}")

    # Validate method.code is lowercase string
    code, code_found = _get_nested(data, "method.code")
    if code_found and isinstance(code, str) and code != code.lower():
        warnings.append(f"method.code '{code}' should be lowercase")

    # Validate duration_sec is float when present
    duration, dur_found = _get_nested(data, "provenance.duration_sec")
    if dur_found and not isinstance(duration, (int, float)):
        errors.append(f"provenance.duration_sec must be a number, got {type(duration).__name__}")

    return errors, warnings


def create_skeleton(id, job_type, n_atoms, elements, code, command,
                    name=None, status="pending", created=None,
                    hostname=None, cwd=None, real_path=None,
                    symlink_traversed=None):
    """
    Create a minimal compliant chembook.json dict with compulsory fields filled.
    Optional fields are included only if provided.
    """
    from datetime import datetime, timezone
    if created is None:
        created = datetime.now(timezone.utc).isoformat(timespec='microseconds')

    node = {
        "chembook": {
            "schema": SCHEMA_VERSION,
            "id": id,
            "created": created,
            "status": status,
        },
        "job": {
            "type": job_type,
        },
        "system": {
            "n_atoms": n_atoms,
            "elements": elements,
        },
        "method": {
            "code": code,
        },
        "provenance": {
            "command": command,
        },
    }

    if name:
        node["job"]["name"] = name

    if hostname:
        node["provenance"]["hostname"] = hostname
    if cwd:
        node["provenance"]["cwd"] = cwd
    if real_path:
        node["provenance"]["real_path"] = real_path
    if symlink_traversed is not None:
        node["provenance"]["symlink_traversed"] = symlink_traversed

    return node
