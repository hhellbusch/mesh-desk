"""Build a settings group from a protobuf message.

Widgets follow the field type. Bytes and nested messages are skipped so a
Save cannot wipe keys or structured sub-messages the form does not show.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk
from google.protobuf.descriptor import FieldDescriptor as FD

# Names we never put in a form, even if the type would allow it.
SKIP_NAMES = {"private_key", "public_key", "admin_key", "sessionkey"}

ACRONYMS = {"tx", "rx", "gps", "psk", "mqtt", "lora", "wifi", "ip", "id", "ntp", "gpio"}

RANGES = {
    "hop_limit": (0, 7, 1),
    "tx_power": (0, 36, 1),
    "fixed_pin": (0, 999999, 1),
    "spread_factor": (5, 12, 1),
    "coding_rate": (4, 8, 1),
    "bandwidth": (0, 2000, 1),
    "channel_num": (0, 255, 1),
    "position_precision": (0, 32, 1),
    "position_broadcast_secs": (0, 86400, 30),
    "gps_update_interval": (0, 86400, 1),
    "screen_on_secs": (0, 3600, 1),
}


def field_title(name: str) -> str:
    words = []
    for word in name.split("_"):
        words.append(word.upper() if word in ACRONYMS else word.capitalize())
    return " ".join(words)


def _range_for(field) -> tuple[float, float, float]:
    if field.name in RANGES:
        return RANGES[field.name]
    if "gpio" in field.name:
        return (-1, 255, 1)
    if "frequency" in field.name:
        return (0, 1000, 0.001)
    if field.type == FD.TYPE_FLOAT or field.type == FD.TYPE_DOUBLE:
        return (-1_000_000, 1_000_000, 0.01)
    if field.type in (FD.TYPE_INT32, FD.TYPE_SINT32, FD.TYPE_SFIXED32):
        return (-1_000_000, 1_000_000, 1)
    return (0, 1_000_000, 1)


def _usable(field) -> bool:
    if field.name in SKIP_NAMES or field.is_repeated:
        return False
    if field.type in (FD.TYPE_MESSAGE, FD.TYPE_GROUP, FD.TYPE_BYTES):
        return False
    return field.type in (
        FD.TYPE_BOOL,
        FD.TYPE_STRING,
        FD.TYPE_ENUM,
        FD.TYPE_FLOAT,
        FD.TYPE_DOUBLE,
        FD.TYPE_INT32,
        FD.TYPE_INT64,
        FD.TYPE_UINT32,
        FD.TYPE_UINT64,
        FD.TYPE_SINT32,
        FD.TYPE_SINT64,
        FD.TYPE_FIXED32,
        FD.TYPE_FIXED64,
        FD.TYPE_SFIXED32,
        FD.TYPE_SFIXED64,
    )


class ProtoForm:
    def __init__(self, message, title: str, description: str = "") -> None:
        self.group = Adw.PreferencesGroup(title=title, description=description)
        self._fields: list[tuple] = []
        for field in message.DESCRIPTOR.fields:
            if not _usable(field):
                continue
            row = self._row_for(field)
            if row is None:
                continue
            self.group.add(row)
            self._fields.append((field, row))

    @property
    def empty(self) -> bool:
        return not self._fields

    def _row_for(self, field):
        title = field_title(field.name)
        if field.type == FD.TYPE_BOOL:
            return Adw.SwitchRow(title=title)
        if field.type == FD.TYPE_ENUM:
            row = Adw.ComboRow(title=title)
            values = list(field.enum_type.values)
            row.set_model(Gtk.StringList.new([v.name for v in values]))
            row._enum_numbers = [int(v.number) for v in values]
            return row
        if field.type == FD.TYPE_STRING:
            secret = field.name.endswith("_psk") or "password" in field.name
            row = Adw.PasswordEntryRow(title=title) if secret else Adw.EntryRow(title=title)
            return row
        low, high, step = _range_for(field)
        row = Adw.SpinRow.new_with_range(low, high, step)
        row.set_title(title)
        if field.type in (FD.TYPE_FLOAT, FD.TYPE_DOUBLE) or "frequency" in field.name:
            row.set_digits(3)
        return row

    def fill(self, message) -> None:
        for field, row in self._fields:
            value = getattr(message, field.name)
            if field.type == FD.TYPE_BOOL:
                row.set_active(bool(value))
            elif field.type == FD.TYPE_ENUM:
                numbers = row._enum_numbers
                try:
                    row.set_selected(numbers.index(int(value)))
                except ValueError:
                    row.set_selected(0)
            elif field.type == FD.TYPE_STRING:
                row.set_text(value or "")
            else:
                low = row.get_adjustment().get_lower()
                high = row.get_adjustment().get_upper()
                number = float(value)
                row.set_value(min(high, max(low, number)))

    def collect(self) -> dict:
        data = {}
        for field, row in self._fields:
            if field.type == FD.TYPE_BOOL:
                data[field.name] = bool(row.get_active())
            elif field.type == FD.TYPE_ENUM:
                idx = row.get_selected()
                numbers = row._enum_numbers
                if idx < 0 or idx >= len(numbers):
                    idx = 0
                data[field.name] = numbers[idx]
            elif field.type == FD.TYPE_STRING:
                data[field.name] = row.get_text()
            elif field.type in (FD.TYPE_FLOAT, FD.TYPE_DOUBLE):
                data[field.name] = float(row.get_value())
            else:
                data[field.name] = int(row.get_value())
        return data


def apply_fields(message, data: dict) -> None:
    """Write collected values onto the protobuf. Unknown names are ignored."""
    fields = message.DESCRIPTOR.fields_by_name
    for name, value in data.items():
        field = fields.get(name)
        if field is None or not _usable(field):
            continue
        if field.type == FD.TYPE_STRING:
            setattr(message, name, str(value))
        elif field.type in (FD.TYPE_FLOAT, FD.TYPE_DOUBLE):
            setattr(message, name, float(value))
        elif field.type == FD.TYPE_BOOL:
            setattr(message, name, bool(value))
        else:
            setattr(message, name, int(value))
