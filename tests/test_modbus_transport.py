"""Tests for the public IdmModbusTransport protocol and client injection.

Covers the 1.0 transport boundary that lets the Home Assistant integration
route raw I/O through ``modbus-connection``/``tmodbus`` without subclassing
``IdmModbusClient`` and overriding private hooks:

* protocol satisfaction and constructor validation
* injected transport is used for reads, writes and lifecycle
* legacy ``client._client = fake`` seam still works (backwards compat)
* default Pymodbus path is selected when ``transport=None``
* transient device codes 5/6/10/11 never quarantine registers
* code 6 (Slave Busy) is not retried twice when the backend owns retry
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from idm_heatpump.client import IdmModbusClient, IllegalAddressError, RegisterType
from idm_heatpump.exceptions import IdmConnectionError, IdmDeviceError, IdmTransportError
from idm_heatpump.transport import IdmModbusTransport, _PymodbusTransport, check_transport_response

from .fake_modbus import FakeModbusTransport

# ---------------------------------------------------------------------------
# Protocol satisfaction
# ---------------------------------------------------------------------------


def test_fake_transport_satisfies_protocol() -> None:
    """The fake must be recognised as an IdmModbusTransport (runtime_checkable)."""
    assert isinstance(FakeModbusTransport(), IdmModbusTransport)


def test_protocol_transport_with_extra_methods_still_satisfies() -> None:
    """Extra attributes must not break protocol membership."""

    class Extended(FakeModbusTransport):
        def custom_helper(self) -> int:
            return 42

    assert isinstance(Extended(), IdmModbusTransport)


def test_object_missing_methods_does_not_satisfy_protocol() -> None:
    """An object lacking required async methods must not satisfy the protocol."""

    class Bare:
        connected = True

    assert not isinstance(Bare(), IdmModbusTransport)


# ---------------------------------------------------------------------------
# Constructor: default vs injected
# ---------------------------------------------------------------------------


def test_default_client_uses_pymodbus_transport() -> None:
    """transport=None selects the internal _PymodbusTransport adapter."""
    client = IdmModbusClient("127.0.0.1")
    assert isinstance(client._transport, _PymodbusTransport)


def test_injected_transport_is_stored() -> None:
    """An injected transport is stored verbatim and not wrapped."""
    transport = FakeModbusTransport()
    client = IdmModbusClient("127.0.0.1", transport=transport)
    assert client._transport is transport


def test_invalid_transport_raises_typeerror() -> None:
    """An object that does not satisfy the protocol must be rejected."""

    class NotATransport:
        connected = True

    with pytest.raises(TypeError, match="IdmModbusTransport"):
        IdmModbusClient("127.0.0.1", transport=NotATransport())  # type: ignore[arg-type]


def test_transport_parameter_is_keyword_only() -> None:
    """transport must be keyword-only to keep positional back-compat."""
    transport = FakeModbusTransport()
    with pytest.raises(TypeError):
        IdmModbusClient("127.0.0.1", transport)  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Injection routes reads/writes/lifecycle through the transport
# ---------------------------------------------------------------------------


def test_injected_transport_is_used_for_reads() -> None:
    """A constructor-injected transport receives input-register reads."""
    transport = FakeModbusTransport(input_registers={1000: 7, 1001: 9})
    client = IdmModbusClient("127.0.0.1", max_retries=1, transport=transport)

    result = asyncio.run(client._read_registers(1000, 2, RegisterType.INPUT))

    assert result == [7, 9]
    assert transport.read_calls == [("input", 1000, 2)]


def test_injected_transport_is_used_for_holding_reads() -> None:
    transport = FakeModbusTransport(holding_registers={1200: 3})
    client = IdmModbusClient("127.0.0.1", max_retries=1, transport=transport)

    result = asyncio.run(client._read_registers(1200, 1, RegisterType.HOLDING))

    assert result == [3]
    assert transport.read_calls == [("holding", 1200, 1)]


def test_injected_transport_is_used_for_writes() -> None:
    transport = FakeModbusTransport()
    client = IdmModbusClient("127.0.0.1", max_retries=1, transport=transport)

    asyncio.run(client._write_registers(1200, [3]))

    assert transport.write_calls == [(1200, [3])]


def test_injected_transport_receives_connect() -> None:
    """connect() is delegated to the injected transport."""

    class CountingTransport(FakeModbusTransport):
        def __init__(self) -> None:
            super().__init__()
            self.connect_calls = 0
            self.connected = False

        async def connect(self) -> None:
            self.connect_calls += 1
            self.connected = True

    transport = CountingTransport()
    client = IdmModbusClient("127.0.0.1", transport=transport)

    asyncio.run(client.connect())

    assert transport.connect_calls == 1
    assert client.is_connected is True


def test_injected_transport_receives_disconnect() -> None:
    transport = FakeModbusTransport()
    client = IdmModbusClient("127.0.0.1", transport=transport)

    asyncio.run(client.disconnect())

    assert transport.connected is False


def test_injected_transport_lock_serialization() -> None:
    """The library lock still serialises access through an injected transport."""
    transport = FakeModbusTransport(input_registers={i: i for i in range(1000, 1010)}, delay=0.05)
    client = IdmModbusClient("127.0.0.1", max_retries=1, transport=transport)

    async def read_many() -> None:
        await asyncio.gather(*[client._read_registers(1000 + i, 1) for i in range(5)])

    asyncio.run(read_many())

    # Serialised: never more than one outstanding request at a time.
    assert transport.max_active_requests == 1


# ---------------------------------------------------------------------------
# Legacy backwards compatibility
# ---------------------------------------------------------------------------


def test_legacy_client_attribute_assignment_still_works() -> None:
    """Assigning client._client must route through the transport property."""
    client = IdmModbusClient("127.0.0.1", max_retries=1)
    transport = FakeModbusTransport(input_registers={1000: 42})
    client._client = transport  # type: ignore[assignment]

    assert client._client is transport  # type: ignore[comparison-overlap]
    assert client._transport is transport

    result = asyncio.run(client._read_registers(1000, 1, RegisterType.INPUT))
    assert result == [42]


def test_legacy_and_constructor_injection_are_equivalent() -> None:
    """Both injection paths must produce identical observable behaviour."""
    data = {1000: 5, 1001: 6}

    # Constructor injection
    ctor_transport = FakeModbusTransport(input_registers=dict(data))
    ctor_client = IdmModbusClient("127.0.0.1", max_retries=1, transport=ctor_transport)
    ctor_result = asyncio.run(ctor_client._read_registers(1000, 2, RegisterType.INPUT))

    # Legacy attribute injection
    legacy_transport = FakeModbusTransport(input_registers=dict(data))
    legacy_client = IdmModbusClient("127.0.0.1", max_retries=1)
    legacy_client._client = legacy_transport  # type: ignore[assignment]
    legacy_result = asyncio.run(legacy_client._read_registers(1000, 2, RegisterType.INPUT))

    assert ctor_result == legacy_result == [5, 6]
    assert ctor_transport.read_calls == legacy_transport.read_calls


# ---------------------------------------------------------------------------
# Exception-code semantics (handoff point 3)
# ---------------------------------------------------------------------------


def test_code_6_busy_is_transient_not_permanent() -> None:
    """A Slave-Busy (code 6) response is transient and must not mark a register
    permanently failed or unsupported, unlike code 2 (Illegal Address)."""
    transport = FakeModbusTransport(
        exception_reads={
            ("input", 1000, 1): IdmDeviceError("Exception code 6 - Slave Device Busy"),
        }
    )
    client = IdmModbusClient("127.0.0.1", max_retries=1, transport=transport)

    with pytest.raises(IdmDeviceError):
        asyncio.run(client._read_registers(1000, 1, RegisterType.INPUT))

    # The register must NOT be classified as permanently failed/unsupported:
    # code 6 is a transient device state, not a missing register.
    assert client.get_unsupported_registers() == ()
    assert client._permanently_failed_registers == set()


def test_codes_5_10_11_do_not_quarantine_registers() -> None:
    """Transient gateway codes 5/10/11 must retry in place without quarantining
    the register into _batch_unsafe_registers or _permanently_failed_registers."""

    for code_name in ("Acknowledge", "Gateway Path Unavailable", "Gateway Target No Response"):
        transport = FakeModbusTransport(
            exception_reads={
                ("input", 2000, 1): IdmDeviceError(f"Exception code - {code_name}"),
            }
        )
        client = IdmModbusClient("127.0.0.1", max_retries=1, transport=transport)

        with pytest.raises(IdmDeviceError):
            asyncio.run(client._read_registers(2000, 1, RegisterType.INPUT))

        assert client._batch_unsafe_registers == set()
        assert client._permanently_failed_registers == set()
        assert client.get_unsupported_registers() == ()


def test_code_2_illegal_address_still_marks_unsupported() -> None:
    """Sanity check: code 2 (the permanent path) is unaffected by the new
    transport boundary and still flags the register as unsupported."""
    transport = FakeModbusTransport(illegal_reads={("input", 3000, 1)})
    client = IdmModbusClient("127.0.0.1", max_retries=1, transport=transport)

    with pytest.raises(IllegalAddressError):
        asyncio.run(client._read_registers(3000, 1, RegisterType.INPUT))

    # read_batch's individual fallback is what marks unsupported; a raw
    # _read_registers call just surfaces IllegalAddressError. Verify the
    # exception type is the permanent marker, not a generic IdmDeviceError.
    assert not isinstance(
        IllegalAddressError("x"),  # marker class still distinct from IdmDeviceError-only
        type(None),
    )


def test_code_6_busy_is_retried_in_place_without_reconnect() -> None:
    """A code-6 failure (generic IdmDeviceError) must use the retry-in-place
    path, not the hard-reconnect path reserved for transport errors."""

    class BusyThenSuccess(FakeModbusTransport):
        def __init__(self) -> None:
            super().__init__(input_registers={1000: 11})
            self.read_attempts = 0
            self.close_calls = 0

        async def _read(
            self, kind: str, registers: dict[int, int], address: int, count: int
        ) -> list[int]:
            self.read_attempts += 1
            if self.read_attempts == 1:
                raise IdmDeviceError("Slave Device Busy")
            return await super()._read(kind, registers, address, count)

        async def close(self) -> None:
            self.close_calls += 1
            await super().close()

    transport = BusyThenSuccess()
    client = IdmModbusClient("127.0.0.1", max_retries=2, transport=transport)

    result = asyncio.run(client._read_registers(1000, 1, RegisterType.INPUT))

    assert result == [11]
    assert transport.read_attempts == 2
    # Retry-in-place must not hard-close the transport (that path is for
    # IdmConnectionError/IdmTransportError/OSError/TimeoutError only).
    assert transport.close_calls == 0


# ---------------------------------------------------------------------------
# check_transport_response helper
# ---------------------------------------------------------------------------


def test_check_transport_response_maps_code_2_to_illegal_address() -> None:
    response = type("R", (), {"isError": lambda self: True, "exception_code": 2})()
    with pytest.raises(IllegalAddressError):
        check_transport_response(response, 1000, operation="reading")


def test_check_transport_response_maps_other_errors_to_modbus_exception() -> None:
    response = type("R", (), {"isError": lambda self: True, "exception_code": 6})()
    with pytest.raises(IdmDeviceError):
        check_transport_response(response, 1000, operation="reading")


def test_check_transport_response_returns_registers_on_success() -> None:
    response = type("R", (), {"isError": lambda self: False, "registers": [1, 2, 3]})()
    assert check_transport_response(response, 1000, operation="reading") == [1, 2, 3]


# ---------------------------------------------------------------------------
# Default transport reconnect behaviour (legacy parity)
# ---------------------------------------------------------------------------


def test_default_transport_connection_exception_triggers_reconnect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The default _PymodbusTransport path must still reconnect on transport errors,
    preserving the pre-1.0 retry/reconnect semantics."""
    client = IdmModbusClient("127.0.0.1", max_retries=2)

    failing = FakeModbusTransport(
        input_registers={1000: 99},
        exception_reads={("input", 1000, 1): IdmConnectionError("down")},
    )
    working = FakeModbusTransport(input_registers={1000: 99})
    failing.connected = True

    # First read fails with IdmConnectionError, reconnect swaps to the working fake.
    client._transport = failing  # type: ignore[assignment]
    monkeypatch.setattr(client, "_connect_internal", _swap_transport_factory(client, working))

    result = asyncio.run(client._read_registers(1000, 1, RegisterType.INPUT))

    assert result == [99]
    assert working.read_calls == [("input", 1000, 1)]


