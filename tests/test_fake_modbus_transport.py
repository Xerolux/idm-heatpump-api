"""Client behavior covered with a deterministic fake Modbus transport."""

from __future__ import annotations

import asyncio
import math
import struct

import pytest
from pymodbus.exceptions import ConnectionException, ModbusException

from idm_heatpump.client import DataType, IdmModbusClient, RegisterDef, RegisterType

from .fake_modbus import FakeModbusTransport


class ReconnectingClient(IdmModbusClient):
    def __init__(self, transports: list[FakeModbusTransport]) -> None:
        super().__init__("127.0.0.1", max_retries=2)
        self._transports = transports

    async def _connect_internal(self) -> None:
        if self._client is not None and self._client.connected:
            return
        if not self._transports:
            raise ConnectionException("no fake transports left")  # type: ignore[no-untyped-call]
        self._client = self._transports.pop(0)  # type: ignore[assignment]


def _float_words(client: IdmModbusClient, value: float) -> list[int]:
    return client.encode_value(value, RegisterDef(1, DataType.FLOAT, "float"))


def _raw_float_words(value: float) -> list[int]:
    return list(struct.unpack("<HH", struct.pack("<f", value)))


def test_fake_transport_reads_writes_and_float_byteorder() -> None:
    client = IdmModbusClient("127.0.0.1")
    temp_words = _float_words(client, 21.5)
    transport = FakeModbusTransport(
        input_registers={1000: temp_words[0], 1001: temp_words[1]},
        holding_registers={1200: 0},
    )
    client._client = transport  # type: ignore[assignment]

    temp = RegisterDef(1000, DataType.FLOAT, "outdoor_temp")
    mode = RegisterDef(
        1200,
        DataType.UCHAR,
        "system_mode",
        writable=True,
        register_type=RegisterType.HOLDING,
    )

    assert asyncio.run(client.read_register(temp)) == 21.5
    asyncio.run(client.write_register(mode, 3))

    assert transport.holding_registers[1200] == 3
    assert transport.write_calls == [(1200, [3])]


def test_batch_read_falls_back_to_individual_reads_on_illegal_address() -> None:
    client = IdmModbusClient("127.0.0.1", max_retries=1)
    first_words = _float_words(client, 10.0)
    second_words = _float_words(client, 12.5)
    transport = FakeModbusTransport(
        input_registers={
            1000: first_words[0],
            1001: first_words[1],
            1002: second_words[0],
            1003: second_words[1],
        },
        error_reads={("input", 1000, 4)},
    )
    client._client = transport  # type: ignore[assignment]

    registers = [
        RegisterDef(1000, DataType.FLOAT, "flow_a"),
        RegisterDef(1002, DataType.FLOAT, "flow_b"),
    ]

    assert asyncio.run(client.read_batch(registers)) == {"flow_a": 10.0, "flow_b": 12.5}
    assert transport.read_calls == [
        ("input", 1000, 4),
        ("input", 1000, 2),
        ("input", 1002, 2),
    ]


def test_incomplete_fake_response_raises_modbus_exception() -> None:
    client = IdmModbusClient("127.0.0.1", max_retries=1)
    client._client = FakeModbusTransport(short_reads={("input", 1000, 2): [1]})  # type: ignore[assignment]

    with pytest.raises(ModbusException, match="got 1 registers, expected 2"):
        asyncio.run(client._read_registers(1000, 2))

    error = client.get_last_error_context()
    assert error is not None
    assert error.operation == "read"
    assert error.address == 1000
    assert error.count == 2
    assert error.register_type == "input"
    assert error.error_type == "ModbusException"
    assert "127.0.0.1" not in error.message

    client.clear_last_error_context()

    assert client.get_last_error_context() is None


def test_timeout_exception_is_deterministic() -> None:
    client = IdmModbusClient("127.0.0.1", max_retries=1)
    client._client = FakeModbusTransport(  # type: ignore[assignment]
        exception_reads={("input", 1000, 1): TimeoutError("fake timeout")}
    )

    with pytest.raises(TimeoutError, match="fake timeout"):
        asyncio.run(client._read_registers(1000, 1))


