"""One radio session. BLE callbacks stay off the GTK thread."""

from __future__ import annotations

import logging
import subprocess
import threading
import time
import traceback
from typing import Any, Callable

from pubsub import pub

log = logging.getLogger("mesh_desk.radio")

BROADCAST_IDS = {"^all", "!ffffffff", "ffffffff", "0xffffffff"}


def _as_dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def _snapshot_values(mapping) -> list:
    """Copy a dict the radio thread is also mutating. Retry if it changes mid-iteration."""
    if not isinstance(mapping, dict):
        return []
    for _ in range(4):
        try:
            return list(mapping.values())
        except RuntimeError:
            continue
    return []


def _ui(fn: Callable[..., None], *args: Any) -> None:
    from gi.repository import GLib

    def once() -> bool:
        try:
            fn(*args)
        except Exception:
            traceback.print_exc()
        return False

    GLib.idle_add(once)


class RadioSession:
    def __init__(self) -> None:
        self.iface = None
        self.lock = threading.Lock()
        self.address = ""
        self._subscribed = False

    def listen(self, on_text, on_nodes, on_lost, on_packet=None) -> None:
        if self._subscribed:
            return
        self._on_text = on_text
        self._on_nodes = on_nodes
        self._on_lost = on_lost
        self._on_packet = on_packet
        pub.subscribe(self._text, "meshtastic.receive.text")
        pub.subscribe(self._node, "meshtastic.node.updated")
        pub.subscribe(self._lost, "meshtastic.connection.lost")
        pub.subscribe(self._packet, "meshtastic.receive")
        self._subscribed = True

    def _text(self, packet, interface=None, **_kwargs) -> None:
        decoded = packet.get("decoded") or {}
        text = decoded.get("text")
        payload = decoded.get("payload")
        if text is None and isinstance(payload, (bytes, bytearray)):
            text = payload.decode("utf-8", "replace")
        if not text:
            return
        _ui(
            self._on_text,
            {
                "ts": time.time(),
                "from_id": packet.get("fromId") or "",
                "to_id": packet.get("toId") or "",
                "to": packet.get("to"),
                "channel": int(packet.get("channel") or 0),
                "text": text,
                "hops": packet.get("hopsAway"),
            },
        )

    def _node(self, node=None, interface=None, **_kwargs) -> None:
        _ui(self._on_nodes)

    def _lost(self, interface=None, **_kwargs) -> None:
        _ui(self._on_lost)

    def _packet(self, packet=None, interface=None, **_kwargs) -> None:
        # `interface` is part of the pubsub topic contract. The name has to match
        # what meshtastic sends or every packet raises SenderUnknownMsgDataError.
        del interface
        if not self._on_packet or not isinstance(packet, dict):
            return
        try:
            summary = _summarize(packet)
        except Exception:
            log.exception("packet summary failed")
            return
        if summary is None:
            return
        _ui(self._on_packet, summary)

    def connect_ble(self, address: str, on_ok, on_err) -> None:
        address = address.strip()

        def work() -> None:
            try:
                subprocess.run(
                    ["bluetoothctl", "disconnect", address],
                    timeout=8,
                    capture_output=True,
                    check=False,
                )
            except Exception:
                log.debug("bluetoothctl disconnect skipped", exc_info=True)
            try:
                from meshtastic.ble_interface import BLEInterface

                iface = BLEInterface(address, timeout=25)
            except Exception as exc:
                log.exception("BLE connect failed")
                _ui(on_err, str(exc))
                return
            with self.lock:
                self.iface = iface
                self.address = address
            _ui(on_ok)

        threading.Thread(target=work, name="mesh-connect", daemon=True).start()

    def connect_serial(self, on_ok, on_err, dev: str | None = None) -> None:
        def work() -> None:
            try:
                from meshtastic.serial_interface import SerialInterface

                iface = SerialInterface(dev) if dev else SerialInterface()
            except Exception as exc:
                log.exception("serial connect failed")
                _ui(on_err, str(exc))
                return
            with self.lock:
                self.iface = iface
                self.address = dev or "serial"
            _ui(on_ok)

        threading.Thread(target=work, name="mesh-serial", daemon=True).start()

    def connect_tcp(self, host: str, on_ok, on_err) -> None:
        host = host.strip()

        def work() -> None:
            try:
                from meshtastic.tcp_interface import TCPInterface

                iface = TCPInterface(host, timeout=20)
            except Exception as exc:
                log.exception("TCP connect failed")
                _ui(on_err, str(exc))
                return
            with self.lock:
                self.iface = iface
                self.address = host
            _ui(on_ok)

        threading.Thread(target=work, name="mesh-tcp", daemon=True).start()

    def disconnect(self, on_done) -> None:
        def work() -> None:
            with self.lock:
                iface = self.iface
                self.iface = None
                self.address = ""
            if iface is not None:
                try:
                    iface.close()
                except Exception:
                    log.exception("close failed")
            _ui(on_done)

        threading.Thread(target=work, name="mesh-close", daemon=True).start()

    def my_id(self) -> str:
        iface = self.iface
        if iface is None or getattr(iface, "myInfo", None) is None:
            return ""
        num = iface.myInfo.my_node_num
        node = _as_dict(iface.nodesByNum.get(num) if isinstance(getattr(iface, "nodesByNum", None), dict) else None)
        user = _as_dict(node.get("user"))
        return user.get("id") or ""

    def nodes(self) -> list[dict]:
        with self.lock:
            iface = self.iface
        if iface is None:
            return []
        rows = []
        for node in _snapshot_values(getattr(iface, "nodes", None)):
            if not isinstance(node, dict):
                continue
            user = _as_dict(node.get("user"))
            metrics = _as_dict(node.get("deviceMetrics"))
            pos = _as_dict(node.get("position"))
            lat = pos.get("latitude")
            lon = pos.get("longitude")
            try:
                lat_f = float(lat) if lat is not None else None
                lon_f = float(lon) if lon is not None else None
            except (TypeError, ValueError):
                lat_f = lon_f = None
            if not lat_f and not lon_f:
                lat_f = lon_f = None
            hops = node.get("hopsAway")
            try:
                hops = int(hops) if hops is not None else None
            except (TypeError, ValueError):
                hops = None
            node_id = str(user.get("id") or "")
            if not node_id:
                continue
            long_name = user.get("longName") or node_id
            rows.append(
                {
                    "id": node_id,
                    "num": node.get("num"),
                    "long": str(long_name),
                    "short": str(user.get("shortName") or ""),
                    "role": str(user.get("role") or ""),
                    "hw": str(user.get("hwModel") or ""),
                    "hops": hops,
                    "battery": metrics.get("batteryLevel"),
                    "last_heard": node.get("lastHeard"),
                    "snr": node.get("snr"),
                    "lat": lat_f,
                    "lon": lon_f,
                    "favorite": bool(node.get("isFavorite")),
                }
            )
        rows.sort(
            key=lambda r: (
                not r["favorite"],
                r["hops"] is None,
                r["hops"] if r["hops"] is not None else 99,
                r["long"].lower(),
            )
        )
        return rows

    def channels(self) -> list[dict]:
        iface = self.iface
        found: list[dict] = []
        raw = []
        if iface is not None and getattr(iface, "localNode", None) is not None:
            raw = iface.localNode.channels or []
        from meshtastic.protobuf import channel_pb2

        disabled = channel_pb2.Channel.Role.DISABLED
        for ch in raw:
            if ch.role == disabled:
                continue
            settings = getattr(ch, "settings", None)
            name = (settings.name if settings is not None else "") or ""
            idx = int(getattr(ch, "index", len(found)))
            if not name:
                name = "LongFast" if idx == 0 else f"Channel {idx}"
            psk = bytes(settings.psk) if settings is not None else b""
            public = idx == 0 and len(psk) <= 1
            label = f"{name} (public)" if public else name
            found.append({"index": idx, "label": label})
        if not found:
            found.append({"index": 0, "label": "LongFast (public)"})
        return found

    def send_channel(self, text: str, channel: int, on_ok, on_err) -> None:
        def work() -> None:
            try:
                iface = self.iface
                if iface is None:
                    raise RuntimeError("Not connected")
                iface.sendText(text, channelIndex=channel)
            except Exception as exc:
                _ui(on_err, str(exc))
                return
            _ui(on_ok)

        threading.Thread(target=work, name="mesh-send", daemon=True).start()

    def send_dm(self, text: str, dest: str, on_ok, on_err) -> None:
        def work() -> None:
            try:
                iface = self.iface
                if iface is None:
                    raise RuntimeError("Not connected")
                iface.sendText(text, destinationId=dest, channelIndex=0)
            except Exception as exc:
                _ui(on_err, str(exc))
                return
            _ui(on_ok)

        threading.Thread(target=work, name="mesh-send", daemon=True).start()

    def local_node(self):
        iface = self.iface
        if iface is None:
            return None
        return getattr(iface, "localNode", None)

    def metadata(self):
        iface = self.iface
        if iface is None:
            return None
        return getattr(iface, "metadata", None)

    def save_writes(self, prepare, on_ok, on_err, *, config_loaded: bool = True) -> None:
        """prepare(node) returns write callables. One settings transaction, then reboot."""

        def work() -> None:
            try:
                self.perform_save(prepare, config_loaded=config_loaded)
            except Exception as exc:
                log.exception("save failed")
                _ui(on_err, str(exc))
                return
            _ui(on_ok)

        threading.Thread(target=work, name="mesh-config", daemon=True).start()

    def perform_save(self, prepare, *, config_loaded: bool = True) -> None:
        """Write one settings transaction.

        Remote admin must pass config_loaded=True only after that node's config
        has been read. A write of a config we never read can wipe the node.
        """
        if not config_loaded:
            raise RuntimeError("Config has not been read")
        iface = self.iface
        if iface is None or getattr(iface, "localNode", None) is None:
            raise RuntimeError("Not connected")
        node = iface.localNode
        writes = list(prepare(node))
        if not writes:
            raise RuntimeError("Nothing to write")
        node.beginSettingsTransaction()
        time.sleep(0.25)
        for fn in writes:
            fn()
            time.sleep(0.3)
        node.commitSettingsTransaction()

    def set_favorite(self, node_id: str, favorite: bool, on_ok, on_err) -> None:
        def work() -> None:
            try:
                node = self.local_node()
                if node is None:
                    raise RuntimeError("Not connected")
                if favorite:
                    node.setFavorite(node_id)
                else:
                    node.removeFavorite(node_id)
                iface = self.iface
                if iface is not None:
                    for entry in _snapshot_values(getattr(iface, "nodes", None)):
                        user = _as_dict(entry.get("user") if isinstance(entry, dict) else None)
                        if user.get("id") == node_id:
                            entry["isFavorite"] = favorite
            except Exception as exc:
                log.exception("favorite failed")
                _ui(on_err, str(exc))
                return
            _ui(on_ok)

        threading.Thread(target=work, name="mesh-favorite", daemon=True).start()

    def traceroute(self, dest: str, on_ok, on_err) -> None:
        def work() -> None:
            try:
                from meshtastic.protobuf import mesh_pb2, portnums_pb2

                iface = self.iface
                if iface is None:
                    raise RuntimeError("Not connected")
                hop = 3
                node = self.local_node()
                if node is not None:
                    hop = int(node.localConfig.lora.hop_limit or 3)
                state: dict[str, Any] = {"done": False}
                event = threading.Event()

                def callback(packet) -> None:
                    if state["done"]:
                        return
                    state["packet"] = packet
                    event.set()

                iface.sendData(
                    mesh_pb2.RouteDiscovery(),
                    destinationId=dest,
                    portNum=portnums_pb2.PortNum.TRACEROUTE_APP,
                    wantResponse=True,
                    onResponse=callback,
                    hopLimit=hop,
                )
                if not event.wait(20 + 8 * hop):
                    state["done"] = True
                    raise RuntimeError("Timed out waiting for a route")
                state["done"] = True
                text = _format_route(iface, state.get("packet") or {}, dest)
            except Exception as exc:
                log.exception("traceroute failed")
                _ui(on_err, str(exc))
                return
            _ui(on_ok, text)

        threading.Thread(target=work, name="mesh-trace", daemon=True).start()

    def send_waypoint(self, name: str, description: str, lat: float, lon: float, on_ok, on_err) -> None:
        def work() -> None:
            try:
                iface = self.iface
                if iface is None:
                    raise RuntimeError("Not connected")
                iface.sendWaypoint(
                    name,
                    description,
                    0,
                    expire=int(time.time()) + 48 * 3600,
                    latitude=lat,
                    longitude=lon,
                )
            except Exception as exc:
                log.exception("waypoint failed")
                _ui(on_err, str(exc))
                return
            _ui(on_ok)

        threading.Thread(target=work, name="mesh-waypoint", daemon=True).start()