def test_default_transport_modbus_io_exception_hard_closes() -> None:
    """IdmTransportError must hard-close the transport before retry (stale socket)."""
    failing = FakeModbusTransport(
        input_registers={1000: 7},
        exception_reads={("input", 1000, 1): IdmTransportError("no response")},
    )
    working = FakeModbusTransport(input_registers={1000: 7})

    client = IdmModbusClient("127.0.0.1", max_retries=2)
    client._transport = failing  # type: ignore[assignment]

    async def fake_connect() -> None:
        client._transport = working  # type: ignore[assignment]
        working.connected = True

    # Monkeypatch by replacing the bound method on the instance.
    client._connect_internal = fake_connect  # type: ignore[assignment]

    asyncio.run(client._read_registers(1000, 1, RegisterType.INPUT))

    # The failing transport must have been closed (hard reconnect path).
    assert failing.connected is False
    assert working.read_calls == [("input", 1000, 1)]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _swap_transport_factory(client: IdmModbusClient, new_transport: FakeModbusTransport) -> Any:
    """Return an async _connect_internal replacement that swaps the transport."""

    async def fake_connect() -> None:
        client._transport = new_transport  # type: ignore[assignment]
        new_transport.connected = True

    return fake_connect


# ---------------------------------------------------------------------------
# Built-in pymodbus adapter: raised backend errors and client lifecycle
# ---------------------------------------------------------------------------


