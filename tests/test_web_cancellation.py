"""Connection cancellation must release resources owned by web clients."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from idm_heatpump.web import IdmNavigator10WebClient, IdmNavigator20WebClient


@pytest.mark.asyncio
@pytest.mark.parametrize("navigator", ["10", "20"])
async def test_cancelled_connection_closes_owned_resources(navigator: str) -> None:
    entered = asyncio.Event()

    async def wait_for_cancellation(*args: object, **kwargs: object) -> str:
        entered.set()
        await asyncio.Event().wait()
        return ""

    session = AsyncMock()
    ws = AsyncMock()
    session.ws_connect.return_value = ws
    if navigator == "10":
        client = IdmNavigator10WebClient("192.0.2.10", "1234", session=session)
        client._own_session = True
        client._receive_text = AsyncMock(side_effect=wait_for_cancellation)
        task = asyncio.create_task(client.connect())
    else:
        nav20 = IdmNavigator20WebClient("192.0.2.10", "1234", session=session)
        nav20._own_session = True
        nav20._initial_get = AsyncMock(side_effect=wait_for_cancellation)
        task = asyncio.create_task(nav20.connect())
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    session.close.assert_awaited_once()
    if navigator == "10":
        ws.close.assert_awaited_once()
        assert client._ws is None
        assert client._session is None
    else:
        assert nav20._session is None
