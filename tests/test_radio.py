"""Radio behavior that must hold with no Bluetooth and no GTK window."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from pubsub import pub

from mesh_desk.radio import (
    RadioSession,
    _format_route,
    _snapshot_values,
    _summarize,
)


class _Churn(dict):
    """Raises the dict-size error the BLE thread can cause, then succeeds."""

    def __init__(self) -> None:
        super().__init__({"a": 1})
        self.calls = 0

    def values(self):
        self.calls += 1
        if self.calls < 3:
            raise RuntimeError("dictionary changed size during iteration")
        return super().values()


def test_snapshot_retries_when_the_node_dict_changes() -> None:
    assert _snapshot_values(_Churn()) == [1]


def test_snapshot_gives_up_instead_of_raising() -> None:
    class Always(dict):
        def values(self):
            raise RuntimeError("dictionary changed size during iteration")

    assert _snapshot_values(Always()) == []
    assert _snapshot_values(None) == []


def test_nodes_skip_bad_records_and_keep_hop_zero() -> None:
    session = RadioSession()
    session.iface = SimpleNamespace(
        nodes={
            "bad": {"user": "not-a-dict", "hopsAway": 1},
            "nameless": {"user": {}, "hopsAway": 1},
            "zero": {"user": {"id": "!zero", "longName": "Zero"}, "hopsAway": 0},
            "far": {
                "user": {"id": "!far", "longName": "Far"},
                "hopsAway": 3,
                "isFavorite": True,
            },
        }
    )
    rows = {row["id"]: row for row in session.nodes()}
    assert set(rows) == {"!zero", "!far"}
    assert rows["!zero"]["hops"] == 0


def test_channels_hide_keys_and_disabled_slots() -> None:
    from meshtastic.protobuf import channel_pb2

    primary = channel_pb2.Channel()
    primary.index = 0
    primary.role = channel_pb2.Channel.Role.PRIMARY
    primary.settings.name = "LongFast"
    primary.settings.psk = bytes([1])

    secret = channel_pb2.Channel()
    secret.index = 1
    secret.role = channel_pb2.Channel.Role.SECONDARY
    secret.settings.name = "Family"
    secret.settings.psk = b"NOT-A-KEY-DO-NOT-SHOW"

    disabled = channel_pb2.Channel()
    disabled.index = 2
    disabled.role = channel_pb2.Channel.Role.DISABLED
    disabled.settings.name = "Old"
    disabled.settings.psk = b"ALSO-HIDDEN"

    session = RadioSession()
    session.iface = SimpleNamespace(localNode=SimpleNamespace(channels=[primary, secret, disabled]))
    found = session.channels()
    rendered = json.dumps(found)
    assert found == [
        {"index": 0, "label": "LongFast (public)"},
        {"index": 1, "label": "Family"},
    ]
    assert "NOT-A-KEY-DO-NOT-SHOW" not in rendered
    assert "ALSO-HIDDEN" not in rendered
    assert "Old" not in rendered


def test_receive_accepts_the_interface_argument() -> None:
    session = RadioSession()
    seen: list[dict] = []
    session.listen(lambda _m: None, lambda: None, lambda: None, seen.append)
    pub.sendMessage(
        "meshtastic.receive",
        packet={
            "fromId": "!abc",
            "toId": "^all",
            "decoded": {
                "portnum": "TEXT_MESSAGE_APP",
                "text": "hi",
                "payload": b"\x00secret-bytes",
            },
        },
        interface=object(),
    )
    from gi.repository import GLib

    context = GLib.MainContext.default()
    while context.pending():
        context.iteration(False)
    assert seen
    assert seen[-1]["extra"] == "hi"
    assert "secret-bytes" not in json.dumps(seen[-1])


def test_summary_truncates_text_and_omits_payload() -> None:
    summary = _summarize(
        {
            "fromId": "!abc",
            "decoded": {"portnum": "TEXT_MESSAGE_APP", "text": "x" * 120, "payload": b"nope"},
        }
    )
    assert summary is not None
    assert summary["extra"].endswith("…")
    assert len(summary["extra"]) == 81
    assert "payload" not in summary
    assert "nope" not in json.dumps(summary)


def test_traceroute_text() -> None:
    iface = SimpleNamespace(nodesByNum={1: {"user": {"longName": "Upstairs"}}})
    direct = _format_route(
        iface,
        {"fromId": "!dest", "decoded": {"traceroute": {"route": []}}},
        "!dest",
    )
    relay = _format_route(
        iface,
        {"fromId": "!dest", "decoded": {"traceroute": {"route": [1]}}},
        "!dest",
    )
    assert direct == "Direct to !dest. No relay in the reply."
    assert relay == "this radio → Upstairs → !dest"
    with pytest.raises(RuntimeError, match="NO_RESPONSE"):
        _format_route(
            iface,
            {"decoded": {"portnum": "ROUTING_APP", "routing": {"errorReason": "NO_RESPONSE"}}},
            "!dest",
        )


def test_save_refuses_when_config_was_not_read() -> None:
    session = RadioSession()
    called: list[str] = []

    def prepare(_node):
        called.append("prepare")
        return [lambda: called.append("write")]

    with pytest.raises(RuntimeError, match="Config has not been read"):
        session.perform_save(prepare, config_loaded=False)
    assert called == []


def test_save_runs_one_transaction() -> None:
    events: list[str] = []

    class Node:
        def beginSettingsTransaction(self) -> None:
            events.append("begin")

        def commitSettingsTransaction(self) -> None:
            events.append("commit")

    session = RadioSession()
    session.iface = SimpleNamespace(localNode=Node())

    def prepare(node):
        assert isinstance(node, Node)
        return [lambda: events.append("write")]

    with patch("mesh_desk.radio.time.sleep"):
        session.perform_save(prepare, config_loaded=True)
    assert events == ["begin", "write", "commit"]
