"""Public raw Modbus transport contract plus the default Pymodbus adapter.

The :class:`IdmModbusTransport` protocol is the stable 1.0 boundary between the
device-agnostic IDM library logic (register maps, codecs, batching, retry,
quarantine, model detection, write safety) and the concrete byte transport
used to talk to a heat pump.

Two implementations ship in-tree:

* :class:`_PymodbusTransport` -- the default, backward-compatible path that
  keeps direct Pymodbus TCP behaviour identical to pre-1.0 releases. Selected
  automatically when ``IdmModbusClient(..., transport=None)`` (the default).
* Any caller-supplied object satisfying :class:`IdmModbusTransport`, injected
  via ``IdmModbusClient(..., transport=custom)``. This is how the Home
  Assistant integration routes raw I/O through ``modbus-connection``/``tmodbus``
  without subclassing the client and overriding private hooks.

The transport owns **only** connection lifecycle and raw register words. It
must surface device-side Modbus exception code 2 (Illegal Data Address) by
raising :class:`IllegalAddressError` so the library retry loop can short-
circuit it as a permanent condition for the affected address. All other
device-side failures should be raised as :class:`ModbusException`,
:class:`ConnectionException`, :class:`ModbusIOException`, :class:`OSError` or
:class:`TimeoutError`; transient codes 5/6/10/11 belong to the retry-in-place
path and must never be classified as an unsupported individual register.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol, runtime_checkable

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ConnectionException, ModbusException

__all__ = [
    "IdmModbusTransport",
    "check_transport_response",
]

_LOGGER = logging.getLogger(__name__)

# Pymodbus reconnect tuning, kept identical to the pre-1.0 client behaviour so
# the default transport is observably unchanged for existing consumers.
_PMODBUS_RECONNECT_DELAY = 0.5
_PMODBUS_RECONNECT_DELAY_MAX = 10.0


@runtime_checkable
class IdmModbusTransport(Protocol):
    """Neutral raw Modbus TCP transport contract.

    Implementations are responsible for a single logical socket connection to
    one Modbus TCP endpoint (host:port, unit/slave id). The library serialises
    access via its own ``asyncio.Lock`` and drives the retry loop, batching,
    model detection and write safety above this layer, so transports must not
    stack their own retries or re-acquire the library lock.

    Required coroutine semantics:

    * :meth:`connect` opens the socket; it must raise :class:`ConnectionException`
      on failure rather than returning a truthy/falsy value.
    * :meth:`close` releases the socket and any background tasks; idempotent.
    * :attr:`connected` reflects the live socket state.

    The three register methods return raw 16-bit register words and must map
    device-side exception responses through :func:`check_transport_response`
    (or raise the equivalent exceptions directly). Incomplete responses
    (fewer registers than requested) must raise :class:`ModbusException`.
    """

    __slots__ = ()

    @property
    def connected(self) -> bool:
        """Whether the transport currently holds an open socket."""
        ...

    async def connect(self) -> None:
        """Open the connection; raise :class:`ConnectionException` on failure."""
        ...

    async def close(self) -> None:
        """Close the connection and release resources. Idempotent."""
        ...

    async def read_input_registers(self, *, address: int, count: int) -> list[int]:
        """Read ``count`` input registers (FC04) starting at ``address``."""
        ...

    async def read_holding_registers(self, *, address: int, count: int) -> list[int]:
        """Read ``count`` holding registers (FC03) starting at ``address``."""
        ...

    async def write_registers(self, *, address: int, values: list[int]) -> None:
        """Write the 16-bit ``values`` (FC16) starting at ``address``."""
        ...


def check_transport_response(result: Any, address: int, *, operation: str) -> list[int]:
    """Validate a pymodbus-style response and return its register words.

    Centralises the device-response mapping so the default Pymodbus adapter
    and any pymodbus-shaped injected transport classify responses identically:

    * ``isError()`` with ``exception_code == 2`` -> :class:`IllegalAddressError`
      (permanent for the address; the library retry loop short-circuits it).
    * Any other ``isError()`` response -> :class:`ModbusException` (transient,
      retried in place; never treated as an unsupported register).
    * A response with fewer registers than requested -> :class:`ModbusException`.

    ``operation`` is one of ``"read"``/``"write"`` and only flavours the error
    message. Transports that already raise the correct exceptions directly do
    not need to call this helper.
    """
    if result.isError():
        if getattr(result, "exception_code", None) == 2:
            # Lazy import: ``IllegalAddressError`` is defined in ``client`` to
            # preserve the pre-1.0 public surface; importing it eagerly here
            # would create a load-time cycle with ``client``.
            from .client import IllegalAddressError

            raise IllegalAddressError(  # type: ignore[no-untyped-call]
                f"Illegal Data Address {operation} address {address}: {result}"
            )
        raise ModbusException(  # type: ignore[no-untyped-call]
            f"Modbus error {operation} address {address}: {result}"
        )
    registers_obj = getattr(result, "registers", None)
    registers = list(registers_obj) if registers_obj is not None else []
    return registers


class _PymodbusTransport:
    """Default :class:`IdmModbusTransport` backed by Pymodbus TCP.

    Wraps :class:`pymodbus.client.AsyncModbusTcpClient` so the library can
    treat the default Pymodbus path and an injected transport symmetrically.
    The adapter owns no retry, lock, batching or write-safety logic; it only
    manages socket lifecycle and raw register words, matching the public
    transport contract.

    The pymodbus unit-id parameter name differs across pymodbus releases
    (``slave`` vs ``device_id``); ``slave_param`` is resolved once by the
    library and passed in so this adapter stays pymodbus-version-agnostic.
    """

    __slots__ = ("_host", "_port", "_timeout", "_retries", "_slave_id", "_slave_param", "_client")

    def __init__(
        self,
        *,
        host: str,
        port: int,
        timeout: float,
        retries: int,
        slave_id: int,
        slave_param: str,
    ) -> None:
        self._host = host
        self._port = port
        self._timeout = timeout
        self._retries = retries
        self._slave_id = slave_id
        self._slave_param = slave_param
        self._client: AsyncModbusTcpClient | None = None

    @property
    def connected(self) -> bool:
        return self._client is not None and bool(self._client.connected)

    async def connect(self) -> None:
        """Open the Pymodbus TCP connection or raise :class:`ConnectionException`."""
        if self._client is not None and self._client.connected:
            return
        self._client = AsyncModbusTcpClient(
            host=self._host,
            port=self._port,
            timeout=self._timeout,
            retries=self._retries,
            reconnect_delay=_PMODBUS_RECONNECT_DELAY,
            reconnect_delay_max=_PMODBUS_RECONNECT_DELAY_MAX,
        )
        if not await self._client.connect():
            self._client = None
            raise ConnectionException(  # type: ignore[no-untyped-call]
                f"Failed to connect to {self._host}:{self._port}"
            )
        _LOGGER.debug("Connected to %s:%s", self._host, self._port)

    async def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
            _LOGGER.debug("Disconnected from %s:%s", self._host, self._port)

    async def read_input_registers(self, *, address: int, count: int) -> list[int]:
        return await self._read(address, count, holding=False)

    async def read_holding_registers(self, *, address: int, count: int) -> list[int]:
        return await self._read(address, count, holding=True)

    async def write_registers(self, *, address: int, values: list[int]) -> None:
        client = self._require_client()
        kwargs: Any = {self._slave_param: self._slave_id}
        result = await client.write_registers(
            address=address,
            values=[int(v) for v in values],
            **kwargs,
        )
        check_transport_response(result, address, operation="writing")

    def _require_client(self) -> AsyncModbusTcpClient:
        if self._client is None or not self._client.connected:
            raise ConnectionException(  # type: ignore[no-untyped-call]
                f"Not connected to {self._host}:{self._port}"
            )
        return self._client

    async def _read(self, address: int, count: int, *, holding: bool) -> list[int]:
        client = self._require_client()
        kwargs: Any = {self._slave_param: self._slave_id}
        if holding:
            result = await client.read_holding_registers(address=address, count=count, **kwargs)
        else:
            result = await client.read_input_registers(address=address, count=count, **kwargs)
        registers = check_transport_response(result, address, operation="reading")
        if len(registers) != count:
            raise ModbusException(  # type: ignore[no-untyped-call]
                f"Incomplete Modbus response at address {address}: "
                f"got {len(registers)} registers, expected {count}"
            )
        return registers
