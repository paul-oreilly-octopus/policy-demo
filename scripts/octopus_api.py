"""Shared Octopus Deploy API helper for the PolicyDemo space.

Reads the API key at runtime from ~/dev/claude/secrets/taniwha.octopus.app/api_key.
Never logs or echoes the key.

Provides both instance-scoped (`/api/...`) and space-scoped (`/api/{spaceId}/...`)
helpers. Space ID is loaded lazily from config/foundation-ids.json — setup-space.py
creates that file as its first effect, after which space-scoped calls work.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

OCTOPUS_SERVER = "https://taniwha.octopus.app"
API_ROOT = f"{OCTOPUS_SERVER}/api"
KEY_FILE = Path.home() / "dev" / "claude" / "secrets" / "taniwha.octopus.app" / "api_key"
CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
FOUNDATION_IDS_FILE = CONFIG_DIR / "foundation-ids.json"

SPACE_NAME = "PolicyDemo"

# ANSI colours
RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[0;33m"
CYAN = "\033[0;36m"
NC = "\033[0m"


def ok(msg: str) -> None:
    print(f"{GREEN}✓{NC} {msg}")


def info(msg: str) -> None:
    print(f"{CYAN}→{NC} {msg}")


def warn(msg: str) -> None:
    print(f"{YELLOW}⚠{NC} {msg}")


def err(msg: str) -> None:
    print(f"{RED}✗{NC} {msg}", file=sys.stderr)


_API_KEY_CACHE: str | None = None


def _api_key() -> str:
    global _API_KEY_CACHE
    if _API_KEY_CACHE is not None:
        return _API_KEY_CACHE
    if not KEY_FILE.exists():
        err(f"API key file not found at {KEY_FILE}")
        sys.exit(1)
    text = KEY_FILE.read_text()
    for line in text.splitlines():
        if line.strip().startswith("value:"):
            _API_KEY_CACHE = line.split(":", 1)[1].strip()
            return _API_KEY_CACHE
    err(f"No 'value:' line in {KEY_FILE}")
    sys.exit(1)


def _request(method: str, url: str, body: dict | None = None) -> Any:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("X-Octopus-ApiKey", _api_key())
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            text = resp.read().decode("utf-8")
            return json.loads(text) if text else None
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace") if e.fp else ""
        err(f"{method} {url} → HTTP {e.code}")
        if body_text:
            print(body_text, file=sys.stderr)
        raise


# ─── Instance-scoped calls (no space ID required) ─────────────────────────────


def iget(path: str) -> Any:
    return _request("GET", f"{API_ROOT}{path}")


def ipost(path: str, body: dict) -> Any:
    return _request("POST", f"{API_ROOT}{path}", body)


def iput(path: str, body: dict) -> Any:
    return _request("PUT", f"{API_ROOT}{path}", body)


def idelete(path: str) -> Any:
    return _request("DELETE", f"{API_ROOT}{path}")


# ─── Space-scoped calls (require space ID) ────────────────────────────────────

_SPACE_ID_CACHE: str | None = None


def space_id() -> str:
    """Resolve the PolicyDemo space ID. Loads from config file if available,
    else queries the API by name. Caches result."""
    global _SPACE_ID_CACHE
    if _SPACE_ID_CACHE is not None:
        return _SPACE_ID_CACHE
    if FOUNDATION_IDS_FILE.exists():
        data = json.loads(FOUNDATION_IDS_FILE.read_text())
        sid = data.get("SpaceId")
        if sid:
            _SPACE_ID_CACHE = sid
            return sid
    # Fall back to API lookup
    for s in iget("/spaces?take=200").get("Items", []):
        if s.get("Name") == SPACE_NAME:
            _SPACE_ID_CACHE = s["Id"]
            return _SPACE_ID_CACHE
    err(f"Space '{SPACE_NAME}' not found. Run setup-space.py first.")
    sys.exit(1)


def _space_base() -> str:
    return f"{API_ROOT}/{space_id()}"


def get(path: str) -> Any:
    return _request("GET", f"{_space_base()}{path}")


def post(path: str, body: dict) -> Any:
    return _request("POST", f"{_space_base()}{path}", body)


def put(path: str, body: dict) -> Any:
    return _request("PUT", f"{_space_base()}{path}", body)


def delete(path: str) -> Any:
    return _request("DELETE", f"{_space_base()}{path}")


# ─── Pagination + lookup helpers ──────────────────────────────────────────────


def get_all(path: str, take: int = 200) -> list[dict]:
    """Page through a space-scoped list endpoint and return all Items."""
    sep = "&" if "?" in path else "?"
    items: list[dict] = []
    skip = 0
    while True:
        chunk = get(f"{path}{sep}skip={skip}&take={take}")
        items.extend(chunk.get("Items", []))
        if len(items) >= chunk.get("TotalResults", 0):
            break
        skip += take
    return items


def find_by_name(path: str, name: str) -> dict | None:
    """Find a resource by Name from a paged space-scoped list endpoint."""
    for item in get_all(path):
        if item.get("Name") == name:
            return item
    return None


def iget_all(path: str, take: int = 200) -> list[dict]:
    """Page through an instance-scoped list endpoint."""
    sep = "&" if "?" in path else "?"
    items: list[dict] = []
    skip = 0
    while True:
        chunk = iget(f"{path}{sep}skip={skip}&take={take}")
        items.extend(chunk.get("Items", chunk.get("DeploymentFreezes", [])))
        if len(items) >= chunk.get("TotalResults", 0):
            break
        skip += take
    return items


# ─── Config I/O ───────────────────────────────────────────────────────────────


def save_ids(file_name: str, data: dict) -> None:
    file_path = CONFIG_DIR / file_name
    file_path.parent.mkdir(parents=True, exist_ok=True)
    # Merge with existing if present
    if file_path.exists():
        existing = json.loads(file_path.read_text())
        existing.update(data)
        data = existing
    file_path.write_text(json.dumps(data, indent=2) + "\n")
    ok(f"saved IDs to {file_path}")


def load_ids(file_name: str) -> dict:
    file_path = CONFIG_DIR / file_name
    if not file_path.exists():
        err(f"IDs file missing: {file_path}")
        sys.exit(1)
    return json.loads(file_path.read_text())
