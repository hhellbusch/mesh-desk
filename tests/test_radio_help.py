"""Radio page explanations stay explanatory and do not include secrets."""

import re

from mesh_desk.radio_help import help_for

_MAC = re.compile(r"(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}")


def test_lora_explains_hops_and_frequency_slot() -> None:
    text = help_for("lora")
    assert "Hop Limit" in text
    assert "frequency slot" in text
    assert "chat channels" in text
    assert "reboots" in text


def test_security_does_not_offer_the_private_key() -> None:
    text = help_for("security").lower()
    assert "private key" in text
    assert "cannot show or edit" in text


def test_primary_channel_says_the_default_key_is_public() -> None:
    text = help_for("channel_primary")
    assert "public default key" in text
    assert "Generate Private Key" in text
    assert "Zero does not share a location" in text


def test_unknown_module_still_says_save_reboots() -> None:
    text = help_for("not_a_real_module")
    assert "optional firmware module" in text
    assert "reboots" in text


def test_help_text_has_no_radio_address() -> None:
    for key in ("user", "device", "lora", "bluetooth", "channel_primary", "mqtt"):
        assert _MAC.search(help_for(key)) is None
