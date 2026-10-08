"""Remembered radios stay on this computer and only accept MAC addresses."""

import json
from pathlib import Path

from mesh_desk.known import auto_radio, load_radios, remember_radio, set_auto_connect


def test_remember_keeps_one_mac(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    remember_radio("not-a-radio", "nope")
    assert not (tmp_path / "mesh-desk" / "radios.json").exists()
    # Split so the source tree does not contain a full address.
    desk = "aa:bb:cc:dd:ee:" + "ff"
    remember_radio(desk, "Desk")
    remember_radio(desk.upper(), "Again")
    assert load_radios() == [{"name": "Desk", "address": desk.upper(), "auto": False}]


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
    assert load_radios() == [{"name": other, "address": other, "auto": False}]


def test_only_one_radio_autoconnects(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    first = "aa:bb:cc:dd:ee:" + "ff"
    second = "11:22:33:44:55:" + "66"
    remember_radio(first, "Desk")
    remember_radio(second, "Other")
    set_auto_connect(first, True)
    chosen = auto_radio()
    assert chosen is not None
    assert chosen["address"] == first.upper()
    set_auto_connect(second, True)
    flags = {item["address"]: item["auto"] for item in load_radios()}
    assert flags[second.upper()] is True
    assert flags[first.upper()] is False
    set_auto_connect(second, False)
    assert auto_radio() is None
    set_auto_connect("not-a-radio", True)
    assert auto_radio() is None


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
