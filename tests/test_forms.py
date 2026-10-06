"""Settings forms must not be able to wipe keys they do not show."""

from meshtastic.protobuf import config_pb2

from mesh_desk.forms import apply_fields


def test_apply_fields_leaves_keys_alone() -> None:
    security = config_pb2.Config.SecurityConfig()
    security.private_key = b"\x01\x02"
    security.admin_key.append(b"\x03\x04")
    security.public_key = b"\x05\x06"

    apply_fields(
        security,
        {
            "private_key": b"\xff" * 32,
            "admin_key": b"\xff" * 32,
            "public_key": b"\xff" * 32,
            "sessionkey": b"\xff",
            "is_managed": True,
        },
    )

    assert security.private_key == b"\x01\x02"
    assert list(security.admin_key) == [b"\x03\x04"]
    assert security.public_key == b"\x05\x06"
    assert security.is_managed is True


def test_apply_fields_writes_a_normal_setting() -> None:
    lora = config_pb2.Config.LoRaConfig()
    lora.hop_limit = 3
    apply_fields(lora, {"hop_limit": 7, "no_such_field": 1})
    assert lora.hop_limit == 7
