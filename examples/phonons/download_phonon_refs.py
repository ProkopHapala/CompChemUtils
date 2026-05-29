#!/usr/bin/env python3
"""
download_phonon_refs.py
=======================
CLI tool to download phonon reference data for Si and diamond from:
  - Materials Project (computed DFT phonons via mp-api)
  - phonondb (Atsushi Togo's phonon database via WMD-group mirror)
  - Mendeley Data (MTP machine-learning potential for Si/diamond)

Usage:
  python download_phonon_refs.py mp --api-key YOUR_KEY --material-id mp-149 --outfile si_mp_phonon.json
  python download_phonon_refs.py mp --api-key YOUR_KEY --material-id mp-66  --outfile diamond_mp_phonon.json
  python download_phonon_refs.py phonondb --material-id mp-149 --outdir ./phonondb_si
  python download_phonon_refs.py mendeley --doi 10.17632/6tjhd74t5r --outdir ./mtp_data
"""

import argparse
import json
import os
import sys
import subprocess
import tarfile
import shutil
import urllib.request

# ------------------------------------------------------------------
# Materials Project downloader
# ------------------------------------------------------------------
def download_mp_phonon(api_key: str, material_id: str, outfile: str):
    """Download phonon band structure from Materials Project API."""
    try:
        from mp_api.client import MPRester
    except ImportError:
        print("ERROR: mp-api not installed. Install with: pip install mp-api")
        sys.exit(1)

    print(f"[MP] Connecting to Materials Project API for {material_id} ...")
    with MPRester(api_key) as mpr:
        # Fetch phonon band structure
        try:
            phonon_bs = mpr.materials.phonon.get_bandstructure_from_material_id(
                material_id=material_id, phonon_method="dfpt"
            )
        except Exception as e:
            print(f"ERROR fetching phonon band structure: {e}")
            sys.exit(1)

        if not phonon_bs:
            print(f"WARNING: No phonon data found for {material_id}")
            sys.exit(1)

        # Convert to phononwebsite JSON format
        phonon_dict = phonon_bs.to_pmg().as_phononwebsite()
        phonon_dict["material_id"] = material_id
        phonon_dict["source"] = "Materials Project (DFPT)"

        with open(outfile, "w") as f:
            json.dump(phonon_dict, f, indent=2)
        print(f"[MP] Saved phonon data to {outfile}")

        # Also try to fetch phonon DOS
        try:
            ph_dos = mpr.materials.phonon.get_dos_by_material_id(material_id)
            dos_file = outfile.replace(".json", "_dos.json")
            dos_dict = {
                "material_id": material_id,
                "frequencies": ph_dos.frequencies.tolist(),
                "densities": ph_dos.densities.tolist(),
                "source": "Materials Project (DFPT)"
            }
            with open(dos_file, "w") as f:
                json.dump(dos_dict, f, indent=2)
            print(f"[MP] Saved phonon DOS to {dos_file}")
        except Exception as e:
            print(f"[MP] Could not fetch DOS: {e}")


# ------------------------------------------------------------------
# phonondb downloader (via WMD-group GitHub mirror)
# ------------------------------------------------------------------
def download_phonondb(material_id: str, outdir: str, phonondb_dir: str = None):
    """Download phonon data from phonondb via WMD-group mirror.

    The phononDB repository must be cloned externally (see DEPEND.md).
    Set phonondb_dir via --phonondb-dir argument, PHONONDB_DIR env var,
    or phonon_config.json -> tools.phonondb_dir.
    """
    # Resolve phonondb_dir
    if not phonondb_dir:
        phonondb_dir = os.environ.get("PHONONDB_DIR", "")
    if not phonondb_dir:
        # Try config file
        config_path = "phonon_config.json"
        if os.path.exists(config_path):
            with open(config_path) as f:
                cfg = json.load(f)
            phonondb_dir = cfg.get("tools", {}).get("phonondb_dir", "")

    if not phonondb_dir:
        print("ERROR: phonondb repository directory not set.")
        print("Options:")
        print("  1. Pass --phonondb-dir /path/to/phononDB_repo")
        print("  2. Set PHONONDB_DIR environment variable")
        print("  3. Add 'phonondb_dir' to phonon_config.json -> tools")
        print("See DEPEND.md for setup instructions.")
        sys.exit(1)

    if not os.path.isdir(phonondb_dir):
        print(f"ERROR: phonondb directory not found: {phonondb_dir}")
        print("Clone the repository outside this repo:")
        print("  git clone https://github.com/WMD-group/phononDB.git /path/to/phononDB_repo")
        sys.exit(1)

    repo_dir = phonondb_dir
    print(f"[phonondb] Using external repo at {repo_dir}")

    # Extract tar files
    tar_dir = os.path.join(repo_dir, "phonon_db_tarred")
    if not os.path.isdir(tar_dir):
        print(f"ERROR: Expected tar directory not found: {tar_dir}")
        sys.exit(1)

    extract_dir = os.path.join(outdir, "extracted")
    os.makedirs(extract_dir, exist_ok=True)

    print(f"[phonondb] Extracting tar files to {extract_dir} ...")
    tar_files = [f for f in os.listdir(tar_dir) if f.endswith(".tar.gz") or f.endswith(".tar.lzma")]
    if not tar_files:
        print("ERROR: No .tar.gz or .tar.lzma files found in phonon_db_tarred/")
        sys.exit(1)

    for tf in tar_files:
        tf_path = os.path.join(tar_dir, tf)
        try:
            if tf.endswith(".tar.gz"):
                with tarfile.open(tf_path, "r:gz") as tar:
                    tar.extractall(path=extract_dir)
            elif tf.endswith(".tar.lzma"):
                # Python tarfile does not support lzma directly in all versions
                import lzma
                with lzma.open(tf_path, "rb") as lz:
                    with tarfile.open(fileobj=lz, mode="r:") as tar:
                        tar.extractall(path=extract_dir)
        except Exception as e:
            print(f"WARNING: Could not extract {tf}: {e}")

    # Build lookup table
    lookup_script = os.path.join(repo_dir, "create_lookup_json.py")
    lookup_file = os.path.join(repo_dir, "lookup_table.json")
    if os.path.exists(lookup_script) and not os.path.exists(lookup_file):
        print("[phonondb] Building lookup table ...")
        try:
            subprocess.run([sys.executable, lookup_script], cwd=repo_dir, check=True)
        except subprocess.CalledProcessError as e:
            print(f"WARNING: lookup table creation failed: {e}")

    # Search for material_id in extracted data
    found = False
    for root, dirs, files in os.walk(extract_dir):
        if material_id in root:
            dest = os.path.join(outdir, material_id)
            if os.path.exists(dest):
                shutil.rmtree(dest)
            shutil.copytree(root, dest)
            print(f"[phonondb] Found and copied data for {material_id} -> {dest}")
            found = True
            break

    if not found:
        for root, dirs, files in os.walk(extract_dir):
            for f in files:
                if material_id in f:
                    dest = os.path.join(outdir, material_id)
                    os.makedirs(dest, exist_ok=True)
                    shutil.copy2(os.path.join(root, f), dest)
                    print(f"[phonondb] Found file matching {material_id}: {f}")
                    found = True
        if not found:
            print(f"WARNING: Could not find {material_id} in phonondb. "
                  "The material may not be in the 2018-04-17 snapshot.")


