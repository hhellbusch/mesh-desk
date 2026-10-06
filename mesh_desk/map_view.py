"""Offline node map. Equirectangular, no tiles.

libshumate is not installed here, and a tile map goes dark with the internet.
Positions come from the node database already on the radio.
"""

from __future__ import annotations

import math

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk


def _age_alpha(last_heard, now: float) -> float:
    if not last_heard:
        return 0.45
    try:
        age = now - float(last_heard)
    except (TypeError, ValueError):
        return 0.45
    if age < 3600:
        return 1.0
    if age < 86400:
        return 0.75
    return 0.4


class MapPage(Gtk.Box):
    def __init__(self, on_node, on_send_waypoint) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._on_node = on_node
        self._on_send_waypoint = on_send_waypoint
        self._rows: list[dict] = []
        self._screen: list[tuple[float, float, dict]] = []
        self.clat = 0.0
        self.clon = 0.0
        self.k = 12.0
        self._fitted = False
        self._drag_last = (0.0, 0.0)

        self.histogram = Gtk.Label(xalign=0, label="Hops: connect a radio")
        self.histogram.set_margin_start(12)
        self.histogram.set_margin_top(8)
        self.histogram.add_css_class("dim-label")

        self.area = Gtk.DrawingArea()
        self.area.set_vexpand(True)
        self.area.set_hexpand(True)
        self.area.set_draw_func(self._draw)
        click = Gtk.GestureClick()
        click.connect("released", self._clicked)
        self.area.add_controller(click)
        drag = Gtk.GestureDrag()
        drag.connect("drag-begin", self._drag_begin)
        drag.connect("drag-update", self._drag_update)
        self.area.add_controller(drag)
        scroll = Gtk.EventControllerScroll.new(Gtk.EventControllerScrollFlags.VERTICAL)
        scroll.connect("scroll", self._scrolled)
        self.area.add_controller(scroll)

        bar = Gtk.Box(spacing=6)
        bar.set_margin_start(12)
        bar.set_margin_end(12)
        bar.set_margin_bottom(6)
        fit = Gtk.Button(label="Fit")
        fit.connect("clicked", lambda _b: self._fit(force=True))
        bar.append(fit)
        hint = Gtk.Label(label="Drag to pan. Scroll to zoom. Click a dot for the node.", xalign=0)
        hint.add_css_class("dim-label")
        hint.set_hexpand(True)
        bar.append(hint)

        side = self._waypoint_box()
        split = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        split.set_vexpand(True)
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        left.append(self.area)
        left.append(bar)
        split.set_start_child(left)
        split.set_end_child(side)
        split.set_resize_end_child(False)
        split.set_shrink_end_child(False)
        self.append(self.histogram)
        self.append(split)

    def _waypoint_box(self) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(8)
        box.set_margin_end(8)
        box.set_size_request(260, -1)
        title = Gtk.Label(label="Waypoints", xalign=0)
        box.append(title)
        self.waypoint_list = Gtk.ListBox()
        self.waypoint_list.set_selection_mode(Gtk.SelectionMode.NONE)
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_child(self.waypoint_list)
        scroll.set_min_content_height(120)
        box.append(scroll)
        self.wp_name = Gtk.Entry(placeholder_text="Name")
        self.wp_lat = Gtk.Entry(placeholder_text="Latitude")
        self.wp_lon = Gtk.Entry(placeholder_text="Longitude")
        self.wp_desc = Gtk.Entry(placeholder_text="Description")
        for entry in (self.wp_name, self.wp_lat, self.wp_lon, self.wp_desc):
            box.append(entry)
        send = Gtk.Button(label="Send waypoint")
        send.connect("clicked", lambda _b: self._on_send_waypoint(self.waypoint_draft()))
        box.append(send)
        note = Gtk.Label(
            label="Sending broadcasts the point on the current channel.",
            wrap=True,
            xalign=0,
        )
        note.add_css_class("dim-label")
        box.append(note)
        return box

    def set_nodes(self, rows: list[dict]) -> None:
        self._rows = rows
        self._update_histogram(rows)
        if not self._fitted:
            self._fit(force=False)
        self.area.queue_draw()

    def _update_histogram(self, rows: list[dict]) -> None:
        counts: dict[str, int] = {}
        for row in rows:
            hops = row.get("hops")
            key = "—" if hops is None else str(int(hops))
            counts[key] = counts.get(key, 0) + 1
        if not counts:
            self.histogram.set_label("Hops: no nodes")
            return
        parts = []
        for key in sorted(counts, key=lambda k: 99 if k == "—" else int(k)):
            parts.append(f"{key} hop: {counts[key]}" if key != "—" else f"unknown: {counts[key]}")
        gps = sum(1 for r in rows if r.get("lat") is not None and r.get("lon") is not None)
        self.histogram.set_label(" · ".join(parts) + f"  ·  {gps} on the map")

    def add_waypoint(self, wp: dict) -> None:
        label = Gtk.Label(xalign=0)
        label.set_wrap(True)
        desc = f"\n{wp['description']}" if wp.get("description") else ""
        label.set_text(f"{wp.get('name') or 'Waypoint'}\n{wp['lat']:.5f}, {wp['lon']:.5f}{desc}")
        label.set_margin_top(4)
        label.set_margin_bottom(4)
        label.set_margin_start(6)
        label.set_margin_end(6)
        self.waypoint_list.append(label)

    def waypoint_draft(self) -> dict:
        return {
            "name": self.wp_name.get_text().strip(),
            "lat": self.wp_lat.get_text().strip(),
            "lon": self.wp_lon.get_text().strip(),
            "description": self.wp_desc.get_text().strip(),
        }

    def _fit(self, force: bool) -> None:
        pts = [
            (r["lat"], r["lon"])
            for r in self._rows
            if r.get("lat") is not None and r.get("lon") is not None
        ]
        if not pts:
            return
        lats = [p[0] for p in pts]
        lons = [p[1] for p in pts]
        self.clat = sum(lats) / len(lats)
        self.clon = sum(lons) / len(lons)
        span = max(max(lats) - min(lats), max(lons) - min(lons), 0.15)
        width = self.area.get_width() or 640
        height = self.area.get_height() or 480
        self.k = 0.75 * min(width, height) / span
        self._fitted = True
        if force:
            self.area.queue_draw()

    def _project(self, lat: float, lon: float, width: float, height: float) -> tuple[float, float]:
        x = width / 2 + (lon - self.clon) * self.k
        y = height / 2 - (lat - self.clat) * self.k
        return x, y

    def _draw(self, area, cr, width, height) -> None:
        import time

        color = area.get_color()
        cr.set_source_rgba(color.red, color.green, color.blue, 0.08)
        cr.paint()
        cr.set_source_rgba(color.red, color.green, color.blue, 0.25)
        cr.set_line_width(1)
        # Light graticule, about every degree at the current scale, clamped.
        step = 1.0
        while step * self.k < 40:
            step *= 2
        while step * self.k > 140 and step > 0.25:
            step /= 2
        if step <= 0:
            step = 1.0
        lon0 = math.floor((self.clon - width / 2 / self.k) / step) * step
        lat0 = math.floor((self.clat - height / 2 / self.k) / step) * step
        drawn = 0
        lon = lon0
        while lon < self.clon + width / self.k and drawn < 30:
            x, _y = self._project(self.clat, lon, width, height)
            cr.move_to(x, 0)
            cr.line_to(x, height)
            lon += step
            drawn += 1
        drawn = 0
        lat = lat0
        while lat < self.clat + height / self.k and drawn < 30:
            _x, y = self._project(lat, self.clon, width, height)
            cr.move_to(0, y)
            cr.line_to(width, y)
            lat += step
            drawn += 1
        cr.stroke()

        now = time.time()
        self._screen = []
        labeled = 0
        for row in self._rows:
            lat, lon = row.get("lat"), row.get("lon")
            if lat is None or lon is None:
                continue
            x, y = self._project(lat, lon, width, height)
            if x < -20 or y < -20 or x > width + 20 or y > height + 20:
                continue
            self._screen.append((x, y, row))
            hops = row.get("hops")
            if hops == 0:
                cr.set_source_rgba(0.2, 0.65, 0.35, _age_alpha(row.get("last_heard"), now))
            elif hops is None:
                cr.set_source_rgba(color.red, color.green, color.blue, 0.7)
            else:
                cr.set_source_rgba(0.85, 0.45, 0.15, _age_alpha(row.get("last_heard"), now))
            cr.arc(x, y, 6 if row.get("favorite") else 4.5, 0, 2 * math.pi)
            cr.fill()
            if labeled < 24:
                cr.set_source_rgba(color.red, color.green, color.blue, 0.9)
                cr.move_to(x + 8, y - 4)
                cr.show_text(str(row.get("short") or row.get("long") or ""))
                labeled += 1

        if not self._screen:
            cr.set_source_rgba(color.red, color.green, color.blue, 0.8)
            cr.move_to(16, 28)
            cr.show_text("No GPS positions in the node database yet.")

    def _clicked(self, _gesture, _n, x, y) -> None:
        best = None
        best_d = 14
        for sx, sy, row in self._screen:
            d = math.hypot(sx - x, sy - y)
            if d < best_d:
                best = row
                best_d = d
        if best is not None:
            self._on_node(best["id"])

    def _drag_begin(self, _gesture, _x, _y) -> None:
        self._drag_last = (0.0, 0.0)
        self._fitted = True

    def _drag_update(self, _gesture, x, y) -> None:
        lx, ly = self._drag_last
        dx, dy = x - lx, y - ly
        self._drag_last = (x, y)
        if self.k <= 0:
            return
        self.clon -= dx / self.k
        self.clat += dy / self.k
        self.area.queue_draw()

    def _scrolled(self, _ctrl, _dx, dy) -> bool:
        self._fitted = True
        factor = 0.85 if dy > 0 else 1.18
        self.k = min(4000, max(4, self.k * factor))
        self.area.queue_draw()
        return True
