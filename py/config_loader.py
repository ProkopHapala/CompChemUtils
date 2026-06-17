"""
py/config_loader.py — Centralized, machine-independent configuration loader.

Usage:
    from py import config_loader as cfg
    sk_path = cfg.require_path('sk_dir')       # crash if missing
    dftb_bin = cfg.get_tool('dftb_bin', default='dftb+')

Setup:
    1. Copy machine_config.template.yaml → machine_config.yaml (repo root)
    2. Fill in your local paths
    3. Never commit machine_config.yaml (it is git-ignored)
"""

import json
import os
from typing import Any, Optional

# Prefer YAML; fallback to JSON if pyyaml is not installed
try:
    import yaml
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False


# === discover repo root ===================================================

_REPO_ROOT: Optional[str] = None

def _find_repo_root() -> str:
    """Locate repo root by searching upward for machine_config.template.yaml."""
    global _REPO_ROOT
    if _REPO_ROOT is not None:
        return _REPO_ROOT
    start = os.path.dirname(os.path.abspath(__file__))
    path = start
    while path != os.path.dirname(path):
        if os.path.isfile(os.path.join(path, 'machine_config.template.yaml')):
            _REPO_ROOT = path
            return path
        path = os.path.dirname(path)
    raise FileNotFoundError(
        f"Could not find repo root (no machine_config.template.yaml found). Started search from {start}"
    )


# === load config =========================================================

_config_cache: Optional[dict] = None


def _load_file(path: str) -> dict:
    """Load YAML if pyyaml is available, otherwise JSON."""
    with open(path) as f:
        if _HAS_YAML:
            return yaml.safe_load(f) or {}
        return json.load(f)


def load_config() -> dict:
    """Load machine_config.yaml (or .json fallback); raise FileNotFoundError with clear instructions if missing."""
    global _config_cache
    if _config_cache is not None:
        return _config_cache

    root = _find_repo_root()
    cfg_path_yaml = os.path.join(root, 'machine_config.yaml')
    cfg_path_json = os.path.join(root, 'machine_config.json')

    if os.path.isfile(cfg_path_yaml):
        _config_cache = _load_file(cfg_path_yaml)
        return _config_cache
    if os.path.isfile(cfg_path_json):
        _config_cache = _load_file(cfg_path_json)
        return _config_cache

    template = os.path.join(root, 'machine_config.template.yaml')
    raise FileNotFoundError(
        f"\n{'='*60}\n"
        f"  Machine-specific config NOT FOUND:\n"
        f"    {cfg_path_yaml}\n\n"
        f"  Please copy the template and fill in your local paths:\n"
        f"    cp {template} {cfg_path_yaml}\n\n"
        f"  Then edit {cfg_path_yaml} with your Slater-Koster paths,\n"
        f"  binary locations, and other machine-specific settings.\n"
        f"{'='*60}"
    )


def reload_config() -> dict:
    """Force reload from disk (useful after editing machine_config.yaml)."""
    global _config_cache
    _config_cache = None
    return load_config()


# === helpers =============================================================

def _get_nested(d: dict, key: str) -> Any:
    """Dot-notation lookup: 'data_dirs.phonondb_dir' → d['data_dirs']['phonondb_dir']."""
    parts = key.split('.')
    val = d
    for p in parts:
        if not isinstance(val, dict):
            raise KeyError(key)
        if p not in val:
            raise KeyError(key)
        val = val[p]
    return val


def _env_override(key: str) -> Optional[str]:
    """Check for COMPCHEM_<UPPER_KEY> environment variable."""
    env_key = 'COMPCHEM_' + key.upper().replace('.', '_')
    return os.environ.get(env_key)


# === public API ==========================================================

def get(key: str, default: Any = None) -> Any:
    """Get a raw config value by dot-notation key.
    Environment variable COMPCHEM_<KEY> overrides YAML value.
    Returns default (may be None) if key is absent.
    """
    env = _env_override(key)
    if env is not None:
        return env
    cfg = load_config()
    try:
        return _get_nested(cfg, key)
    except KeyError:
        return default


def require(key: str) -> Any:
    """Get a config value; raise ValueError with clear message if missing."""
    val = get(key)
    if val is None:
        raise ValueError(
            f"Config key '{key}' is missing from machine_config.yaml.\n"
            f"Please add it to machine_config.yaml (see template for examples)."
        )
    return val


def get_tool(name: str, default: Optional[str] = None) -> str:
    """Get path/name of an external tool binary.
    Falls back to `default` or bare name if not configured.
    """
    val = get(f"tools.{name}")
    if val is not None:
        return str(val)
    if default is not None:
        return default
    return name  # bare name (assumes binary is in PATH)


def require_tool(name: str) -> str:
    """Get tool path; fail loudly if missing and not in PATH."""
    val = get(f"tools.{name}")
    if val is not None:
        return str(val)
    # Try PATH
    import shutil
    found = shutil.which(name)
    if found:
        return found
    raise ValueError(
        f"Tool '{name}' not configured in machine_config.yaml (tools.{name}) "
        f"and not found in PATH.\n"
        f"Please set tools.{name} in machine_config.yaml or ensure it is in PATH."
    )


def get_path(key: str, default: Optional[str] = None) -> Optional[str]:
    """Get a filesystem path (tools, sk_dir, data_dirs).
    Expands ~ and environment variables.
    """
    val = get(key)
    if val is None:
        return default
    p = os.path.expandvars(os.path.expanduser(str(val)))
    return p


def require_path(key: str) -> str:
    """Get a filesystem path and verify it exists.
    Raises FileNotFoundError with clear instructions if missing.
    """
    p = get_path(key)
    if p is None:
        raise FileNotFoundError(
            f"Config path '{key}' is not set in machine_config.yaml.\n"
            f"Please add it to machine_config.yaml (see template for examples)."
        )
    if not os.path.exists(p):
        raise FileNotFoundError(
            f"Config path '{key}' points to a non-existent location:\n"
            f"  {p}\n"
            f"Please fix machine_config.yaml."
        )
    return p