def _summarize(packet: dict) -> dict | None:
    decoded = packet.get("decoded") or {}
    port = str(decoded.get("portnum") or "packet")
    extra = ""
    text = decoded.get("text")
    if isinstance(text, str) and text:
        extra = text if len(text) <= 80 else text[:80] + "…"
    elif port in ("TRACEROUTE_APP", "ROUTING_APP", "ADMIN_APP", "NODEINFO_APP", "POSITION_APP"):
        extra = ""
    waypoint = None
    raw_wp = decoded.get("waypoint")
    if isinstance(raw_wp, dict):
        lat_i = raw_wp.get("latitudeI", raw_wp.get("latitude_i"))
        lon_i = raw_wp.get("longitudeI", raw_wp.get("longitude_i"))
        try:
            lat = float(lat_i) * 1e-7
            lon = float(lon_i) * 1e-7
        except (TypeError, ValueError):
            lat = lon = None
        if lat is not None and lon is not None and (lat or lon):
            waypoint = {
                "name": raw_wp.get("name") or "Waypoint",
                "description": raw_wp.get("description") or "",
                "lat": lat,
                "lon": lon,
            }
            extra = waypoint["name"]
    return {
        "ts": time.time(),
        "from": packet.get("fromId") or "",
        "to": packet.get("toId") or "",
        "port": port,
        "hops": packet.get("hopsAway"),
        "extra": extra,
        "waypoint": waypoint,
    }


def _format_route(iface, packet: dict, dest: str) -> str:
    decoded = packet.get("decoded") or {}
    if decoded.get("portnum") == "ROUTING_APP":
        reason = (decoded.get("routing") or {}).get("errorReason") or "no route"
        if reason != "NONE":
            raise RuntimeError(f"Traceroute failed: {reason}")
    route = (decoded.get("traceroute") or {}).get("route") or []
    names = [_node_label(iface, num) for num in route]
    end = packet.get("fromId") or dest
    parts = ["this radio", *names, end]
    # Drop an immediate duplicate if the reply id equals the last hop.
    collapsed = [parts[0]]
    for part in parts[1:]:
        if part != collapsed[-1]:
            collapsed.append(part)
    if len(collapsed) <= 2 and not names:
        return f"Direct to {end}. No relay in the reply."
    return " → ".join(collapsed)


def _node_label(iface, num) -> str:
    try:
        number = int(num)
    except (TypeError, ValueError):
        return str(num)
    node = (getattr(iface, "nodesByNum", {}) or {}).get(number) or {}
    user = node.get("user") or {}
    return user.get("longName") or user.get("id") or f"!{number:08x}"
