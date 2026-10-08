"""Explanations for the Radio page. Info never writes config."""

from __future__ import annotations

_REBOOT = (
    "Save writes this section to the radio you are connected to. "
    "That radio reboots and the Bluetooth link drops. Other radios are not changed."
)

_SECTIONS = {
    "user": (
        "Long name is what other people see in their node list. "
        "Short name is at most four characters, used where the long name does not fit.\n\n"
        "Licensed operator is for a licensed amateur radio operator. "
        "Turning it on disables encryption on this radio. Leave it off unless you hold that license."
    ),
    "device": (
        "Role is this radio's job.\n\n"
        "Client is a normal radio you carry. It hears the mesh and rebroadcasts when it can. "
        "Client Mute hears the mesh and does not rebroadcast. "
        "Client Hidden does not announce itself, so other people are less likely to see it. "
        "Client Base is a radio that stays in one place and relays for your own radios.\n\n"
        "Router and Repeater are for a radio you place as infrastructure. "
        "A Router rebroadcasts ahead of handhelds and can make nearby radios harder to hear. "
        "Use Client for a radio you carry.\n\n"
        "Tracker, Sensor, and TAK are special jobs. Leave them unless you mean to use that job.\n\n"
        "Rebroadcast Mode ALL is the usual setting. LOCAL ONLY keeps this radio from passing along other people's packets."
    ),
    "position": (
        "These settings control the location this radio transmits.\n\n"
        "GPS Mode and GPS Enabled decide whether it uses its own GPS. "
        "Position Broadcast Secs is how often it tells the mesh where it is. "
        "Smart broadcast sends an update when the radio has moved, instead of only on that timer.\n\n"
        "Fixed Position uses a location you set. That is for a radio that stays indoors.\n\n"
        "How precise that location looks on a channel is set on the channel itself, further down this page. "
        "Zero there means the channel does not share a location."
    ),
    "power": (
        "These timers decide when the radio sleeps or shuts down. "
        "A radio you carry can stay awake. A radio on solar power often uses the timers."
    ),
    "network": (
        "Wi-Fi and Ethernet. Many handhelds do not have either. Leave Wi-Fi off on a radio that has none.\n\n"
        "The Wi-Fi password is written to the radio. This app does not keep a copy."
    ),
    "display": (
        "This is the radio's own screen, not this app. "
        "Screen On Secs is how long that screen stays lit."
    ),
    "lora": (
        "The radios you want to hear have to share this section.\n\n"
        "Region has to be legal where you are. A radio set to a different region will not hear this mesh.\n\n"
        "Modem Preset Long Fast is the usual public mesh. "
        "Use Preset should stay on, so the preset chooses bandwidth and spreading. "
        "Changing the preset is how you leave the public mesh.\n\n"
        "Hop Limit is how many radios your own packet may be passed through. "
        "Zero reaches only radios that hear you directly. Three is common. Seven is the maximum.\n\n"
        "Channel Num picks a frequency slot inside the region. "
        "The chat channels further down this page are a different thing. "
        "Slot 0 is the usual one. Another slot will not hear the usual mesh.\n\n"
        "TX Enabled lets the radio transmit. TX Power is how strongly it transmits. "
        "Higher reaches farther and uses more battery."
    ),
    "bluetooth": (
        "This is how a phone or this app connects to the radio. It is not how the radio talks to other radios.\n\n"
        "Enabled lets a Bluetooth client connect. "
        "Random PIN asks for a new code each time. "
        "Fixed PIN uses the number in Fixed Pin. "
        "No PIN lets anyone nearby connect. Fixed PIN is the usual choice.\n\n"
        "The PIN is the pairing code. It is not a channel key."
    ),
    "security": (
        "The public key identifies this radio. It is safe to read.\n\n"
        "The private key and the admin keys stay on the radio. This page cannot show or edit them. "
        "Saving this section still reboots the radio, and it does not reveal those keys."
    ),
    "channel_primary": (
        "This is the channel your radio uses for ordinary chat. "
        "A new radio names it LongFast and uses the public default key. "
        "Anyone running Meshtastic can read that.\n\n"
        "The name is a label. The key is what lets another radio read the channel. "
        "Use Public Key puts back the shared Meshtastic key. "
        "Generate Private Key makes a key only radios you share it with can read. "
        "The key is never shown. Changing the primary key means your other radios stop hearing you until they have the same key.\n\n"
        "MQTT Uplink copies this channel onto an internet server. Leave it off if you do not want these messages on the public internet map. "
        "MQTT Downlink accepts messages from that server back onto the radio mesh.\n\n"
        "Muted means this radio does not notify you for the channel.\n\n"
        "Position precision is how exact a location is on this channel. "
        "Zero does not share a location. A smaller number is a coarser area. 32 is the full GPS reading."
    ),
    "channel_secondary": (
        "An extra channel beside the primary one. "
        "Other radios hear it when they have the same name and the same key.\n\n"
        "Generate Private Key makes a new key and does not show it. "
        "MQTT Uplink and Downlink copy the channel to and from an internet server.\n\n"
        "Delete removes the channel from this radio. Radios that still have it are unchanged."
    ),
    "add_channel": (
        "This fills the next free channel slot. "
        "The new channel gets a random key, and MQTT stays off. The key is not shown."
    ),
}

