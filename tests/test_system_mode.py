"""Keep controller system modes consistent across reads and guarded writes."""

from __future__ import annotations

import pytest

from idm_heatpump.client import DataType, IdmModbusClient, IdmModelInfo, RegisterType
from idm_heatpump.const import (
    MODEL_NAVIGATOR_10,
    MODEL_NAVIGATOR_17,
    MODEL_NAVIGATOR_20,
    MODEL_NAVIGATOR_PRO,
    SYSTEM_MODE_OPTIONS,
    SystemMode,
)
from idm_heatpump.registers import CORE_REGISTERS, build_register_map

from .fake_modbus import FakeModbusTransport


def _model_info(model: str) -> IdmModelInfo:
    return IdmModelInfo(model, ["A"], 0, False, False, False, False)


@pytest.mark.asyncio
@pytest.mark.parametrize("model", [MODEL_NAVIGATOR_20, MODEL_NAVIGATOR_10, MODEL_NAVIGATOR_PRO])
@pytest.mark.parametrize("mode", range(6))
async def test_system_modes_survive_validated_poll_and_write(model: str, mode: int) -> None:
    """Issue #596: holiday must survive the batch/individual enum validator."""
    reg = build_register_map(model_info=_model_info(model))["system_mode"]
    transport = FakeModbusTransport(input_registers={1005: mode})
    client = IdmModbusClient("127.0.0.1", transport=transport)

    assert (reg.address, reg.datatype, reg.size, reg.register_type) == (
        1005,
        DataType.UCHAR,
        1,
        RegisterType.INPUT,
    )
    assert reg.writable and reg.eeprom_sensitive
    assert await client.read_batch([reg]) == {"system_mode": mode}
    assert transport.read_calls == [("input", 1005, 1)]
    assert client.get_register_outcomes()["system_mode"]["status"] == "ok"
    assert client.get_batch_unsafe_registers() == ()

    await client.write_register(reg, mode)
    assert transport.write_calls == [(1005, [mode])]
    with pytest.raises(ValueError, match="EEPROM-sensitive"):
        await client.write_register(reg, (mode + 1) % 6)
    assert len(transport.write_calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", [-1, 6, 255])
async def test_unknown_system_modes_remain_rejected(mode: int) -> None:
    reg = CORE_REGISTERS["system_mode"]
    transport = FakeModbusTransport(input_registers={1005: mode & 0xFFFF})
    client = IdmModbusClient("127.0.0.1", transport=transport)
    assert await client.read_batch([reg]) == {}
    with pytest.raises(ValueError):
        await client.write_register(reg, mode)
    assert transport.write_calls == []


def test_holiday_option_does_not_change_navigator_17_mode_meanings() -> None:
    assert SystemMode.HOLIDAY == 3
    assert CORE_REGISTERS["system_mode"].enum_options == SYSTEM_MODE_OPTIONS
    assert SYSTEM_MODE_OPTIONS[3] == "Holiday"
    legacy = build_register_map(model_info=_model_info(MODEL_NAVIGATOR_17))
    assert "system_mode" not in legacy
    assert legacy["system_mode_17"].enum_options == {
        0: "Standby",
        1: "Automatic",
        2: "Hot Water",
        3: "Hot Water Once",
    }
