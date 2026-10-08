"""Node detail: identity, favorite, traceroute, jump to a direct message."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk


def present_node(parent, node: dict, *, on_favorite, on_traceroute, on_message) -> None:
    dialog = Adw.Dialog(title=node.get("long") or "Node")
    dialog.set_content_width(460)
    dialog.set_can_close(True)
    # Floating card over a scrim. The scrim click and Escape call close() and nothing else.
    dialog.set_presentation_mode(Adw.DialogPresentationMode.FLOATING)
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    box.set_margin_top(12)
    box.set_margin_bottom(12)
    box.set_margin_start(12)
    box.set_margin_end(12)

    lines = [
        node.get("id") or "",
        f"Role {node.get('role') or '—'}",
        f"Hops {node['hops'] if node.get('hops') is not None else '—'}",
        f"Battery {node['battery']}%" if node.get("battery") is not None else "Battery —",
        f"SNR {node['snr']}" if node.get("snr") is not None else "SNR —",
        f"Hardware {node['hw']}" if node.get("hw") else "",
    ]
    if node.get("lat") is not None and node.get("lon") is not None:
        lines.append(f"{node['lat']:.5f}, {node['lon']:.5f}")
    text = "\n".join(line for line in lines if line)
    body = Gtk.Label(label=text, xalign=0, selectable=True)
    body.set_can_focus(False)
    box.append(body)

    favorite = Adw.SwitchRow(title="Favorite on this radio")
    favorite.set_active(bool(node.get("favorite")))
    node_id = node.get("id") or ""

    def toggled(row, _pspec) -> None:
        on_favorite(node_id, row.get_active())

    favorite.connect("notify::active", toggled)
    box.append(favorite)

    result = Gtk.Label(label="", xalign=0, wrap=True, selectable=True)
    result.set_can_focus(False)
    row = Gtk.Box(spacing=8)
    trace = Gtk.Button(label="Traceroute")
    trace.connect(
        "clicked",
        lambda _b: _trace(trace, result, node_id, on_traceroute),
    )
    message = Gtk.Button(label="Direct message")
    message.add_css_class("suggested-action")
    message.connect("clicked", lambda _b: (dialog.close(), on_message(node_id)))
    row.append(trace)
    row.append(message)
    box.append(row)
    box.append(result)
    if not node_id:
        favorite.set_sensitive(False)
        trace.set_sensitive(False)
        message.set_sensitive(False)
    # Header bar supplies the close button. It only dismisses the dialog.
    view = Adw.ToolbarView()
    view.add_top_bar(Adw.HeaderBar())
    view.set_content(box)
    dialog.set_child(view)
    dialog.present(parent)


def _trace(button, result, node_id: str, on_traceroute) -> None:
    button.set_sensitive(False)
    result.set_label("Tracing… this can take half a minute.")

    def ok(text: str) -> None:
        button.set_sensitive(True)
        result.set_label(text)

    def err(message: str) -> None:
        button.set_sensitive(True)
        result.set_label(message)

    on_traceroute(node_id, ok, err)
