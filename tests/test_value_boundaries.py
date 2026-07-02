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


def test_cyclic_ttl_requires_cyclic_write_class() -> None:
    with pytest.raises(ValueError, match="Cyclic write TTL requires cyclic_required=True"):
        RegisterDef(1, DataType.FLOAT, "invalid", writable=True, cyclic_write_ttl=60)


@pytest.mark.parametrize("ttl", [0, -1, float("inf")])
def test_cyclic_ttl_must_be_positive_and_finite(ttl: float) -> None:
    with pytest.raises(ValueError, match="Cyclic write TTL must be finite and positive"):
        RegisterDef(
            1,
            DataType.FLOAT,
            "invalid",
            writable=True,
            cyclic_required=True,
            cyclic_write_ttl=ttl,
        )


def test_eeprom_write_throttle_blocks_repeated_writes_until_window_expires() -> None:
    current_time = 1000.0
    transport = FakeModbusTransport()
    client = IdmModbusClient("127.0.0.1")
    client._client = transport  # type: ignore[assignment]
    client._time = lambda: current_time
    reg = RegisterDef(1200, DataType.UCHAR, "eeprom", writable=True, eeprom_sensitive=True)

    asyncio.run(client.write_register(reg, 1))

    with pytest.raises(ValueError, match=r"try again in 60\.0s"):
        asyncio.run(client.write_register(reg, 2))

    current_time += 60.0
    asyncio.run(client.write_register(reg, 3))

    assert transport.write_calls == [(1200, [1]), (1200, [3])]


def test_eeprom_write_throttle_can_be_reset_after_process_restart() -> None:
    transport = FakeModbusTransport()
    client = IdmModbusClient("127.0.0.1")
    client._client = transport  # type: ignore[assignment]
    client._time = lambda: 1000.0
    reg = RegisterDef(1200, DataType.UCHAR, "eeprom", writable=True, eeprom_sensitive=True)

    asyncio.run(client.write_register(reg, 1))
    client.reset_write_throttle(reg)
    asyncio.run(client.write_register(reg, 2))

    assert transport.write_calls == [(1200, [1]), (1200, [2])]


def test_failed_eeprom_write_does_not_start_throttle_window() -> None:
    current_time = 1000.0
    transport = FakeModbusTransport(error_writes={1200})
    client = IdmModbusClient("127.0.0.1", max_retries=1)
    client._client = transport  # type: ignore[assignment]
    client._time = lambda: current_time
    reg = RegisterDef(1200, DataType.UCHAR, "eeprom", writable=True, eeprom_sensitive=True)

    with pytest.raises(Exception, match="Modbus error writing address 1200"):
        asyncio.run(client.write_register(reg, 1))

    assert client._last_eeprom_writes == {}


def test_cyclic_write_sets_and_expires_heartbeat_deadline() -> None:
    current_time = 1000.0
    transport = FakeModbusTransport()
    client = IdmModbusClient("127.0.0.1")
    client._client = transport  # type: ignore[assignment]
    client._time = lambda: current_time
    reg = RegisterDef(
        1696,
        DataType.FLOAT,
        "glt_temp_demand_heating",
        writable=True,
        cyclic_required=True,
        cyclic_write_ttl=30,
    )

    asyncio.run(client.write_register(reg, 42.5))

    assert client.get_active_cyclic_writes() == {"glt_temp_demand_heating": 1030.0}
    assert client.get_expired_cyclic_writes() == set()

    current_time = 1030.0

    assert client.get_active_cyclic_writes() == {}
    assert client.get_expired_cyclic_writes() == {"glt_temp_demand_heating"}


def test_cyclic_write_heartbeat_refreshes_deadline_and_can_be_reset() -> None:
    current_time = 1000.0
    transport = FakeModbusTransport()
    client = IdmModbusClient("127.0.0.1")
    client._client = transport  # type: ignore[assignment]
    client._time = lambda: current_time
    reg = RegisterDef(
        1696,
        DataType.FLOAT,
        "glt_temp_demand_heating",
        writable=True,
        cyclic_required=True,
        cyclic_write_ttl=30,
    )

    asyncio.run(client.write_register(reg, 40.0))
    current_time = 1010.0
    asyncio.run(client.write_register(reg, 41.0))

    assert client.get_active_cyclic_writes() == {"glt_temp_demand_heating": 1040.0}

    client.reset_cyclic_write_state(reg)

    assert client.get_active_cyclic_writes() == {}
    assert client.get_expired_cyclic_writes() == set()
