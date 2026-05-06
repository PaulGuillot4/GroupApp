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
                    pass

            async def _upstream_to_browser():
                try:
                    async for message in upstream:
                        await websocket.send_text(message)
                except Exception:
                    pass

            t1 = asyncio.create_task(_browser_to_upstream())
            t2 = asyncio.create_task(_upstream_to_browser())

            done, pending = await asyncio.wait(
                [t1, t2],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    except websockets.exceptions.InvalidURI:
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
        return
    except Exception:
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
        return

    try:
        await websocket.close(code=1000)
    except Exception:
        pass