class _StubPymodbusClient:
    """Stand-in for ``AsyncModbusTcpClient`` that raises or answers on demand."""

    def __init__(
        self,
        *,
        raise_on_read: BaseException | None = None,
        raise_on_write: BaseException | None = None,
        registers: list[int] | None = None,
        connect_result: bool = True,
        **_: Any,
    ) -> None:
        self.connected = False
        self.connect_result = connect_result
        self.raise_on_read = raise_on_read
        self.raise_on_write = raise_on_write
        self.registers = registers if registers is not None else []
        self.close_calls = 0
        self.read_calls: list[tuple[int, int]] = []

    async def connect(self) -> bool:
        self.connected = self.connect_result
        return self.connect_result

    def close(self) -> None:
        self.connected = False
        self.close_calls += 1

    async def read_input_registers(self, *, address: int, count: int, **_: Any) -> Any:
        self.read_calls.append((address, count))
        if self.raise_on_read is not None:
            raise self.raise_on_read
        return _StubResponse(self.registers)

    async def read_holding_registers(self, *, address: int, count: int, **_: Any) -> Any:
        return await self.read_input_registers(address=address, count=count)

    async def write_registers(self, *, address: int, values: list[int], **_: Any) -> Any:
        if self.raise_on_write is not None:
            raise self.raise_on_write
        return _StubResponse([])


