import os
from fastapi import FastAPI, WebSocket
from pydantic import BaseModel
import uvicorn
import websockets
import asyncio
import datetime
import pytz
import json
from typing import Optional
from starlette.websockets import WebSocketDisconnect
import contextlib

from myaa.src.session_manager import SessionManager
from myaa.src.graph_setup import (
    stream_chat,
    stream_chat_debug,
    stream_assistant_first,
    list_graph_states,
    default_persona_id,
)

BOT_WS_URL = "ws://127.0.0.1:8765"
JST = pytz.timezone("Asia/Tokyo")
jihou_session_key: Optional[str] = None
jihou_active = False
jihou_event = asyncio.Event()

app = FastAPI()
session_mgr = SessionManager()


class ChatReq(BaseModel):
    session_key: str
    user_text: str
    speaker: str
    persona_id: str | None = None
    debug: bool = False


@app.websocket("/chat_ws")
async def chat_ws(ws: WebSocket):
    await ws.accept()
    try:
        req = await ws.receive_json()

        ev = req.get("event")
        if ev == "jihou_register":
            global jihou_session_key, jihou_active, jihou_event
            jihou_session_key = str(req["session_key"])
            jihou_active = True
            jihou_event.set()
            return
        elif ev == "jihou_unregister":
            jihou_session_key = None
            jihou_active = False
            jihou_event.clear()
            return

        session_key = req["session_key"]
        user_text = req["user_text"]
        speaker = req["speaker"]
        persona_id = req.get("persona_id") or default_persona_id
        debug = bool(req.get("debug", False))

        thread_id = session_mgr.resolve(session_key)

        async for chunk in stream_chat(thread_id, user_text, persona_id, speaker):
            await ws.send_json(
                {"event": "token", "session_key": session_key, "delta": chunk}
            )

        if debug:
            async for d in stream_chat_debug(thread_id, user_text, persona_id, speaker):
                await ws.send_json(
                    {"event": "debug", "session_key": session_key, "delta": d}
                )

        await ws.send_json({"event": "done", "session_key": session_key})

    except WebSocketDisconnect:
        return
    except Exception as e:
        await ws.send_json({"event": "error", "message": str(e)})
    finally:
        with contextlib.suppress(Exception):
            await ws.close()


@app.get("/dump")
async def dump_states():
    return {"text": list_graph_states(session_mgr)}


def seconds_until_next_7am_jst() -> float:
    now = datetime.datetime.now(JST)
    target = now.replace(hour=7, minute=0, second=0, microsecond=0)
    if now >= target:
        target += datetime.timedelta(days=1)
    return (target - now).total_seconds()


async def morning_greeting_loop():
    while True:
        if not jihou_active:
            await jihou_event.wait()

        remain = seconds_until_next_7am_jst()
        while remain > 0 and jihou_active:
            dt = min(remain, 30)
            await asyncio.sleep(dt)
            remain -= dt
        if not jihou_active or not jihou_session_key:
            continue

        now = datetime.datetime.now(JST).strftime("%Y-%m-%d %H:%M")
        system_prompt = (
            "INSTRUCTION: 朝の時報メッセージを1通だけ生成してください。\n"
            f"- 現在時刻（JST）は {now} です。\n"
        )
        try:
            thread_id = session_mgr.resolve(jihou_session_key)
            persona_id = default_persona_id

            async with websockets.connect(BOT_WS_URL, ping_interval=20) as ws:
                async for chunk in stream_assistant_first(
                    thread_id, system_prompt, persona_id
                ):
                    if chunk:
                        await ws.send(
                            json.dumps(
                                {
                                    "event": "token",
                                    "session_key": jihou_session_key,
                                    "delta": chunk,
                                }
                            )
                        )
                await ws.send(
                    json.dumps({"event": "done", "session_key": jihou_session_key})
                )
        except Exception as e:
            print(f"[Agent] greeting error: {e}")
            await asyncio.sleep(60)


@app.on_event("startup")
async def _on_startup():
    asyncio.create_task(morning_greeting_loop())


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("AGENT_PORT", "8000")))
