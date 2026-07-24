"""
ChemBook CLI — init, run, validate, scan commands.

Usage:
    python -m py.chembook init <dir> --type relax --n-atoms 3 --elements H:2,O:1 --code dftb+
    python -m py.chembook run --type relax --code dftb+ --n-atoms 3 --elements H:2,O:1 -- python run.py
    python -m py.chembook validate [dir]
    python -m py.chembook scan [dir] [--format table|json]
"""
import sys
import os
import argparse
import json

from . import core
from . import schema


def _parse_elements(s):
    """Parse 'H:2,O:1' -> {'H': 2, 'O': 1}"""
    if isinstance(s, dict):
        return s
    result = {}
    for pair in s.split(","):
        pair = pair.strip()
        if not pair:
            continue
        elem, count = pair.split(":")
        result[elem.strip()] = int(count.strip())
    return result


def cmd_init(args):
    """Create a chembook.json skeleton in the target directory."""
    cwd = os.path.abspath(args.dir)
    os.makedirs(cwd, exist_ok=True)

    # Check if one already exists
    existing, _ = core.read_node(cwd)
    if existing and not args.force:
        print(f"ERROR: {core.CHEMBOOK_FILENAME} already exists in {cwd}. Use --force to overwrite.", file=sys.stderr)
        sys.exit(1)

    # Resolve symlink context
    logical_cwd, real_cwd, symlink_traversed = core.resolve_true_path(cwd)

    # Generate unique ID
    root_dir = args.root_dir if args.root_dir else cwd
    node_id = core.generate_id(root_dir=root_dir)

    # Build command string (what was used to init)
    command_str = f"chembook init {' '.join(sys.argv[2:])}"

    node = schema.create_skeleton(
        id=node_id,
        job_type=args.type,
        n_atoms=args.n_atoms,
        elements=_parse_elements(args.elements) if args.elements else {},
        code=args.code,
        command=command_str,
        name=args.name,
        status="pending",
        hostname=__import__("socket").gethostname(),
        cwd=logical_cwd,
        real_path=real_cwd,
        symlink_traversed=symlink_traversed,
    )

    # Add optional fields
    if args.formula:
        node["system"]["formula"] = args.formula
    if args.method:
        node["method"]["method"] = args.method
    if args.basis:
        node["method"]["basis"] = args.basis

    filepath = core.write_node(cwd, node)
    print(f"Created {filepath}")
    print(f"  id={node_id}  status=pending  type={args.type}  code={args.code}")
    if symlink_traversed:
        print(f"  symlink_traversed: {logical_cwd} -> {real_cwd}")


def cmd_run(args):
    """Run a command, capture provenance, write chembook.json."""
    command = args.command
    # Strip leading '--' if present (argparse REMAINDER may include it)
    if command and command[0] == '--':
        command = command[1:]
    if not command:
        print("ERROR: no command specified. Use -- to separate chembook args from the command.", file=sys.stderr)
        sys.exit(1)

    cwd = os.path.abspath(args.dir) if args.dir else os.getcwd()
    os.makedirs(cwd, exist_ok=True)

    root_dir = args.root_dir if args.root_dir else cwd
    elements = _parse_elements(args.elements) if args.elements else {}

    exit_code, duration_sec, node_id = core.run_command_and_record(
        command=command,
        cwd=cwd,
        job_type=args.type,
        n_atoms=args.n_atoms,
        elements=elements,
        code=args.code,
        name=args.name,
        root_dir=root_dir,
    )

    status = "done" if exit_code == 0 else "failed"
    print(f"\nchembook: id={node_id}  status={status}  exit_code={exit_code}  duration={duration_sec:.6f}s")
    sys.exit(exit_code)


def cmd_validate(args):
    """Validate chembook.json files in a directory tree."""
    root = os.path.abspath(args.dir) if args.dir else os.getcwd()
    n_ok = 0
    n_err = 0
    n_warn = 0

    # Walk all files, including invalid ones
    for dirpath, dirnames, filenames in os.walk(root):
        if core.CHEMBOOK_FILENAME in filenames:
            filepath = os.path.join(dirpath, core.CHEMBOOK_FILENAME)
            data, err = core.read_node(dirpath)
            if err:
                print(f"ERROR: {filepath}: {err}", file=sys.stderr)
                n_err += 1
                continue

            errors, warnings = schema.validate(data)
            if errors:
                for e in errors:
                    print(f"ERROR: {filepath}: {e}", file=sys.stderr)
                n_err += 1
            else:
                n_ok += 1
                if args.verbose:
                    print(f"OK: {filepath}")

            for w in warnings:
                print(f"WARN: {filepath}: {w}", file=sys.stderr)
                n_warn += 1

    print(f"\nSummary: {n_ok} valid, {n_err} with errors, {n_warn} warnings")
    sys.exit(1 if n_err > 0 else 0)


