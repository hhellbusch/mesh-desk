"""Follow the desktop light/dark preference.

libadwaita does not wear the Cinnamon GTK theme (Mint-Y). It does follow
light vs dark when we tell StyleManager. Cinnamon reports that through the
theme name; GNOME reports it through color-scheme.
"""

from __future__ import annotations

import gi

gi.require_version("Adw", "1")
from gi.repository import Adw, Gio


def _prefers_dark() -> bool:
    theme = ""
    try:
        theme = Gio.Settings.new("org.cinnamon.desktop.interface").get_string("gtk-theme")
    except Exception:
        theme = ""
    scheme = "default"
    try:
        scheme = Gio.Settings.new("org.gnome.desktop.interface").get_string("color-scheme")
    except Exception:
        scheme = "default"
    if scheme in ("prefer-dark", "dark"):
        return True
    if scheme in ("prefer-light", "light"):
        return False
    return "dark" in theme.lower()


def apply_os_color_scheme() -> None:
    scheme = Adw.ColorScheme.FORCE_DARK if _prefers_dark() else Adw.ColorScheme.FORCE_LIGHT
    Adw.StyleManager.get_default().set_color_scheme(scheme)


def watch_os_color_scheme() -> None:
    apply_os_color_scheme()
    for schema, key in (
        ("org.cinnamon.desktop.interface", "gtk-theme"),
        ("org.gnome.desktop.interface", "color-scheme"),
    ):
        try:
            settings = Gio.Settings.new(schema)
        except Exception:
            continue
        settings.connect(f"changed::{key}", lambda *_a: apply_os_color_scheme())
