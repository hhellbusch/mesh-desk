"""Remembered radios stay on this computer and only accept MAC addresses."""

import json
from pathlib import Path

from mesh_desk.known import load_radios, remember_radio


def test_remember_keeps_one_mac(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    remember_radio("not-a-radio", "nope")
    assert not (tmp_path / "mesh-desk" / "radios.json").exists()
    # Split so the source tree does not contain a full address.
    desk = "aa:bb:cc:dd:ee:" + "ff"
    remember_radio(desk, "Desk")
    remember_radio(desk.upper(), "Again")
    assert load_radios() == [{"name": "Desk", "address": desk.upper()}]


def test_bad_file_loads_as_empty(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    path = tmp_path / "mesh-desk"
    path.mkdir()
    (path / "radios.json").write_text("{")
    assert load_radios() == []
    other = "11:22:33:44:55:" + "66"
    (path / "radios.json").write_text(
        json.dumps([{"name": "ok", "address": "not-a-mac"}, "nope", {"address": other}])
    )
    assert load_radios() == [{"name": other, "address": other}]


def test_source_tree_has_no_bluetooth_address() -> None:
    import re

    mac = re.compile(r"(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}")
    root = Path(__file__).resolve().parents[1]
    suffixes = {".py", ".md", ".toml", ".desktop", ".txt", ".yml"}
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in suffixes:
            continue
        if any(part in {".git", ".pytest_cache", "__pycache__"} for part in path.parts):
            continue
        match = mac.search(path.read_text(errors="ignore"))
        assert match is None, f"{path} contains {match.group(0)}"
