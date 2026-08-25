"""The library-owned Modbus exception hierarchy (#85).

Two properties matter and pull in opposite directions, so both are pinned here:
consumers can migrate to the library's own types today, and consumers that have
not migrated keep working until the pymodbus bases are removed in 2.0.0.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap

import pytest

from idm_heatpump import (
    IdmConnectionError,
    IdmDeviceError,
    IdmModbusError,
    IdmTransportError,
    IllegalAddressError,
)


class TestHierarchy:
    def test_every_error_derives_from_the_library_base(self) -> None:
        for cls in (IdmConnectionError, IdmTransportError, IdmDeviceError, IllegalAddressError):
            assert issubclass(cls, IdmModbusError)

    def test_the_base_is_not_rooted_in_a_third_party_class(self) -> None:
        """``IdmModbusError`` itself must stay free of pymodbus.

        The subclasses carry the pymodbus bases for backwards compatibility; the
        base does not, so ``except IdmModbusError`` will keep working unchanged
        once those bases are dropped.
        """
        assert IdmModbusError.__mro__ == (IdmModbusError, Exception, BaseException, object)

    def test_illegal_address_is_a_device_error(self) -> None:
        assert issubclass(IllegalAddressError, IdmDeviceError)
        assert IllegalAddressError("nope").is_illegal_address is True

    def test_catching_the_base_catches_every_variant(self) -> None:
        for error in (
            IdmConnectionError("link down"),
            IdmTransportError("no answer"),
            IdmDeviceError("refused"),
            IllegalAddressError("no such address"),
        ):
            with pytest.raises(IdmModbusError):
                raise error


class TestExceptionCode:
    """The device's exception code is an attribute, not something to parse out.

    Consumers previously had to regex ``exception_code=(\\d+)`` out of the
    rendered message to name the code in a user-facing error.
    """

    def test_device_error_carries_the_code(self) -> None:
        error = IdmDeviceError("device refused the write", exception_code=4)
        assert error.exception_code == 4
        assert "device refused the write" in str(error)

    def test_code_is_optional(self) -> None:
        assert IdmDeviceError("no code supplied").exception_code is None

    def test_illegal_address_defaults_to_code_2(self) -> None:
        assert IllegalAddressError("no such address").exception_code == 2


class TestPymodbusIsNotInTheContract:
    """2.0.0 removed the shared base with pymodbus outright (#85).

    A consumer injecting its own transport must not need pymodbus installed,
    and must not have to catch a third party's exception types.
    """

    def test_no_error_inherits_from_pymodbus(self) -> None:
        pymodbus_exceptions = pytest.importorskip("pymodbus.exceptions")
        modbus_exception = pymodbus_exceptions.ModbusException
        for cls in (IdmConnectionError, IdmTransportError, IdmDeviceError, IllegalAddressError):
            assert not issubclass(cls, modbus_exception), cls.__name__

    def test_importing_the_package_does_not_import_pymodbus(self) -> None:
        """The base package must load with no Modbus stack present.

        Run in a subprocess with pymodbus masked, because the test extra
        installs it for the built-in transport's own tests.
        """
        script = textwrap.dedent(
            """
            import sys

            class _Blocker:
                def find_module(self, name, path=None):
                    if name == "pymodbus" or name.startswith("pymodbus."):
                        raise ImportError("pymodbus is masked for this check")
                    return None

                def find_spec(self, name, path=None, target=None):
                    self.find_module(name)
                    return None

            sys.meta_path.insert(0, _Blocker())
            import idm_heatpump
            from idm_heatpump import IdmModbusClient, IdmModbusError, IllegalAddressError

            assert "pymodbus" not in sys.modules, sorted(
                m for m in sys.modules if m.startswith("pymodbus")
            )
            print("clean")
            """
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert "clean" in result.stdout

    def test_the_builtin_transport_explains_the_missing_extra(self) -> None:
        """Without the extra, the built-in transport must say how to fix it."""
        script = textwrap.dedent(
            """
            import sys

            class _Blocker:
                def find_spec(self, name, path=None, target=None):
                    if name == "pymodbus" or name.startswith("pymodbus."):
                        raise ImportError("pymodbus is masked for this check")
                    return None

            sys.meta_path.insert(0, _Blocker())
            from idm_heatpump.transport import create_pymodbus_transport

            try:
                create_pymodbus_transport(host="127.0.0.1", port=502, timeout=1.0, retries=0, slave_id=1)
            except ImportError as err:
                assert "idm-heatpump-api[pymodbus]" in str(err), str(err)
                assert "transport=" in str(err), str(err)
                print("explained")
            else:
                raise AssertionError("expected ImportError")
            """
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert "explained" in result.stdout