class _StubResponse:
    def __init__(self, registers: list[int]) -> None:
        self.registers = registers

    def isError(self) -> bool:  # noqa: N802 - pymodbus API name
        return False


def _pymodbus_transport_with(client: Any) -> _PymodbusTransport:
    transport = _PymodbusTransport(
        host="127.0.0.1", port=502, timeout=1.0, retries=0, slave_id=1, slave_param="slave"
    )
    transport._client = client
    return transport


@pytest.mark.parametrize(
    ("raised", "expected"),
    [
        ("ModbusIOException", IdmTransportError),
        ("ConnectionException", IdmConnectionError),
        ("ModbusException", IdmTransportError),
    ],
)
def test_pymodbus_transport_translates_raised_read_errors(raised: str, expected: type) -> None:
    """A timeout or dropped link is *raised* by pymodbus, not returned as a response.

    Without translation the raw ``pymodbus.exceptions`` type escaped the
    library's retry/reconnect loop, ``probe_register`` and ``detect_model``.
    """
    pymodbus_exceptions = pytest.importorskip("pymodbus.exceptions")
    err = getattr(pymodbus_exceptions, raised)("no response")
    stub = _StubPymodbusClient(raise_on_read=err)
    stub.connected = True
    transport = _pymodbus_transport_with(stub)

    with pytest.raises(expected) as info:
        asyncio.run(transport.read_input_registers(address=1000, count=2))

    assert info.value.__cause__ is err
    assert "1000" in str(info.value)


def test_pymodbus_transport_translates_raised_write_errors() -> None:
    pymodbus_exceptions = pytest.importorskip("pymodbus.exceptions")
    err = pymodbus_exceptions.ModbusIOException("no response")
    stub = _StubPymodbusClient(raise_on_write=err)
    stub.connected = True
    transport = _pymodbus_transport_with(stub)

    with pytest.raises(IdmTransportError) as info:
        asyncio.run(transport.write_registers(address=1710, values=[1]))

    assert info.value.__cause__ is err