def test_probe_register_can_use_single_fast_attempt() -> None:
    client = IdmModbusClient("127.0.0.1")
    transport = FakeModbusTransport(error_reads={("input", 1000, 1)})
    client._client = transport  # type: ignore[assignment]

    assert asyncio.run(client.probe_register(1000, max_retries=1, timeout=0.05)) is None
    assert transport.read_calls == [("input", 1000, 1)]


def test_permanently_failed_registers_can_be_reset() -> None:
    client = IdmModbusClient("127.0.0.1", max_retries=1)
    client._client = FakeModbusTransport(error_reads={("input", 1000, 1)})  # type: ignore[assignment]
    missing = RegisterDef(1000, DataType.UCHAR, "missing_register")

    for _ in range(3):
        assert asyncio.run(client.read_batch([missing])) == {}

    assert "missing_register" in client._permanently_failed_registers
    assert asyncio.run(client.read_batch([missing])) == {}

    client.reset_failed_registers()

    assert "missing_register" not in client._permanently_failed_registers


def test_connection_exception_triggers_reconnect() -> None:
    disconnected = FakeModbusTransport(
        exception_reads={("input", 1000, 1): ConnectionException("fake abort")}  # type: ignore[no-untyped-call]
    )
    working = FakeModbusTransport(input_registers={1000: 7})
    client = ReconnectingClient([working])
    client._client = disconnected  # type: ignore[assignment]

    assert asyncio.run(client._read_registers(1000, 1)) == [7]


def test_os_error_triggers_reconnect() -> None:
    failing = FakeModbusTransport(exception_reads={("input", 1000, 1): OSError("socket reset")})
    working = FakeModbusTransport(input_registers={1000: 7})
    client = ReconnectingClient([working])
    client._client = failing  # type: ignore[assignment]

    assert asyncio.run(client._read_registers(1000, 1)) == [7]


def test_write_error_context_is_redacted_and_omits_written_values() -> None:
    client = IdmModbusClient("127.0.0.1", max_retries=1)
    client._client = FakeModbusTransport(error_writes={1200})  # type: ignore[assignment]

    with pytest.raises(ModbusException, match="Modbus error writing address 1200"):
        asyncio.run(client._write_registers(1200, [123]))

    error = client.get_last_error_context()

    assert error is not None
    assert error.operation == "write"
    assert error.address == 1200
    assert error.count == 1
    assert error.register_type == "holding"
    assert error.error_type == "ModbusException"
    assert "127.0.0.1" not in error.message
    assert "123" not in error.message


def test_batch_groups_split_by_gap_and_size_limits() -> None:
    registers = [
        RegisterDef(1000, DataType.UCHAR, "a"),
        RegisterDef(1011, DataType.UCHAR, "b"),
        RegisterDef(1052, DataType.UCHAR, "c"),
    ]

    client = IdmModbusClient("127.0.0.1")
    groups = client._group_registers(registers)

    assert [[reg.name for reg in group] for group in groups] == [["a"], ["b"], ["c"]]


def test_batch_groups_do_not_span_unrequested_addresses() -> None:
    client = IdmModbusClient("127.0.0.1")
    registers = [
        RegisterDef(1000, DataType.FLOAT, "temperature"),
        RegisterDef(1003, DataType.UCHAR, "mode"),
    ]

    groups = client._group_registers(registers)

    assert [[reg.name for reg in group] for group in groups] == [["temperature"], ["mode"]]


def test_batch_groups_split_official_overlapping_data_points() -> None:
    """IDM data points that overlap at a boundary require exact separate reads."""
    client = IdmModbusClient("127.0.0.1")
    registers = [
        RegisterDef(1390, DataType.FLOAT, "hc_g_setpoint_flow_temp"),
        RegisterDef(1392, DataType.FLOAT, "humidity_sensor"),
        RegisterDef(1393, DataType.UCHAR, "hc_a_mode"),
        RegisterDef(1394, DataType.UCHAR, "hc_b_mode"),
    ]

    groups = client._group_registers(registers)

    assert [[reg.name for reg in group] for group in groups] == [
        ["hc_g_setpoint_flow_temp", "humidity_sensor"],
        ["hc_a_mode", "hc_b_mode"],
    ]