def cmd_scan(args):
    """Walk a directory tree and list all chembook nodes."""
    root = os.path.abspath(args.dir) if args.dir else os.getcwd()

    nodes = []
    for dirpath, data in core.walk_nodes(root):
        cb = data.get("chembook", {})
        job = data.get("job", {})
        sys_info = data.get("system", {})
        method = data.get("method", {})
        prov = data.get("provenance", {})
        results = data.get("results", {})

        nodes.append({
            "dir": dirpath,
            "id": cb.get("id", "?"),
            "status": cb.get("status", "?"),
            "type": job.get("type", "?"),
            "name": job.get("name", ""),
            "code": method.get("code", "?"),
            "n_atoms": sys_info.get("n_atoms", "?"),
            "formula": sys_info.get("formula", ""),
            "duration_sec": prov.get("duration_sec", ""),
            "energy_eV": results.get("energy_eV", ""),
            "converged": results.get("converged", ""),
        })

    if args.format == "json":
        print(json.dumps(nodes, indent=2))
    else:
        # Table format
        if not nodes:
            print(f"No chembook.json nodes found under {root}")
            return

        # Print table
        headers = ["id", "status", "type", "code", "n_atoms", "duration_sec", "dir"]
        widths = {h: max(len(h), max(len(str(n.get(h, ""))) for n in nodes)) for h in headers}

        def print_row(vals):
            parts = []
            for h in headers:
                parts.append(str(vals.get(h, "")).ljust(widths[h]))
            print("  ".join(parts))

        print_row({h: h for h in headers})
        print_row({h: "-" * widths[h] for h in headers})
        for n in nodes:
            print_row(n)

        print(f"\n{len(nodes)} nodes found")


def main():
    parser = argparse.ArgumentParser(
        prog="chembook",
        description="ChemBook — metadata tracking for QC simulations.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # init
    p_init = sub.add_parser("init", help="Create chembook.json skeleton in a directory")
    p_init.add_argument("dir", help="Target directory")
    p_init.add_argument("--type", required=True, help="Job type (relax, rigid_scan, etc.)")
    p_init.add_argument("--n-atoms", type=int, required=True, help="Total number of atoms")
    p_init.add_argument("--elements", required=True, help="Element counts, e.g. 'H:2,O:1'")
    p_init.add_argument("--code", required=True, help="QC code name (lowercase, e.g. 'dftb+')")
    p_init.add_argument("--name", default=None, help="Optional job name")
    p_init.add_argument("--formula", default=None, help="Chemical formula (optional)")
    p_init.add_argument("--method", default=None, help="Method level (e.g. 'SCC-DFTB')")
    p_init.add_argument("--basis", default=None, help="Basis set (e.g. '3ob-3-1')")
    p_init.add_argument("--root-dir", default=None, help="Project root for ID collision checking")
    p_init.add_argument("--force", action="store_true", help="Overwrite existing chembook.json")
    p_init.set_defaults(func=cmd_init)

    # run
    p_run = sub.add_parser("run", help="Run a command and capture provenance")
    p_run.add_argument("--type", default="single_point", help="Job type")
    p_run.add_argument("--code", default="unknown", help="QC code name (lowercase)")
    p_run.add_argument("--n-atoms", type=int, default=0, help="Total number of atoms")
    p_run.add_argument("--elements", default=None, help="Element counts, e.g. 'H:2,O:1'")
    p_run.add_argument("--name", default=None, help="Optional job name")
    p_run.add_argument("--dir", default=None, help="Working directory (default: cwd)")
    p_run.add_argument("--root-dir", default=None, help="Project root for ID collision checking")
    p_run.add_argument("command", nargs=argparse.REMAINDER, help="Command to run (after --)")
    p_run.set_defaults(func=cmd_run)

    # validate
    p_val = sub.add_parser("validate", help="Validate chembook.json files in a tree")
    p_val.add_argument("dir", nargs="?", default=".", help="Directory to validate (default: cwd)")
    p_val.add_argument("-v", "--verbose", action="store_true", help="Print OK nodes too")
    p_val.set_defaults(func=cmd_validate)

    # scan
    p_scan = sub.add_parser("scan", help="List all chembook nodes in a tree")
    p_scan.add_argument("dir", nargs="?", default=".", help="Root directory to scan")
    p_scan.add_argument("--format", choices=["table", "json"], default="table", help="Output format")
    p_scan.set_defaults(func=cmd_scan)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
