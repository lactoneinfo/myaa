import os
from fastapi import FastAPI, WebSocket
from pydantic import BaseModel
import uvicorn
import websockets
import asyncio
import datetime
import pytz

from myaa.src.session_manager import SessionManager
from myaa.src.graph_setup import (
    stream_chat,
    stream_chat_debug,
    list_graph_states,
    default_persona_id,
)

BOT_WS_URL = "ws://127.0.0.1:8765"
JST = pytz.timezone("Asia/Tokyo")

app = FastAPI()
session_mgr = SessionManager()


class ChatReq(BaseModel):
    session_key: str
    user_text: str
    speaker: str
    persona_id: str | None = None
    debug: bool = False


@app.post("/chat")
async def chat(req: ChatReq):
    thread_id = session_mgr.resolve(req.session_key)
    persona = req.persona_id or default_persona_id
    last_reply = None

    async for chunk in stream_chat(thread_id, req.user_text, persona, req.speaker):
        last_reply = chunk

    if req.debug:
        async for d in stream_chat_debug(
            thread_id, req.user_text, persona, req.speaker
        ):
            print(d)

    return {"reply": last_reply, "session_key": req.session_key}


@app.websocket("/chat_ws")
async def chat_ws(ws: WebSocket):
    await ws.accept()
    try:
        req = await ws.receive_json()
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
    except Exception as e:
        await ws.send_json({"event": "error", "message": str(e)})
    finally:
        await ws.close()


@app.get("/dump")
async def dump_states():
    return {"text": list_graph_states(session_mgr)}


async def trigger_bot():
    async with websockets.connect(BOT_WS_URL) as ws:
        await ws.send("Agent からのメッセージ")
        print("[Agent] Trigger sent")


async def send_time_every_5min():
    while True:
        try:
            now = datetime.datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
            async with websockets.connect(BOT_WS_URL, ping_interval=20) as ws:
                await ws.send(f"[Agent 時刻] {now}")
                print(f"[Agent] Sent time: {now}")
        except Exception as e:
            print(f"[Agent] Failed to send time: {e}")
        await asyncio.sleep(300)


@app.on_event("startup")
async def _on_startup():
    asyncio.create_task(send_time_every_5min())


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("AGENT_PORT", "8000")))
