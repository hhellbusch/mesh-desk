"""Main window: connect, nodes, channel chat, direct messages."""

from __future__ import annotations

import time
from datetime import datetime

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from mesh_desk.config_panel import ConfigPanel
from mesh_desk.known import load_radios, remember_radio
from mesh_desk.map_view import MapPage
from mesh_desk.node_dialog import present_node
from mesh_desk.packet_log import PacketLog
from mesh_desk.radio import BROADCAST_IDS, RadioSession
from mesh_desk.store import Store


def _heard(ts) -> str:
    if not ts:
        return "—"
    try:
        age = time.time() - float(ts)
    except (TypeError, ValueError):
        return "—"
    if age < 60:
        return "just now"
    if age < 3600:
        return f"{int(age // 60)} min"
    if age < 86400:
        return f"{int(age // 3600)} h"
    return f"{int(age // 86400)} d"


def _clock(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%H:%M")


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application) -> None:
        super().__init__(application=app, title="mesh-desk")
        self.set_default_size(1100, 760)
        self.store = Store()
        self.radio = RadioSession()
        self.radio.listen(self._on_text, self._on_nodes, self._on_lost, self._on_packet)
        self.names: dict[str, str] = {}
        self._nodes_by_id: dict[str, dict] = {}
        self.view: tuple[str, object] = ("channel", 0)
        self._closing = False
        self._selecting = False
        self._suppress_select = False
        self._node_refresh_pending = False
        self._row_node: dict[Gtk.ListBoxRow, str] = {}
        self._row_channel: dict[Gtk.ListBoxRow, int] = {}

        self.status = Gtk.Label(label="Disconnected")
        self.status.add_css_class("dim-label")
        self.connect_btn = Gtk.Button(label="Connect")
        self.connect_btn.connect("clicked", self._open_connect)

        self.channel_list = Gtk.ListBox()
        self.channel_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.channel_list.connect("row-selected", self._channel_selected)
        self.node_list = Gtk.ListBox()
        self.node_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.node_list.connect("row-selected", self._node_selected)
        nodes_scroll = Gtk.ScrolledWindow()
        nodes_scroll.set_vexpand(True)
        nodes_scroll.set_child(self.node_list)
        side = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        side.set_margin_top(6)
        side.set_margin_bottom(6)
        side.set_margin_start(6)
        side.set_margin_end(6)
        side.append(Gtk.Label(label="Channels", xalign=0))
        side.append(self.channel_list)
        side.append(Gtk.Separator())
        side.append(Gtk.Label(label="Nodes — click to message, Info for detail", xalign=0))
        self.heard = Gtk.DropDown.new_from_strings(
            ["Any time", "Last hour", "Last 6 hours", "Last day", "Last week"]
        )
        self.heard.connect("notify::selected", lambda *_a: self._refresh_nodes())
        side.append(self.heard)
        side.append(nodes_scroll)
        side.set_size_request(280, -1)

        self.messages = Gtk.ListBox()
        self.messages.set_selection_mode(Gtk.SelectionMode.NONE)
        msg_scroll = Gtk.ScrolledWindow()
        msg_scroll.set_vexpand(True)
        msg_scroll.set_child(self.messages)
        self.msg_scroll = msg_scroll
        self.entry = Gtk.Entry(placeholder_text="Message")
        self.entry.set_hexpand(True)
        self.entry.connect("activate", self._send)
        send = Gtk.Button(label="Send")
        send.add_css_class("suggested-action")
        send.connect("clicked", self._send)
        compose = Gtk.Box(spacing=6)
        compose.set_margin_top(6)
        compose.set_margin_bottom(6)
        compose.set_margin_start(6)
        compose.set_margin_end(6)
        compose.append(self.entry)
        compose.append(send)
        chat = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        chat.append(msg_scroll)
        chat.append(compose)

        chat_page = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        chat_page.append(side)
        # side should not eat the whole window
        side.set_hexpand(False)
        chat.set_hexpand(True)
        chat_page.append(chat)

        self.config = ConfigPanel(self._save_config)
        self.map = MapPage(self._open_node, self._send_waypoint)
        self.packet_log = PacketLog()
        self.stack = Adw.ViewStack()
        self.stack.add_titled(chat_page, "chat", "Chat")
        self.stack.add_titled(self.map, "map", "Map")
        self.stack.add_titled(self.config, "radio", "Radio")
        self.stack.add_titled(self.packet_log, "log", "Log")
        switcher = Adw.ViewSwitcher()
        switcher.set_policy(Adw.ViewSwitcherPolicy.WIDE)
        switcher.set_stack(self.stack)

        header = Adw.HeaderBar()
        header.set_title_widget(switcher)
        header.pack_start(self.status)
        header.pack_end(self.connect_btn)

        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        body.append(header)
        body.append(self.stack)
        self.set_content(body)
        self.connect("close-request", self._on_close)
        self._show_channels([{"index": 0, "label": "LongFast (public)"}])
        self._reload_messages()

    def _open_connect(self, _btn) -> None:
        if self.radio.iface is not None:
            self.status.set_label("Disconnecting…")
            self.connect_btn.set_sensitive(False)
            self.radio.disconnect(self._disconnected)
            return
        dialog = Adw.Dialog(title="Connect")
        dialog.set_content_width(420)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_margin_start(12)
        box.set_margin_end(12)
        radios = load_radios()
        self._addr = Gtk.Entry()
        self._addr.set_placeholder_text("Bluetooth address")
        if radios:
            self._addr.set_text(radios[0]["address"])
        else:
            hint = Gtk.Label(
                label="Type a Bluetooth address. Addresses you connect are remembered on this computer only.",
                wrap=True,
                xalign=0,
            )
            hint.add_css_class("dim-label")
            box.append(hint)
        for radio in radios:
            btn = Gtk.Button(label=f"{radio['name']}  {radio['address']}")
            btn.connect("clicked", lambda _b, a=radio["address"]: self._addr.set_text(a))
            box.append(btn)
        box.append(self._addr)
        self._tcp = Gtk.Entry(placeholder_text="TCP host, if the radio has Wi-Fi")
        box.append(self._tcp)
        row = Gtk.Box(spacing=8)
        ble = Gtk.Button(label="Connect BLE")
        ble.add_css_class("suggested-action")
        ble.connect("clicked", lambda _b: self._start_ble(dialog))
        serial = Gtk.Button(label="USB serial")
        serial.connect("clicked", lambda _b: self._start_serial(dialog))
        tcp = Gtk.Button(label="TCP")
        tcp.connect("clicked", lambda _b: self._start_tcp(dialog))
        row.append(ble)
        row.append(serial)
        row.append(tcp)
        box.append(row)
        dialog.set_child(box)
        dialog.present(self)

    def _start_ble(self, dialog: Adw.Dialog) -> None:
        addr = self._addr.get_text().strip()
        if not addr:
            self.status.set_label("Need a BLE address")
            return
        dialog.close()
        self.status.set_label(f"Connecting {addr}…")
        self.connect_btn.set_sensitive(False)
        self.radio.connect_ble(addr, self._connected, self._failed)

    def _start_serial(self, dialog: Adw.Dialog) -> None:
        dialog.close()
        self.status.set_label("Connecting USB…")
        self.connect_btn.set_sensitive(False)
        self.radio.connect_serial(self._connected, self._failed)

    def _start_tcp(self, dialog: Adw.Dialog) -> None:
        host = self._tcp.get_text().strip()
        if not host:
            self.status.set_label("Need a TCP host")
            return
        dialog.close()
        self.status.set_label(f"Connecting {host}…")
        self.connect_btn.set_sensitive(False)
        self.radio.connect_tcp(host, self._connected, self._failed)

    def _connected(self) -> None:
        self.connect_btn.set_sensitive(True)
        self.connect_btn.set_label("Disconnect")
        my = self.radio.my_id()
        remember_radio(self.radio.address)
        self.status.set_label(f"Connected {self.radio.address}" + (f"  {my}" if my else ""))
        self._show_channels(self.radio.channels())
        self._refresh_nodes()
        node = self.radio.local_node()
        if node is not None:
            try:
                self.config.load(node, self.radio.metadata())
            except Exception as exc:
                self.status.set_label(f"Connected, settings failed to load: {exc}"[:180])

    def _failed(self, message: str) -> None:
        self.connect_btn.set_sensitive(True)
        self.connect_btn.set_label("Connect")
        short = message.strip().splitlines()[-1] if message else "Connect failed"
        self.status.set_label(short[:180])

    def _disconnected(self) -> None:
        self.connect_btn.set_sensitive(True)
        self.connect_btn.set_label("Connect")
        self.status.set_label("Disconnected")
        self.config.clear()

    def _on_lost(self) -> None:
        if self._closing:
            return
        self.connect_btn.set_label("Connect")
        self.status.set_label("Radio disconnected")
        self.config.clear()

    def _on_nodes(self) -> None:
        if self._closing or self._node_refresh_pending:
            return
        self._node_refresh_pending = True
        GLib.timeout_add(400, self._debounced_nodes)

    def _debounced_nodes(self) -> bool:
        self._node_refresh_pending = False
        if not self._closing:
            self._refresh_nodes()
        return False

    def _refresh_nodes(self) -> None:
        if not hasattr(self, "map") or self._closing:
            return
        rows = self.radio.nodes()
        self._nodes_by_id = {r["id"]: r for r in rows if r["id"]}
        self.names = {r["id"]: r["long"] for r in rows if r["id"]}
        self.map.set_nodes(rows)
        selected_filter = self.heard.get_selected()
        limit = None if selected_filter > 4 else (None, 3600, 6 * 3600, 86400, 7 * 86400)[selected_filter]
        if limit is not None:
            now = time.time()
            kept = []
            for row in rows:
                heard = row.get("last_heard")
                try:
                    fresh = heard is not None and now - float(heard) <= limit
                except (TypeError, ValueError):
                    fresh = False
                if fresh:
                    kept.append(row)
            rows = kept
        selected = self.view[1] if self.view[0] == "dm" else None
        self.node_list.handler_block_by_func(self._node_selected)
        try:
            child = self.node_list.get_first_child()
            while child is not None:
                nxt = child.get_next_sibling()
                self.node_list.remove(child)
                child = nxt
            self._row_node.clear()
            for row in rows:
                label = Gtk.Label(xalign=0)
                label.set_hexpand(True)
                hops = "—" if row["hops"] is None else str(row["hops"])
                star = "★ " if row["favorite"] else ""
                battery = f" · {row['battery']}%" if row["battery"] is not None else ""
                label.set_text(f"{star}{row['long']}\n{hops} hops · {_heard(row['last_heard'])}{battery}")
                label.set_wrap(True)
                info = Gtk.Button(label="Info")
                info.add_css_class("flat")
                gesture = Gtk.GestureClick()
                gesture.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
                gesture.connect("pressed", self._info_pressed, row["id"])
                info.add_controller(gesture)
                line = Gtk.Box(spacing=6)
                line.append(label)
                line.append(info)
                holder = Gtk.ListBoxRow()
                holder.set_child(line)
                self._row_node[holder] = row["id"]
                self.node_list.append(holder)
                if row["id"] == selected:
                    self.node_list.select_row(holder)
        finally:
            self.node_list.handler_unblock_by_func(self._node_selected)

    def _info_pressed(self, gesture, _n, _x, _y, node_id: str) -> None:
        self._suppress_select = True
        gesture.set_state(Gtk.EventSequenceState.CLAIMED)
        self._open_node(node_id)

    def _show_channels(self, channels: list[dict]) -> None:
        self.channel_list.handler_block_by_func(self._channel_selected)
        try:
            child = self.channel_list.get_first_child()
            while child is not None:
                nxt = child.get_next_sibling()
                self.channel_list.remove(child)
                child = nxt
            self._row_channel.clear()
            first = None
            for ch in channels:
                label = Gtk.Label(label=ch["label"], xalign=0)
                holder = Gtk.ListBoxRow()
                holder.set_child(label)
                self._row_channel[holder] = ch["index"]
                self.channel_list.append(holder)
                if first is None:
                    first = holder
            if first is not None and self.view[0] == "channel":
                self.channel_list.select_row(first)
        finally:
            self.channel_list.handler_unblock_by_func(self._channel_selected)

    def _channel_selected(self, _box, row) -> None:
        if row is None or self._selecting or self._suppress_select:
            return
        index = self._row_channel.get(row)
        if index is None:
            return
        self._selecting = True
        self.node_list.unselect_all()
        self._selecting = False
        self.view = ("channel", int(index))
        self._reload_messages()

    def _node_selected(self, _box, row) -> None:
        if self._suppress_select:
            self._suppress_select = False
            return
        if row is None or self._selecting:
            return
        node_id = self._row_node.get(row)
        if not node_id:
            return
        self._selecting = True
        self.channel_list.unselect_all()
        self._selecting = False
        self.view = ("dm", node_id)
        self._reload_messages()

    def _name(self, node_id: str) -> str:
        if not node_id:
            return "unknown"
        return self.names.get(node_id, node_id)

    def _reload_messages(self) -> None:
        if self.view[0] == "dm":
            rows = self.store.list_dm(str(self.view[1]))
        else:
            rows = self.store.list_channel(int(self.view[1]))
        child = self.messages.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self.messages.remove(child)
            child = nxt
        for row in rows:
            who = "you" if row["outgoing"] else self._name(row["from_id"] or "")
            label = Gtk.Label(xalign=0)
            label.set_wrap(True)
            label.set_text(f"{_clock(row['ts'])}  {who}\n{row['text']}")
            label.set_margin_top(4)
            label.set_margin_bottom(4)
            label.set_margin_start(8)
            label.set_margin_end(8)
            self.messages.append(label)
        GLib.idle_add(self._scroll_end)

    def _scroll_end(self) -> bool:
        adj = self.msg_scroll.get_vadjustment()
        if adj is not None:
            adj.set_value(adj.get_upper())
        return False

    def _on_text(self, packet: dict) -> None:
        my = self.radio.my_id()
        from_id = packet["from_id"]
        to_id = packet["to_id"] or ""
        if from_id and self.store.recent_duplicate(from_id, packet["text"]):
            return
        broadcast = (not to_id) or to_id in BROADCAST_IDS or packet.get("to") in (0, 0xFFFFFFFF)
        if broadcast:
            self.store.add(
                kind="channel",
                channel=packet["channel"],
                from_id=from_id,
                to_id=to_id,
                text=packet["text"],
                hops=packet.get("hops"),
                ts=packet["ts"],
                outgoing=bool(my and from_id == my),
            )
            visible = self.view == ("channel", packet["channel"])
        else:
            peer = to_id if from_id == my else from_id
            self.store.add(
                kind="dm",
                peer=peer,
                from_id=from_id,
                to_id=to_id,
                text=packet["text"],
                hops=packet.get("hops"),
                ts=packet["ts"],
                outgoing=bool(my and from_id == my),
            )
            visible = self.view == ("dm", peer)
        if visible:
            self._reload_messages()

    def _send(self, *_args) -> None:
        text = self.entry.get_text().strip()
        if not text:
            return
        if self.radio.iface is None:
            self.status.set_label("Connect a radio first")
            return
        my = self.radio.my_id()
        kind, target = self.view

        def ok() -> None:
            if kind == "dm":
                self.store.add(
                    kind="dm",
                    peer=str(target),
                    from_id=my,
                    to_id=str(target),
                    text=text,
                    outgoing=True,
                )
            else:
                self.store.add(
                    kind="channel",
                    channel=int(target),
                    from_id=my,
                    to_id="^all",
                    text=text,
                    outgoing=True,
                )
            self.entry.set_text("")
            self._reload_messages()

        def err(message: str) -> None:
            self.status.set_label(message[:180])

        if kind == "dm":
            self.radio.send_dm(text, str(target), ok, err)
        else:
            self.radio.send_channel(text, int(target), ok, err)

    def _save_config(self, heading: str, body: str, prepare) -> None:
        if prepare is None:
            self.status.set_label(str(body)[:180])
            return
        if self.radio.iface is None:
            self.status.set_label("Connect a radio first")
            return
        dialog = Adw.AlertDialog(heading=heading, body=body)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("save", "Save")
        dialog.set_response_appearance("save", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect(
            "response",
            lambda _d, resp, prepare=prepare: self._write_config(prepare) if resp == "save" else None,
        )
        dialog.present(self)

    def _write_config(self, prepare) -> None:
        self.status.set_label("Saving… the radio will reboot")
        self.config.set_sensitive(False)
        self.radio.save_writes(prepare, self._saved, self._save_failed)

    def _saved(self) -> None:
        self.status.set_label("Saved. The radio is rebooting and will drop the link.")

    def _save_failed(self, message: str) -> None:
        self.config.set_sensitive(True)
        self.status.set_label(message[:180])

    def _on_packet(self, summary: dict) -> None:
        self.packet_log.add(summary)
        waypoint = summary.get("waypoint")
        if waypoint:
            self.map.add_waypoint(waypoint)

    def _open_node(self, node_id: str) -> None:
        node = self._nodes_by_id.get(node_id)
        if node is None:
            return
        present_node(
            self,
            node,
            on_favorite=self._favorite,
            on_traceroute=self.radio.traceroute,
            on_message=self._open_dm,
        )

    def _favorite(self, node_id: str, favorite: bool) -> None:
        self.radio.set_favorite(
            node_id,
            favorite,
            lambda: self._favorite_done(node_id, favorite),
            lambda message: self.status.set_label(message[:180]),
        )

    def _favorite_done(self, node_id: str, favorite: bool) -> None:
        self.status.set_label("Favorite updated on the radio")
        self._refresh_nodes()

    def _open_dm(self, node_id: str) -> None:
        if not node_id:
            return
        self.view = ("dm", node_id)
        self.stack.set_visible_child_name("chat")
        self._reload_messages()

    def _send_waypoint(self, draft: dict) -> None:
        if self.radio.iface is None:
            self.status.set_label("Connect a radio first")
            return
        if not draft["name"]:
            self.status.set_label("Waypoint needs a name")
            return
        try:
            lat = float(draft["lat"])
            lon = float(draft["lon"])
        except ValueError:
            self.status.set_label("Latitude and longitude need to be numbers")
            return
        dialog = Adw.AlertDialog(
            heading="Broadcast this waypoint?",
            body=f"{draft['name']} at {lat:.5f}, {lon:.5f} goes out on the primary channel.",
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("send", "Send")
        dialog.set_response_appearance("send", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")

        def go(_d, resp, name=draft["name"], desc=draft["description"], lat=lat, lon=lon) -> None:
            if resp != "send":
                return
            self.radio.send_waypoint(
                name,
                desc,
                lat,
                lon,
                lambda: self.status.set_label("Waypoint sent"),
                lambda message: self.status.set_label(message[:180]),
            )

        dialog.connect("response", go)
        dialog.present(self)

    def _on_close(self, _win) -> bool:
        if self._closing:
            return False
        self._closing = True
        if self.radio.iface is None:
            self.store.close()
            return False
        self.status.set_label("Closing radio…")
        self.radio.disconnect(self._finish_quit)
        return True

    def _finish_quit(self) -> None:
        self.store.close()
        self.destroy()
