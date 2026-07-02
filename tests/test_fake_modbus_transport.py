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
            raise ConnectionException("no fake transports left")
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


def test_timeout_exception_is_deterministic() -> None:
    client = IdmModbusClient("127.0.0.1", max_retries=1)
    client._client = FakeModbusTransport(  # type: ignore[assignment]
        exception_reads={("input", 1000, 1): TimeoutError("fake timeout")}
    )

    with pytest.raises(TimeoutError, match="fake timeout"):
        asyncio.run(client._read_registers(1000, 1))


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
        exception_reads={("input", 1000, 1): ConnectionException("fake abort")}
    )
    working = FakeModbusTransport(input_registers={1000: 7})
    client = ReconnectingClient([working])
    client._client = disconnected  # type: ignore[assignment]

    assert asyncio.run(client._read_registers(1000, 1)) == [7]


def test_batch_groups_split_by_gap_and_size_limits() -> None:
    registers = [
        RegisterDef(1000, DataType.UCHAR, "a"),
        RegisterDef(1011, DataType.UCHAR, "b"),
        RegisterDef(1052, DataType.UCHAR, "c"),
    ]

    groups = IdmModbusClient._group_registers(registers)

    assert [[reg.name for reg in group] for group in groups] == [["a", "b"], ["c"]]


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