def test_batch_read_uses_exact_requests_for_overlapping_data_points() -> None:
    client = IdmModbusClient("127.0.0.1", max_retries=1)
    humidity_words = _raw_float_words(54.75)
    transport = FakeModbusTransport(
        input_registers={1392: humidity_words[0], 1393: 2},
        short_reads={("input", 1392, 2): humidity_words},
    )
    client._client = transport  # type: ignore[assignment]
    humidity = RegisterDef(1392, DataType.FLOAT, "humidity_sensor", min_val=0, max_val=100)
    mode = RegisterDef(1393, DataType.UCHAR, "hc_a_mode", enum_options={0: "off", 2: "normal"})

    result = asyncio.run(client.read_batch([humidity, mode]))

    assert result == {"humidity_sensor": 54.75, "hc_a_mode": 2}
    assert transport.read_calls == [("input", 1392, 2), ("input", 1393, 1)]


def test_sentinel_and_non_finite_values_are_decoded_safely() -> None:
    client = IdmModbusClient("127.0.0.1")

    assert client.decode_value([65535], RegisterDef(1, DataType.INT16, "sentinel_minus_one")) == -1
    assert client.decode_value([255], RegisterDef(1, DataType.UCHAR, "sentinel_255")) == 255

    nan_words = _raw_float_words(math.nan)
    inf_words = _raw_float_words(math.inf)

    assert client.decode_value(nan_words, RegisterDef(1, DataType.FLOAT, "nan_value")) is None
    assert client.decode_value(inf_words, RegisterDef(1, DataType.FLOAT, "inf_value")) is None


def test_client_lock_serializes_parallel_requests() -> None:
    client = IdmModbusClient("127.0.0.1")
    transport = FakeModbusTransport(input_registers={1000: 1, 1001: 2}, delay=0.01)
    client._client = transport  # type: ignore[assignment]

    async def read_twice() -> None:
        await asyncio.gather(client._read_registers(1000, 1), client._read_registers(1001, 1))

    asyncio.run(read_twice())

    assert transport.max_active_requests == 1


def test_batch_read_re_reads_suspect_enum_values() -> None:
    """Issue #69: some IDM controllers return corrupt UCHAR data in large batch
    reads. The client should detect out-of-range enum values and re-read them
    individually to recover the real value."""
    client = IdmModbusClient("127.0.0.1", max_retries=1)

    temp_words = _raw_float_words(22.0)
    setpoint_words = _raw_float_words(20.0)

    # Correct individual values stored at each address
    input_registers = {
        2002: temp_words[0],
        2003: temp_words[1],
        2004: setpoint_words[0],
        2005: setpoint_words[1],
        2006: 45,
        2007: 3,
        2008: 1,
    }

    # Corrupt batch response: mode position has 255 instead of 3
    corrupt_batch = temp_words + setpoint_words + [45, 255, 1]
    transport = FakeModbusTransport(
        input_registers=input_registers,
        short_reads={("input", 2002, 7): corrupt_batch},
    )
    client._client = transport  # type: ignore[assignment]

    registers = [
        RegisterDef(2002, DataType.FLOAT, "zm1_room1_temp"),
        RegisterDef(2004, DataType.FLOAT, "zm1_room1_setpoint"),
        RegisterDef(2006, DataType.UCHAR, "zm1_room1_humidity"),
        RegisterDef(
            2007,
            DataType.UCHAR,
            "zm1_room1_mode",
            enum_options={0: "off", 1: "auto", 2: "eco", 3: "normal", 4: "comfort"},
        ),
        RegisterDef(2008, DataType.UCHAR, "zm1_room1_relay"),
    ]

    result = asyncio.run(client.read_batch(registers))

    assert result["zm1_room1_temp"] == 22.0
    assert result["zm1_room1_setpoint"] == 20.0
    assert result["zm1_room1_humidity"] == 45
    assert result["zm1_room1_mode"] == 3
    assert result["zm1_room1_relay"] == 1

    assert ("input", 2002, 7) in transport.read_calls
    assert ("input", 2007, 1) in transport.read_calls


