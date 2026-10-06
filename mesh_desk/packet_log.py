"""Rolling packet log. Summaries only — payloads and keys stay out of the buffer."""

from __future__ import annotations

from collections import deque
from datetime import datetime

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk


class PacketLog(Gtk.Box):
    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self._rows: deque[dict] = deque(maxlen=400)
        bar = Gtk.Box(spacing=6)
        bar.set_margin_start(8)
        bar.set_margin_end(8)
        bar.set_margin_top(8)
        self.filter = Gtk.Entry(placeholder_text="Filter by name, port, or text")
        self.filter.set_hexpand(True)
        self.filter.connect("changed", lambda _e: self._rebuild())
        clear = Gtk.Button(label="Clear")
        clear.connect("clicked", self._clear)
        bar.append(self.filter)
        bar.append(clear)
        self.append(bar)
        self.view = Gtk.TextView(editable=False, monospace=True, wrap_mode=Gtk.WrapMode.WORD_CHAR)
        self.view.set_left_margin(8)
        self.view.set_right_margin(8)
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_child(self.view)
        self.append(scroll)

    def add(self, row: dict) -> None:
        self._rows.append(row)
        self._rebuild()

    def _clear(self, _btn) -> None:
        self._rows.clear()
        self._rebuild()

    def _rebuild(self) -> None:
        needle = self.filter.get_text().strip().lower()
        lines = []
        for row in self._rows:
            line = _format(row)
            if needle and needle not in line.lower():
                continue
            lines.append(line)
        buf = self.view.get_buffer()
        buf.set_text("\n".join(lines))
        end = buf.get_end_iter()
        self.view.scroll_to_iter(end, 0.0, False, 0.0, 1.0)


def _format(row: dict) -> str:
    clock = datetime.fromtimestamp(row["ts"]).strftime("%H:%M:%S")
    hops = "" if row.get("hops") is None else f"  {row['hops']} hops"
    extra = f"  {row['extra']}" if row.get("extra") else ""
    return f"{clock}  {row.get('from') or '?'} → {row.get('to') or '?'}  {row.get('port') or '?'}{hops}{extra}"
