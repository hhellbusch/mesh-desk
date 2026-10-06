# mesh-desk

Read this before changing the app. `README.md` is for someone installing it.

This is a GTK front end on the official Meshtastic Python library. Do not add a second Bluetooth stack or a second protobuf stack.

## Radio session

One live radio. BlueZ allows one session. Quit mesh-desk before the `meshtastic` CLI uses the same radio.

Callbacks from the library are off the GTK thread. Widget updates go through `GLib.idle_add`.

Packet listeners must accept the `interface` argument. The library sends it on every `meshtastic.receive` publish. A listener that omits the name makes every packet raise.

Do not call library methods that `sys.exit` on failure. That includes `requestConfig`, `sendTraceRoute`, `setOwner` with an empty name, `writeConfig` with a bad section name, and `deleteChannel` on the primary channel.

## Config writes

A Save reboots the radio and drops the link. Save stays explicit. Do not write config to try the UI.

`RadioSession.perform_save` is the only write path. Remote admin passes `config_loaded=True` only after that node's config has been read. `config_loaded=False` raises and does not call `prepare`. A write of a config that was never read can wipe the node.

Forms skip byte fields, repeated fields, and nested messages. `apply_fields` ignores `private_key`, `public_key`, `admin_key`, and `sessionkey`. A Save must not clear a key the screen never showed.

Channel keys are never shown, logged, or stored. The packet log is a short summary, not a hex dump.

## What stays off the machine and out of git

Do not print, log, or commit channel keys, private keys, admin keys, radio names, Bluetooth addresses, or coordinates. Remembered radios live in `$XDG_CONFIG_HOME/mesh-desk/radios.json`. Messages live in `$XDG_DATA_HOME/mesh-desk/messages.sqlite`. Neither file belongs in this repository.

## Out of scope

Firmware flashing stays with the Meshtastic project. Several radios connected at the same time stays out. Administering a second node through the connected radio is in scope, and it uses the read-before-write rule above.

## Tests

Behavior that can be proved without a radio gets a pytest. Bluetooth connect, quit, and a real Save stay a manual check.