def test_suspect_register_is_quarantined_from_later_batch_reads() -> None:
    client = IdmModbusClient("127.0.0.1", max_retries=1)
    mode = RegisterDef(
        1001,
        DataType.UCHAR,
        "mode",
        enum_options={0: "off", 1: "on"},
    )
    relay = RegisterDef(1002, DataType.UCHAR, "relay")
    transport = FakeModbusTransport(
        input_registers={1001: 1, 1002: 0},
        short_reads={("input", 1001, 2): [255, 0]},
    )
    client._client = transport  # type: ignore[assignment]

    assert asyncio.run(client.read_batch([mode, relay])) == {"mode": 1, "relay": 0}
    assert client.get_batch_unsafe_registers() == ("mode",)

    transport.read_calls.clear()
    assert asyncio.run(client.read_batch([mode, relay])) == {"relay": 0, "mode": 1}
    assert transport.read_calls == [("input", 1002, 1), ("input", 1001, 1)]


def test_invalid_individual_value_is_not_exposed() -> None:
    client = IdmModbusClient("127.0.0.1", max_retries=1)
    humidity = RegisterDef(1392, DataType.FLOAT, "humidity_sensor", min_val=0, max_val=100)
    invalid_words = _raw_float_words(188.0)
    client._client = FakeModbusTransport(  # type: ignore[assignment]
        input_registers={1392: invalid_words[0], 1393: invalid_words[1]}
    )

    assert asyncio.run(client._read_individual_fallback([humidity])) == {}


def test_humidity_float_is_decoded_from_two_words() -> None:
    client = IdmModbusClient("127.0.0.1", max_retries=1)
    humidity = RegisterDef(1392, DataType.FLOAT, "humidity_sensor", min_val=0, max_val=100)
    humidity_words = _raw_float_words(54.75)
    client._client = FakeModbusTransport(  # type: ignore[assignment]
        input_registers={1392: humidity_words[0], 1393: humidity_words[1]}
    )

    assert asyncio.run(client._read_individual_fallback([humidity])) == {"humidity_sensor": 54.75}


def test_is_value_suspect_detects_out_of_range_enum() -> None:
    reg = RegisterDef(
        1,
        DataType.UCHAR,
        "mode",
        enum_options={0: "off", 1: "auto", 2: "eco", 3: "normal", 4: "comfort"},
    )
    assert IdmModbusClient._is_value_suspect(reg, 3) is False
    assert IdmModbusClient._is_value_suspect(reg, 255) is True
    assert IdmModbusClient._is_value_suspect(reg, 5) is True


def test_is_value_suspect_detects_out_of_range_bounds() -> None:
    reg = RegisterDef(1, DataType.UCHAR, "humidity", min_val=0, max_val=100)
    assert IdmModbusClient._is_value_suspect(reg, 50) is False
    assert IdmModbusClient._is_value_suspect(reg, 101) is True

    no_constraints = RegisterDef(1, DataType.UCHAR, "relay")
    assert IdmModbusClient._is_value_suspect(no_constraints, 255) is False
    assert IdmModbusClient._is_value_suspect(no_constraints, 0) is False

    sentinel = RegisterDef(1, DataType.UCHAR, "optional", max_val=100, sentinel_values=(255,))
    assert IdmModbusClient._is_value_suspect(sentinel, 255) is False


def test_is_value_suspect_ignores_none_and_bool() -> None:
    reg = RegisterDef(
        1,
        DataType.UCHAR,
        "mode",
        enum_options={0: "off", 1: "auto"},
    )
    assert IdmModbusClient._is_value_suspect(reg, None) is False
    bool_reg = RegisterDef(1, DataType.BOOL, "flag")
    assert IdmModbusClient._is_value_suspect(bool_reg, True) is False


def test_max_group_size_is_configurable() -> None:
    client = IdmModbusClient("127.0.0.1", max_group_size=2)
    assert client._max_group_size == 2

    registers = [
        RegisterDef(1000, DataType.UCHAR, "a"),
        RegisterDef(1001, DataType.UCHAR, "b"),
        RegisterDef(1002, DataType.UCHAR, "c"),
    ]
    groups = client._group_registers(registers)
    assert len(groups) == 2
    assert [reg.name for reg in groups[0]] == ["a", "b"]
    assert [reg.name for reg in groups[1]] == ["c"]


def test_default_max_group_size_is_40() -> None:
    client = IdmModbusClient("127.0.0.1")
    assert client._max_group_size == 40


def test_max_group_size_rejects_zero() -> None:
    with pytest.raises(ValueError, match="max_group_size"):
        IdmModbusClient("127.0.0.1", max_group_size=0)
