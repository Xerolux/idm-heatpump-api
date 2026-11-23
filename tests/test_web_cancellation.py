"""Connection cancellation must release resources owned by web clients."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from idm_heatpump.web import (
    IdmNavigator10WebClient,
    IdmNavigator20WebClient,
    IdmWebConnectionError,
)


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


@pytest.mark.asyncio
async def test_close_during_handshake_releases_the_websocket() -> None:
    """close() while the Navigator 10 handshake is in flight must not leave a socket behind.

    close() takes no lock, so it can run while connect() is suspended in the
    HTTP upgrade. The websocket opened after that moment belongs to a closed
    client; it has to be closed as well, and connect() has to report the
    closed client instead of succeeding.
    """
    handshake_started = asyncio.Event()
    release_handshake = asyncio.Event()
    ws = AsyncMock()
    session = AsyncMock()

    async def slow_ws_connect(*args: object, **kwargs: object) -> AsyncMock:
        handshake_started.set()
        await release_handshake.wait()
        return ws

    session.ws_connect.side_effect = slow_ws_connect
    client = IdmNavigator10WebClient("192.0.2.10", "1234", session=session)

    task = asyncio.create_task(client.connect())
    await handshake_started.wait()
    await client.close()
    release_handshake.set()

    with pytest.raises(IdmWebConnectionError, match="closed while connecting"):
        await task

    ws.close.assert_awaited_once()
    assert client._ws is None
