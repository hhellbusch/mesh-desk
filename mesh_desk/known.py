"""Bluetooth radios remembered on this computer.

The list lives in $XDG_CONFIG_HOME/mesh-desk/radios.json. It is not part of
the source tree and is never written by the repository.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

_MAC = re.compile(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")


def config_dir() -> Path:
    root = os.environ.get("XDG_CONFIG_HOME")
    base = Path(root) if root else Path.home() / ".config"
    path = base / "mesh-desk"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _path() -> Path:
    return config_dir() / "radios.json"


def load_radios() -> list[dict]:
    path = _path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return []
    found = []
    if not isinstance(data, list):
        return found
    for item in data:
        if not isinstance(item, dict):
            continue
        address = str(item.get("address") or "").strip()
        if not _MAC.match(address):
            continue
        name = str(item.get("name") or "").strip() or address
        found.append({"name": name, "address": address.upper(), "auto": bool(item.get("auto"))})
    return found


def _write(radios: list[dict]) -> None:
    _path().write_text(json.dumps(radios, indent=2) + "\n")


def remember_radio(address: str, name: str = "") -> None:
    address = address.strip().upper()
    if not _MAC.match(address):
        return
    radios = load_radios()
    for item in radios:
        if item["address"] == address:
            return
    label = name.strip() or address
    radios.insert(0, {"name": label, "address": address, "auto": False})
    _write(radios)


def set_auto_connect(address: str, enabled: bool) -> None:
    """Mark one remembered radio to connect when the app opens. Others are cleared."""
    address = address.strip().upper()
    if not _MAC.match(address):
        return
    radios = load_radios()
    found = False
    for item in radios:
        if item["address"] == address:
            item["auto"] = bool(enabled)
            found = True
        elif enabled:
            item["auto"] = False
    if not found:
        return
    _write(radios)


def auto_radio() -> dict | None:
    for item in load_radios():
        if item.get("auto"):
            return item
    return None