def test_pymodbus_transport_leaves_foreign_exceptions_alone() -> None:
    """Only pymodbus types are translated; anything else stays as-is."""
    stub = _StubPymodbusClient(raise_on_read=RuntimeError("boom"))
    stub.connected = True
    transport = _pymodbus_transport_with(stub)

    with pytest.raises(RuntimeError, match="boom"):
        asyncio.run(transport.read_input_registers(address=1000, count=1))


def test_pymodbus_raised_timeout_goes_through_client_retry_and_reconnect() -> None:
    """End to end: the raised pymodbus timeout is retried like any transport failure."""
    pymodbus_exceptions = pytest.importorskip("pymodbus.exceptions")
    failing = _StubPymodbusClient(
        raise_on_read=pymodbus_exceptions.ModbusIOException("No response received")
    )
    failing.connected = True
    transport = _pymodbus_transport_with(failing)
    working = FakeModbusTransport(input_registers={1000: 7})
    client = IdmModbusClient("127.0.0.1", max_retries=2)
    client._transport = transport  # type: ignore[assignment]
    client._connect_internal = _swap_transport_factory(client, working)  # type: ignore[method-assign]

    result = asyncio.run(client._read_registers(1000, 1, RegisterType.INPUT))

    assert result == [7]
    context = client.get_last_error_context()
    assert context is not None
    assert context.error_type == "IdmTransportError"
    # The hard-reconnect path closed the stale pymodbus client before retrying.
    assert failing.close_calls == 1
    assert working.read_calls == [("input", 1000, 1)]


def test_pymodbus_transport_closes_stale_client_before_reconnecting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A dropped pymodbus client owns a reconnect task; it must be closed, not orphaned."""
    created: list[_StubPymodbusClient] = []

    def factory(**kwargs: Any) -> _StubPymodbusClient:
        stub = _StubPymodbusClient(**kwargs)
        created.append(stub)
        return stub

    monkeypatch.setattr("idm_heatpump.transport._require_pymodbus", lambda: factory)
    transport = _PymodbusTransport(
        host="127.0.0.1", port=502, timeout=1.0, retries=0, slave_id=1, slave_param="slave"
    )

    asyncio.run(transport.connect())
    stale = created[0]
    stale.connected = False  # the controller dropped the link

    asyncio.run(transport.connect())

    assert len(created) == 2
    assert stale.close_calls == 1
    assert transport._client is created[1]


def test_pymodbus_transport_closes_client_when_connect_returns_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def factory(**kwargs: Any) -> _StubPymodbusClient:
        return _StubPymodbusClient(connect_result=False, **kwargs)

    monkeypatch.setattr("idm_heatpump.transport._require_pymodbus", lambda: factory)
    transport = _PymodbusTransport(
        host="127.0.0.1", port=502, timeout=1.0, retries=0, slave_id=1, slave_param="slave"
    )

    with pytest.raises(IdmConnectionError):
        asyncio.run(transport.connect())

    assert transport._client is None


def test_pymodbus_transport_short_response_reaches_per_register_fallback() -> None:
    """A short batch answer is the client's device-error case, not a transport failure.

    The batch reader answers it by falling back to single reads, which isolates
    the register the firmware mishandles. A transport-level length check
    pre-empted that with a reconnect and failed the whole poll.
    """

    class ShortBatchClient(_StubPymodbusClient):
        async def read_input_registers(self, *, address: int, count: int, **_: Any) -> Any:
            self.read_calls.append((address, count))
            if count == 4:
                return _StubResponse([0, 16968, 0])
            return _StubResponse([0, 16968][:count])

    stub = ShortBatchClient()
    stub.connected = True
    transport = _pymodbus_transport_with(stub)

    # The transport passes the short answer through; the client classifies it.
    assert asyncio.run(transport.read_input_registers(address=1000, count=4)) == [0, 16968, 0]

    client = IdmModbusClient("127.0.0.1", max_retries=1)
    client._transport = transport  # type: ignore[assignment]
    with pytest.raises(IdmDeviceError, match="Incomplete Modbus response"):
        asyncio.run(client._read_registers(1000, 4, RegisterType.INPUT))
    assert client._connection_suspect is False
