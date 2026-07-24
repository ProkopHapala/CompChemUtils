"""
Core ChemBook utilities: ID generation, symlink-aware path resolution,
node read/write, tree walking.
"""
import os
import json
import secrets
import time
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path

CHEMBOOK_FILENAME = "chembook.json"


def generate_id(root_dir=None, existing_ids=None):
    """
    Generate a 12-char hex ID. If root_dir is given, check for collisions
    against all existing chembook.json files in that tree.
    """
    if existing_ids is None and root_dir is not None:
        existing_ids = set()
        for _, data in walk_nodes(root_dir):
            if isinstance(data, dict) and "chembook" in data and "id" in data["chembook"]:
                existing_ids.add(data["chembook"]["id"])

    if existing_ids is None:
        existing_ids = set()

    while True:
        new_id = secrets.token_hex(6)  # 12 hex chars
        if new_id not in existing_ids:
            return new_id


def resolve_true_path(path):
    """
    Resolve a path, detecting symlink traversal.
    Returns (logical_path, real_path, symlink_traversed).
    - logical_path: the path as given (absolute, may contain symlinks)
    - real_path: os.path.realpath() — fully resolved physical path
    - symlink_traversed: True if any component of the path is a symlink
    """
    abs_path = os.path.abspath(path)
    real_path = os.path.realpath(abs_path)
    symlink_traversed = abs_path != real_path
    return abs_path, real_path, symlink_traversed


def get_git_commit():
    """Try to get current git commit hash. Returns None if not in a git repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
            cwd=os.getcwd()
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def now_iso():
    """Current UTC timestamp in ISO 8601 with microseconds."""
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')


def read_node(dirpath):
    """
    Read chembook.json from dirpath.
    Returns (data_dict, error_or_None).
    """
    filepath = os.path.join(dirpath, CHEMBOOK_FILENAME)
    if not os.path.isfile(filepath):
        return None, f"No {CHEMBOOK_FILENAME} in {dirpath}"
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        return data, None
    except json.JSONDecodeError as e:
        return None, f"Invalid JSON in {filepath}: {e}"


def write_node(dirpath, data):
    """
    Write chembook.json to dirpath.
    Creates the directory if it doesn't exist.
    """
    os.makedirs(dirpath, exist_ok=True)
    filepath = os.path.join(dirpath, CHEMBOOK_FILENAME)
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2, sort_keys=False)
        f.write("\n")
    return filepath


def walk_nodes(root):
    """
    Walk a directory tree, yielding (dirpath, data) for each directory
    that contains a valid chembook.json.
    """
    root = os.path.abspath(root)
    for dirpath, dirnames, filenames in os.walk(root):
        if CHEMBOOK_FILENAME in filenames:
            data, err = read_node(dirpath)
            if data is not None:
                yield dirpath, data
            # else: silently skip invalid JSON — use validate to find them


def find_by_id(root, node_id):
    """
    Find a node by its chembook.id within the root tree.
    Returns (dirpath, data) or (None, None).
    """
    for dirpath, data in walk_nodes(root):
        if isinstance(data, dict) and data.get("chembook", {}).get("id") == node_id:
            return dirpath, data
    return None, None


def check_id_unique(root, node_id):
    """
    Check that node_id does not already exist in the root tree.
    Returns True if unique, False if collision.
    """
    dirpath, _ = find_by_id(root, node_id)
    return dirpath is None


def update_node_status(dirpath, status, duration_sec=None, exit_code=None,
                       started=None, finished=None, extra_results=None):
    """
    Update the status (and optionally timing/results) of an existing node.
    Reads, modifies, and writes back the chembook.json.
    """
    data, err = read_node(dirpath)
    if err:
        raise FileNotFoundError(err)

    data["chembook"]["status"] = status

    if duration_sec is not None:
        data["provenance"]["duration_sec"] = duration_sec
    if exit_code is not None:
        data["provenance"]["exit_code"] = exit_code
    if started is not None:
        data["provenance"]["started"] = started
    if finished is not None:
        data["provenance"]["finished"] = finished

    if extra_results:
        if "results" not in data:
            data["results"] = {}
        data["results"].update(extra_results)

    write_node(dirpath, data)
    return data


def run_command_and_record(command, cwd=None, job_type="single_point",
                           n_atoms=0, elements=None, code="unknown",
                           name=None, root_dir=None):
    """
    Run a command, capture provenance, and write/update chembook.json.
    This is the core of `chembook run`.

    Parameters:
        command: list of strings (the command to run)
        cwd: working directory (where chembook.json will be written)
        job_type: e.g. 'relax', 'rigid_scan', etc.
        n_atoms: number of atoms in the system
        elements: dict of element->count
        code: QC code name (lowercase)
        name: optional job name
        root_dir: project root for ID collision checking (default: cwd)

    Returns:
        (exit_code, duration_sec, node_id)
    """
    import sys

    if cwd is None:
        cwd = os.getcwd()
    if root_dir is None:
        root_dir = cwd
    if elements is None:
        elements = {}

    # Resolve paths (symlink awareness)
    logical_cwd, real_cwd, symlink_traversed = resolve_true_path(cwd)

    # Generate unique ID
    node_id = generate_id(root_dir=root_dir)

    # Build command string
    command_str = " ".join(command) if isinstance(command, list) else str(command)

    # Create skeleton with status=pending
    from .schema import create_skeleton
    node = create_skeleton(
        id=node_id,
        job_type=job_type,
        n_atoms=n_atoms,
        elements=elements,
        code=code,
        command=command_str,
        name=name,
        status="pending",
        hostname=socket.gethostname(),
        cwd=logical_cwd,
        real_path=real_cwd,
        symlink_traversed=symlink_traversed,
    )

    # Write pending node before execution
    write_node(cwd, node)

    # Execute
    started_iso = now_iso()
    start_ns = time.perf_counter_ns()

    result = subprocess.run(command, cwd=cwd, capture_output=False)

    end_ns = time.perf_counter_ns()
    finished_iso = now_iso()
    duration_sec = (end_ns - start_ns) / 1e9

    # Update node with results
    status = "done" if result.returncode == 0 else "failed"
    update_node_status(
        cwd, status,
        duration_sec=duration_sec,
        exit_code=result.returncode,
        started=started_iso,
        finished=finished_iso,
    )

    return result.returncode, duration_sec, node_id