_MODULES = {
    "mqtt": (
        "MQTT is a gateway between the radio mesh and an internet server. "
        "A handheld usually leaves the module off. "
        "The per-channel MQTT switches, above, decide which chat channels are published."
    ),
    "telemetry": (
        "Telemetry is the battery, environment, and device readings this radio broadcasts. "
        "A shorter interval means more packets on the mesh."
    ),
    "store_forward": (
        "Store and forward lets a radio that stays powered keep messages for a radio that was out of range. "
        "Turn it on for a home radio. A handheld usually leaves it off."
    ),
    "neighbor_info": (
        "Neighbor info tells other radios which nodes this one can hear directly. "
        "It makes the mesh easier to picture, and it adds traffic."
    ),
    "range_test": (
        "Range test sends regular pings so you can walk and see where the signal drops. "
        "Turn it off when you are done. It is noisy for everyone on the channel."
    ),
    "serial": "Serial talks to a device plugged into this radio. Leave it off unless you have that device.",
    "external_notification": (
        "External notification rings a buzzer, LED, or other output when a message arrives."
    ),
    "canned_message": "Canned messages are replies stored on the radio, sent from its own buttons.",
    "detection_sensor": "Detection sensor watches a pin and can send a message when that input changes.",
    "paxcounter": "Paxcounter estimates how many Wi-Fi and Bluetooth devices are nearby. It adds traffic.",
    "ambient_lighting": "Ambient lighting drives LEDs on radios that have them.",
    "audio": "Audio is for a radio with a codec or I2S audio hardware. A typical handheld leaves it off.",
    "remote_hardware": (
        "Remote hardware lets another node read or set pins on this radio. "
        "Leave it off unless you mean to allow that."
    ),
    "statusmessage": "Status message is a short text this radio can broadcast about itself.",
    "traffic_management": "Traffic management slows this radio down when the channel is busy.",
    "tak": "TAK connects this radio to a Team Awareness Kit system. Leave it off unless you use TAK.",
}

_GENERIC_MODULE = (
    "This is an optional firmware module. "
    "Leave it off unless you mean to use it."
)


def help_for(key: str) -> str:
    body = _SECTIONS.get(key) or _MODULES.get(key) or _GENERIC_MODULE
    return f"{body}\n\n{_REBOOT}"


def present_help(parent, title: str, body: str) -> None:
    import gi

    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Adw, Gtk, Pango

    dialog = Adw.Dialog(title=title)
    dialog.set_content_width(440)
    dialog.set_can_close(True)
    dialog.set_presentation_mode(Adw.DialogPresentationMode.FLOATING)
    label = Gtk.Label(label=body, xalign=0, yalign=0, wrap=True, selectable=True)
    label.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
    label.set_max_width_chars(46)
    label.set_margin_top(12)
    label.set_margin_bottom(12)
    label.set_margin_start(12)
    label.set_margin_end(12)
    scroll = Gtk.ScrolledWindow()
    scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    scroll.set_min_content_height(160)
    scroll.set_max_content_height(420)
    scroll.set_propagate_natural_height(True)
    scroll.set_child(label)
    view = Adw.ToolbarView()
    view.add_top_bar(Adw.HeaderBar())
    view.set_content(scroll)
    dialog.set_child(view)
    dialog.present(parent)
