"""Library-owned Modbus exception hierarchy.

Until 2.0.0 every error this library raised was a ``pymodbus`` exception, and
:class:`IllegalAddressError` — a *public* export — inherited from
``pymodbus.exceptions.ModbusException``. That made pymodbus part of the public
contract: a consumer injecting its own transport (the documented way to use the
library since 1.0) still had to install pymodbus and catch pymodbus types.

These classes take that role over outright. There is no shared base with
pymodbus any more; ``except ModbusException`` no longer catches anything this
library raises. See issue #85 for the migration.

Catch :class:`IdmModbusError` to handle any failure from the client without
depending on which Modbus stack performed the I/O.
"""

from __future__ import annotations

__all__ = [
    "IdmConnectionError",
    "IdmDeviceError",
    "IdmModbusError",
    "IdmTransportError",
    "IllegalAddressError",
]


class IdmModbusError(Exception):
    """Base class for every Modbus-level error raised by this library."""


class IdmConnectionError(IdmModbusError):
    """The transport could not be established, or the link was lost.

    Retrying is worthwhile, but only after reconnecting.
    """


class IdmTransportError(IdmModbusError):
    """A request produced no usable answer.

    Covers timeouts, short or shifted responses, and replies that answer a
    different exchange. The session may be stale, so a reconnect is the usual
    response.
    """


class IdmDeviceError(IdmModbusError):
    """The device answered, and refused the request.

    ``exception_code`` carries the numeric Modbus exception code when the
    device supplied one, so consumers can name it without parsing it back out
    of the message text.
    """

    #: Numeric Modbus exception code, or None when the device supplied none.
    exception_code: int | None = None

    def __init__(self, message: str, *, exception_code: int | None = None) -> None:
        """Store the message and the device's exception code."""
        super().__init__(message)
        self.exception_code = exception_code


class IllegalAddressError(IdmDeviceError):
    """Modbus ``Illegal Data Address`` (exception code 2).

    Raised when the device reports that a register address does not exist.
    Unlike a generic device error, this is a permanent condition for the
    address in question: retrying is pointless and only produces noisy log
    lines. Callers that detect this marker (via ``isinstance`` or the
    ``is_illegal_address`` attribute) can short-circuit retries and suppress
    the repeated "failed after N attempts" warnings that otherwise flood the
    log when optional registers are probed on devices that do not implement
    them (e.g. Navigator-10-only blocks read against a Navigator 2.0).
    """

    #: Sentinel attribute checked by the retry loop to bail out silently.
    is_illegal_address: bool = True

    def __init__(self, message: str, *, exception_code: int | None = 2) -> None:
        """Default the exception code to 2, the code this class represents."""
        super().__init__(message, exception_code=exception_code)
