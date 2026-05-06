import asyncio
import os

import websockets
import websockets.exceptions
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["websocket"])

MESSAGING_WS = os.getenv("MESSAGING_WS", "ws://localhost:8001")


@router.websocket("/ws/chat/")
async def ws_proxy(websocket: WebSocket):
    query = websocket.scope.get("query_string", b"").decode()
    upstream_url = f"{MESSAGING_WS}/ws/chat/?{query}"

    await websocket.accept()

    try:
        async with websockets.connect(upstream_url) as upstream:

            async def _browser_to_upstream():
                try:
                    while True:
                        text = await websocket.receive_text()
                        await upstream.send(text)
                except (WebSocketDisconnect, Exception):
                    await upstream.close()

            async def _upstream_to_browser():
                try:
                    async for message in upstream:
                        await websocket.send_text(message)
                except Exception:
                    pass

            done, pending = await asyncio.wait(
                [
                    asyncio.ensure_future(_browser_to_upstream()),
                    asyncio.ensure_future(_upstream_to_browser()),
                ],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()

    except websockets.exceptions.InvalidURI:
        await websocket.close(code=1011)
    except Exception:
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
