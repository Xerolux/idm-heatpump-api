"""Boundary tests for register value encoding, decoding, and write validation."""

from __future__ import annotations

import asyncio

import pytest

from idm_heatpump.client import DataType, IdmModbusClient, RegisterDef, RegisterType, WriteClass

from .fake_modbus import FakeModbusTransport


@pytest.mark.parametrize(
    ("datatype", "minimum", "maximum"),
    [
        (DataType.UCHAR, 0, 255),
        (DataType.INT8, -128, 127),
        (DataType.INT16, -32768, 32767),
        (DataType.UINT16, 0, 65535),
    ],
)
def test_integer_encode_decode_boundaries(datatype: DataType, minimum: int, maximum: int) -> None:
    client = IdmModbusClient("127.0.0.1")
    reg = RegisterDef(1, datatype, datatype.value)

    for value in (minimum, maximum):
        encoded = client.encode_value(value, reg)
        assert client.decode_value(encoded, reg) == value


@pytest.mark.parametrize(
    ("datatype", "invalid_values"),
    [
        (DataType.UCHAR, [-1, 256]),
        (DataType.INT8, [-129, 128]),
        (DataType.INT16, [-32769, 32768]),
        (DataType.UINT16, [-1, 65536]),
    ],
)
def test_integer_encode_rejects_out_of_range_values(
    datatype: DataType, invalid_values: list[int]
) -> None:
    client = IdmModbusClient("127.0.0.1")
    reg = RegisterDef(1, datatype, datatype.value)

    for value in invalid_values:
        with pytest.raises(ValueError, match="out of .* range"):
            client.encode_value(value, reg)


def test_multiplier_round_trip_uses_scaled_wire_values() -> None:
    client = IdmModbusClient("127.0.0.1")
    reg = RegisterDef(1, DataType.UINT16, "scaled", multiplier=0.1)

    assert client.encode_value(12.3, reg) == [123]
    assert client.decode_value([123], reg) == 12.3


@pytest.mark.parametrize(("value", "expected"), [(False, [0]), (True, [1])])
def test_bool_encoding(value: bool, expected: list[int]) -> None:
    client = IdmModbusClient("127.0.0.1")
    reg = RegisterDef(1, DataType.BOOL, "bool")

    assert client.encode_value(value, reg) == expected
    assert client.decode_value(expected, reg) is value


def test_bitflag_encoding_masks_to_low_byte() -> None:
    client = IdmModbusClient("127.0.0.1")
    reg = RegisterDef(1, DataType.BITFLAG, "flags")

    assert client.encode_value(0x1FF, reg) == [0xFF]
    assert client.decode_value([0x1FF], reg) == 0xFF


@pytest.mark.parametrize(
    ("value", "match"),
    [
        (9, "below minimum"),
        (31, "exceeds maximum"),
        (255, "not writable"),
    ],
)
def test_write_register_validates_min_max_and_excluded_enum_values(value: int, match: str) -> None:
    client = IdmModbusClient("127.0.0.1")
    reg = RegisterDef(
        1200,
        DataType.UCHAR,
        "room_mode",
        writable=True,
        min_val=10,
        max_val=30,
        enum_options={10: "eco", 20: "normal", 30: "comfort", 255: "unconfigured"},
        exclude_from_write={255},
        register_type=RegisterType.HOLDING,
    )

    with pytest.raises(ValueError, match=match):
        asyncio.run(client.write_register(reg, value))


def test_write_register_accepts_valid_boundary_values() -> None:
    transport = FakeModbusTransport()
    client = IdmModbusClient("127.0.0.1")
    client._client = transport  # type: ignore[assignment]
    reg = RegisterDef(
        1200,
        DataType.UCHAR,
        "room_setpoint",
        writable=True,
        min_val=10,
        max_val=30,
        register_type=RegisterType.HOLDING,
    )

    for value in (10, 30):
        asyncio.run(client.write_register(reg, value))

    assert transport.write_calls == [(1200, [10]), (1200, [30])]


def test_unsupported_datatype_paths_are_guarded() -> None:
    client = IdmModbusClient("127.0.0.1")
    reg = RegisterDef(1, DataType.UCHAR, "mutated")
    reg.datatype = object()  # type: ignore[assignment]

    with pytest.raises(ValueError, match="Unsupported datatype"):
        client.decode_value([1], reg)
    with pytest.raises(ValueError, match="Unsupported datatype"):
        client.encode_value(1, reg)


@pytest.mark.parametrize(
    ("reg", "write_class"),
    [
        (RegisterDef(1, DataType.UCHAR, "read_only"), WriteClass.FORBIDDEN),
        (RegisterDef(1, DataType.UCHAR, "volatile", writable=True), WriteClass.VOLATILE),
        (
            RegisterDef(1, DataType.UCHAR, "cyclic", writable=True, cyclic_required=True),
            WriteClass.CYCLIC,
        ),
        (
            RegisterDef(1, DataType.UCHAR, "eeprom", writable=True, eeprom_sensitive=True),
            WriteClass.EEPROM,
        ),
        (
            RegisterDef(1, DataType.UCHAR, "write_only", writable=True, write_only=True),
            WriteClass.WRITE_ONLY,
        ),
    ],
)
def test_register_write_class_is_derived_from_write_metadata(
    reg: RegisterDef, write_class: WriteClass
) -> None:
    assert reg.write_class is write_class


@pytest.mark.parametrize(
    "kwargs",
    [
        {"eeprom_sensitive": True},
        {"cyclic_required": True},
        {"write_only": True},
        {"exclude_from_write": {255}},
    ],
)
def test_write_metadata_requires_writable_registers(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="Write metadata requires writable=True"):
        RegisterDef(1, DataType.UCHAR, "invalid", **kwargs)


def test_eeprom_and_cyclic_write_classes_are_mutually_exclusive() -> None:
    with pytest.raises(ValueError, match="cannot be both EEPROM-sensitive and cyclic"):
        RegisterDef(
            1,
            DataType.UCHAR,
            "invalid",
            writable=True,
            eeprom_sensitive=True,
            cyclic_required=True,
        )
