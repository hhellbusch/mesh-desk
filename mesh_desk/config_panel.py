"""Radio admin. One Save per section. The radio reboots after a save.

Channel keys can be replaced (public default or a newly generated key) but
are never shown. Security private keys and admin keys are not on the form.
A security Save sends the key bytes already stored on the radio.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from meshtastic.protobuf import channel_pb2
from meshtastic.util import genPSK256

from mesh_desk.forms import ProtoForm, apply_fields
from mesh_desk.radio_help import help_for, present_help

Role = channel_pb2.Channel.Role

RADIO_SECTIONS = (
    ("device", "Device", ""),
    ("position", "Position", ""),
    ("power", "Power", "Sleep and shutdown timers the firmware exposes."),
    ("network", "Network", "Wi-Fi and Ethernet. A T-Echo has neither."),
    ("display", "Display", ""),
    ("lora", "LoRa", "Region and modem preset have to match the rest of the mesh."),
    ("bluetooth", "Bluetooth", ""),
    ("security", "Security", "Private key and admin keys stay on the radio."),
)

MODULE_BITS = {
    "mqtt": 0x1,
    "serial": 0x2,
    "external_notification": 0x4,
    "store_forward": 0x8,
    "range_test": 0x10,
    "telemetry": 0x20,
    "canned_message": 0x40,
    "audio": 0x80,
    "remote_hardware": 0x100,
    "neighbor_info": 0x200,
    "ambient_lighting": 0x400,
    "detection_sensor": 0x800,
    "paxcounter": 0x1000,
}

SECTION_BITS = {
    "bluetooth": 0x2000,
    "network": 0x4000,
}

MODULE_TITLES = {
    "mqtt": "MQTT",
}


def psk_label(psk: bytes) -> str:
    if psk == bytes([0]):
        return "No encryption"
    if len(psk) <= 1:
        return "Public default key"
    return f"Private key ({len(psk)} bytes)"


def _excluded(metadata) -> int:
    if metadata is None:
        return 0
    try:
        return int(getattr(metadata, "excluded_modules", 0) or 0)
    except (TypeError, ValueError):
        return 0


class ConfigPanel(Adw.PreferencesPage):
    """on_save(heading, body, prepare) where prepare(node) -> list of write callables."""

    def __init__(self, on_save) -> None:
        super().__init__()
        self._on_save = on_save
        self._groups: list[Adw.PreferencesGroup] = []
        self.set_title("Radio")
        self.set_description("Each Save writes that section and the radio reboots.")
        self._placeholder("Connect a radio to load its settings.")

    def _placeholder(self, text: str) -> None:
        self._remember(Adw.PreferencesGroup(title="Radio", description=text))

    def _remember(self, group: Adw.PreferencesGroup) -> None:
        self.add(group)
        self._groups.append(group)

    def _reset(self) -> None:
        for group in self._groups:
            self.remove(group)
        self._groups.clear()

    def clear(self) -> None:
        self._reset()
        self._placeholder("Connect a radio to load its settings.")
        self.set_sensitive(True)

    def load(self, node, metadata=None) -> None:
        self._reset()
        self.set_sensitive(True)
        mask = _excluded(metadata)
        self._add_user(node)
        for name, title, description in RADIO_SECTIONS:
            bit = SECTION_BITS.get(name, 0)
            if bit and mask & bit:
                continue
            message = getattr(node.localConfig, name, None)
            if message is None or message.DESCRIPTOR.fields is None:
                continue
            form = ProtoForm(message, title, description)
            if form.empty:
                continue
            form.fill(message)
            if name == "security":
                self._add_public_key(form.group, message)
            self._info(form.group, name, title)
            self._section_save(form, title, name, module=False)
            self._remember(form.group)
        self._add_channels(node)
        self._add_modules(node, mask)

    def _add_public_key(self, group, security) -> None:
        raw = bytes(security.public_key)
        text = raw.hex() if raw else "No public key yet"
        if len(text) > 48:
            text = text[:24] + "…" + text[-16:]
        group.add(Adw.ActionRow(title="Public key", subtitle=text))

    def _add_user(self, node) -> None:
        group = Adw.PreferencesGroup(title="User")
        long_name = Adw.EntryRow(title="Long name")
        short_name = Adw.EntryRow(title="Short name")
        short_name.set_max_length(4)
        licensed = Adw.SwitchRow(title="Licensed operator")
        me = _my_user(node)
        long_name.set_text(me.get("longName") or me.get("long_name") or "")
        short_name.set_text(me.get("shortName") or me.get("short_name") or "")
        licensed.set_active(bool(me.get("isLicensed") or me.get("is_licensed")))
        group.add(long_name)
        group.add(short_name)
        group.add(licensed)

        def collect():
            return {
                "long_name": long_name.get_text(),
                "short_name": short_name.get_text(),
                "licensed": licensed.get_active(),
            }

        self._info(group, "user", "User")
        self._button(
            group,
            "Save the node name and reboot the radio?",
            "The long name and a short name of 1 to 4 characters are both required.",
            collect,
            _prepare_owner,
        )
        self._remember(group)

    def _section_save(self, form: ProtoForm, title: str, section: str, module: bool) -> None:
        def collect():
            return form.collect()

        def prepare(node, data, section=section, module=module):
            target = getattr(node.moduleConfig if module else node.localConfig, section)
            apply_fields(target, data)

            def write(node=node, section=section):
                node.writeConfig(section)

            return [write]

        self._button(
            form.group,
            f"Save {title} and reboot the radio?",
            "Bluetooth will drop while the radio restarts.",
            collect,
            prepare,
        )

    def _button(self, group, heading: str, body: str, collect, prepare) -> None:
        button = Gtk.Button(label="Save")
        button.add_css_class("suggested-action")

        def clicked(_btn, heading=heading, body=body, collect=collect, prepare=prepare) -> None:
            data = collect()

            def bound(node, data=data, prepare=prepare):
                return prepare(node, data)

            self._on_save(heading, body, bound)

        button.connect("clicked", clicked)
        self._add_header_button(group, button)

    def _info(self, group, key: str, title: str) -> None:
        button = Gtk.Button(label="Info")
        button.add_css_class("flat")
        button.connect("clicked", lambda _b, key=key, title=title: present_help(self, title, help_for(key)))
        self._add_header_button(group, button)

    def _add_header_button(self, group, button) -> None:
        existing = group.get_header_suffix()
        if existing is None:
            group.set_header_suffix(button)
            return
        if isinstance(existing, Gtk.Box):
            existing.append(button)
            return
        box = Gtk.Box(spacing=6)
        group.set_header_suffix(None)
        box.append(existing)
        box.append(button)
        group.set_header_suffix(box)

    def _add_channels(self, node) -> None:
        channels = list(node.channels or [])
        if not channels:
            self._remember(
                Adw.PreferencesGroup(
                    title="Channels",
                    description="The radio has not sent a channel list yet.",
                )
            )
            return
        for ch in channels:
            if ch.role == Role.DISABLED:
                continue
            self._remember(self._channel_group(ch))
        if any(ch.role == Role.DISABLED for ch in channels):
            group = Adw.PreferencesGroup(
                title="Add a channel",
                description="Uses the next free slot, a new random key, and no MQTT uplink.",
            )
            name = Adw.EntryRow(title="Name")
            name.set_text("Private")
            group.add(name)
            self._info(group, "add_channel", "Add a channel")

            def collect(name=name):
                return name.get_text()

            self._button(
                group,
                "Add a secondary channel and reboot the radio?",
                "A new random key is written. It is not shown and not saved to disk. MQTT uplink stays off.",
                collect,
                lambda node, data: _prepare_add_channel(node, data),
            )
            self._remember(group)

    def _channel_group(self, ch) -> Adw.PreferencesGroup:
        index = int(ch.index)
        title = "Primary channel" if ch.role == Role.PRIMARY else f"Channel {index}"
        settings = ch.settings
        group = Adw.PreferencesGroup(title=title)
        help_key = "channel_primary" if ch.role == Role.PRIMARY else "channel_secondary"
        self._info(group, help_key, title)
        name = Adw.EntryRow(title="Name")
        name.set_text(settings.name or "")
        uplink = Adw.SwitchRow(title="MQTT uplink")
        uplink.set_active(bool(settings.uplink_enabled))
        downlink = Adw.SwitchRow(title="MQTT downlink")
        downlink.set_active(bool(settings.downlink_enabled))
        muted = Adw.SwitchRow(title="Muted")
        muted.set_active(bool(settings.module_settings.is_muted))
        precision = Adw.SpinRow.new_with_range(0, 32, 1)
        precision.set_title("Position precision (bits, 0 hides the position)")
        precision.set_value(int(settings.module_settings.position_precision))
        key_row = Adw.ActionRow(title="Encryption", subtitle=psk_label(bytes(settings.psk)))
        pending: dict[str, bytes | None] = {"psk": None}

        def mark(psk: bytes, subtitle: str) -> None:
            pending["psk"] = psk
            key_row.set_subtitle(subtitle + " — pending save")

        public = Gtk.Button(label="Use public key")
        public.connect("clicked", lambda _b: mark(bytes([1]), "Public default key"))
        generate = Gtk.Button(label="Generate private key")
        generate.connect("clicked", lambda _b: mark(genPSK256(), "New private key"))
        key_row.add_suffix(public)
        key_row.add_suffix(generate)
        for widget in (name, uplink, downlink, muted, precision, key_row):
            group.add(widget)

        if ch.role == Role.SECONDARY:
            delete = Gtk.Button(label="Delete")
            delete.add_css_class("destructive-action")
            delete.connect(
                "clicked",
                lambda _b, index=index: self._on_save(
                    f"Delete channel {index} and reboot the radio?",
                    "Only a secondary channel can be deleted. Nodes still using it will stop hearing you.",
                    lambda node, index=index: _prepare_delete(node, index),
                ),
            )
            self._add_header_button(group, delete)

        def collect(
            index=index,
            name=name,
            uplink=uplink,
            downlink=downlink,
            muted=muted,
            precision=precision,
            pending=pending,
        ):
            return {
                "index": index,
                "name": name.get_text(),
                "uplink": uplink.get_active(),
                "downlink": downlink.get_active(),
                "muted": muted.get_active(),
                "precision": int(precision.get_value()),
                "psk": pending["psk"],
            }

        button = Gtk.Button(label="Save")
        button.add_css_class("suggested-action")

        def clicked(_btn) -> None:
            data = collect()
            body = "Bluetooth will drop while the radio restarts."
            if data["psk"] is not None and index == 0:
                body = "Channel 0's key will change. Other nodes need the same key. " + body
            elif data["psk"] is not None:
                body = "This channel's key will change. The new key is not shown. " + body
            self._on_save(
                f"Save channel {index} and reboot the radio?",
                body,
                lambda node, data=data: _prepare_channel(node, data),
            )

        button.connect("clicked", clicked)
        self._add_header_button(group, button)
        return group

    def _add_modules(self, node, mask: int) -> None:
        module_config = node.moduleConfig
        for field in module_config.DESCRIPTOR.fields:
            if field.message_type is None:
                continue
            bit = MODULE_BITS.get(field.name, 0)
            if bit and mask & bit:
                continue
            message = getattr(module_config, field.name)
            title = MODULE_TITLES.get(field.name, field.name.replace("_", " ").title())
            form = ProtoForm(message, title)
            if form.empty:
                continue
            form.fill(message)
            self._info(form.group, field.name, title)
            self._section_save(form, title, field.name, module=True)
            self._remember(form.group)


def _my_user(node) -> dict:
    iface = getattr(node, "iface", None)
    if iface is None or getattr(iface, "myInfo", None) is None:
        return {}
    num = iface.myInfo.my_node_num
    found = (iface.nodesByNum.get(num) or {}).get("user") or {}
    return found


def _prepare_owner(node, data: dict):
    long_name = str(data.get("long_name") or "").strip()
    short_name = str(data.get("short_name") or "").strip()[:4]
    if not long_name or not short_name:
        raise RuntimeError("Long name and short name are required")
    licensed = bool(data.get("licensed"))

    def write(node=node, long_name=long_name, short_name=short_name, licensed=licensed):
        node.setOwner(long_name=long_name, short_name=short_name, is_licensed=licensed)

    return [write]


def _prepare_channel(node, data: dict):
    index = int(data["index"])
    channels = list(node.channels or [])
    if index < 0 or index >= len(channels):
        raise RuntimeError(f"No channel {index}")
    ch = channels[index]
    ch.settings.name = str(data["name"]).strip()
    ch.settings.uplink_enabled = bool(data["uplink"])
    ch.settings.downlink_enabled = bool(data["downlink"])
    ch.settings.module_settings.is_muted = bool(data["muted"])
    ch.settings.module_settings.position_precision = int(data["precision"])
    psk = data.get("psk")
    if psk is not None:
        ch.settings.psk = psk

    def write(node=node, index=index):
        node.writeChannel(index)

    return [write]


def _prepare_add_channel(node, name: str):
    clean = str(name).strip()
    if not clean:
        raise RuntimeError("Channel name is required")
    ch = node.getDisabledChannel()
    if ch is None:
        raise RuntimeError("No free channel slot")
    ch.role = Role.SECONDARY
    ch.settings.name = clean
    ch.settings.psk = genPSK256()
    ch.settings.uplink_enabled = False
    ch.settings.downlink_enabled = False
    index = int(ch.index)

    def write(node=node, index=index):
        node.writeChannel(index)

    return [write]


def _prepare_delete(node, index: int):
    channels = list(node.channels or [])
    if index < 0 or index >= len(channels):
        raise RuntimeError(f"No channel {index}")
    if channels[index].role != Role.SECONDARY:
        raise RuntimeError("Only a secondary channel can be deleted")

    def write(node=node, index=index):
        node.deleteChannel(index)

    return [write]