# ------------------------------------------------------------------
# Mendeley Data downloader (public datasets)
# ------------------------------------------------------------------
def download_mendeley(doi: str, outdir: str):
    """Download files from a public Mendeley Data dataset by DOI."""
    # Mendeley DOI format: 10.17632/<dataset_id>
    parts = doi.split("/")
    if len(parts) < 2:
        print("ERROR: DOI should be in format 10.17632/<dataset_id>")
        sys.exit(1)
    dataset_id = parts[-1]

    base_url = "https://api.data.mendeley.com"
    os.makedirs(outdir, exist_ok=True)

    print(f"[Mendeley] Fetching dataset metadata for {dataset_id} ...")
    meta_url = f"{base_url}/datasets/{dataset_id}"
    try:
        with urllib.request.urlopen(meta_url, timeout=30) as r:
            meta = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        print(f"ERROR fetching dataset metadata: {e}")
        print("Note: Public datasets may require a Mendeley Data account token.")
        sys.exit(1)

    print(f"[Mendeley] Dataset: {meta.get('name', 'N/A')}")

    # Get files list
    files_url = f"{base_url}/datasets/{dataset_id}/files"
    try:
        with urllib.request.urlopen(files_url, timeout=30) as r:
            files = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        print(f"ERROR fetching file list: {e}")
        sys.exit(1)

    if not files:
        print("WARNING: No files found in dataset.")
        return

    for fmeta in files:
        fname = fmeta.get("filename", "unknown")
        fuuid = fmeta.get("id")
        content = fmeta.get("content_details", {})
        download_url = content.get("download_url")

        if not download_url:
            # Try redirect endpoint
            download_url = f"{base_url}/datasets/{dataset_id}/files/{fuuid}/download"

        out_path = os.path.join(outdir, fname)
        print(f"[Mendeley] Downloading {fname} ...")
        try:
            with urllib.request.urlopen(download_url, timeout=120) as r, open(out_path, "wb") as f:
                shutil.copyfileobj(r, f)
            print(f"[Mendeley] Saved {out_path} ({os.path.getsize(out_path)} bytes)")
        except Exception as e:
            print(f"WARNING: Failed to download {fname}: {e}")


# ------------------------------------------------------------------
# CLI entry point
# ------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Download phonon reference data from public databases"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # MP subcommand
    mp_parser = subparsers.add_parser("mp", help="Download from Materials Project")
    mp_parser.add_argument("--api-key", required=True, help="Materials Project API key")
    mp_parser.add_argument("--material-id", default="mp-149",
                           help="MP material ID (default: mp-149 for Si)")
    mp_parser.add_argument("--outfile", default="mp_phonon.json",
                           help="Output JSON file")

    # phonondb subcommand
    pdb_parser = subparsers.add_parser("phonondb", help="Download from phonondb")
    pdb_parser.add_argument("--material-id", default="mp-149",
                            help="MP material ID to search for (default: mp-149)")
    pdb_parser.add_argument("--outdir", default="./phonondb_data",
                            help="Output directory")
    pdb_parser.add_argument("--phonondb-dir", default=None,
                            help="Path to external phononDB_repo (default: env PHONONDB_DIR or phonon_config.json)")

    # Mendeley subcommand
    men_parser = subparsers.add_parser("mendeley", help="Download from Mendeley Data")
    men_parser.add_argument("--doi", default="10.17632/6tjhd74t5r",
                            help="Mendeley Data DOI (default: Si/diamond MTP dataset)")
    men_parser.add_argument("--outdir", default="./mendeley_data",
                            help="Output directory")

    args = parser.parse_args()

    if args.command == "mp":
        download_mp_phonon(args.api_key, args.material_id, args.outfile)
    elif args.command == "phonondb":
        download_phonondb(args.material_id, args.outdir, args.phonondb_dir)
    elif args.command == "mendeley":
        download_mendeley(args.doi, args.outdir)


if __name__ == "__main__":
    main()
