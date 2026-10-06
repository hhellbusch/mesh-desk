# mesh-desk

A Linux desktop client for [Meshtastic](https://meshtastic.org/). One radio at a time, over Bluetooth, USB serial, or TCP.

It is a GTK front end on the official Python library. Chat history stays in a local SQLite file because the radio does not keep a full inbox.

Tested on Fedora with Cinnamon. It needs Python 3.11 or newer, GTK 4, libadwaita, and PyGObject. Bluetooth also needs BlueZ.

This is not an official Meshtastic application.

## Install

On Fedora:

```bash
sudo dnf install python3-gobject gtk4 libadwaita bluez
pip install --user -r requirements.txt
./run
```

`pip install .` also works when PyGObject comes from the system Python, not from a virtualenv that cannot see GTK.

Copy `app.meshdesk.MeshDesk.desktop` to `~/.local/share/applications/` if you want a menu entry. `Exec` expects `mesh-desk` on `PATH` (`pip install --user` puts it in `~/.local/bin`).

## Use

**Chat** — channels and direct messages. Click a node to open a direct thread. **Info** shows role, battery, hardware, position, favorite, and traceroute.

**Map** — nodes that have sent a GPS position, plus a hop histogram. Drag to pan, scroll to zoom. No map tiles, so the map still works with the internet down. Waypoints on this page are broadcast on the primary channel after a confirm.

**Radio** — settings read from the connected firmware: user, device, LoRa, position, power, display, network, Bluetooth, security, channels, and modules the firmware includes. Each section has its own Save. Save asks first, then the radio reboots and drops the link. A channel key can be set to the public default or replaced with a new random key. The key is not shown and is not stored by this app. Security private keys and admin keys are not editable.

**Log** — a short rolling summary of packets. Not a hex dump.

Bluetooth addresses you connect are remembered in `$XDG_CONFIG_HOME/mesh-desk/radios.json` (usually `~/.config/mesh-desk/radios.json`). Message history is `$XDG_DATA_HOME/mesh-desk/messages.sqlite`. Neither file is part of this repository.

If a Bluetooth connect fails, press a button on the radio to wake it, and disconnect any other client first. BlueZ allows one session. Quit mesh-desk before using the `meshtastic` CLI against the same radio.

The window follows the desktop light/dark preference. On Cinnamon that is the GTK theme name. libadwaita does not wear the rest of the desktop theme.

## Not in this app

- Firmware flashing. That stays with the Meshtastic project.
- Several radios connected at the same time.

Administering a second node through the one you are connected to is planned. It uses the same settings screens, sent over the mesh, and it will not write until that node's config has been read.

## Development

`pytest` runs without a radio. Bluetooth connect and a real Save stay a manual check. Read `AGENTS.md` before changing how the app talks to a radio.

## License

GPL-3.0-only, the same license as the Meshtastic Python library this program imports.
