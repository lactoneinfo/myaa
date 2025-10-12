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
    stream_assistant_first,
    list_graph_states,
    default_persona_id,
)
from myaa.src.tools.paper_watch import fetch_all_last_24h_rich

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

        thread_id = session_mgr.resolve(session_key)

        async for chunk in stream_chat(thread_id, user_text, persona_id, speaker):
            await ws.send_json(
                {"event": "token", "session_key": session_key, "delta": chunk}
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
    target = now.replace(hour=1, minute=8, second=0, microsecond=0)
    if now >= target:
        target += datetime.timedelta(days=1)
    return (target - now).total_seconds()


def next_7am_jst(now: datetime.datetime | None = None) -> datetime.datetime:
    now = now or datetime.datetime.now(JST)
    target = now.replace(hour=8, minute=0, second=0, microsecond=0)
    if now >= target:
        target += datetime.timedelta(days=1)
    return target


def seconds_until(dt: datetime.datetime) -> float:
    now = datetime.datetime.now(JST)
    return max(0.0, (dt - now).total_seconds())


async def _emit_ws_text(session_key: str, text: str):
    async with websockets.connect(BOT_WS_URL, ping_interval=20) as ws:
        await ws.send(
            json.dumps({"event": "token", "session_key": session_key, "delta": text})
        )
        await ws.send(json.dumps({"event": "done", "session_key": session_key}))


def build_greeting_instruction(now_txt: str) -> str:
    return (
        "INSTRUCTION: 時報の朝挨拶を1通だけ生成してください。\n"
        f"- 現在時刻（JST）は {now_txt} です。\n"
        "- 1～2文、合計120字以内。\n"
        "- 季節や天気の軽い雑談を一言添え、直後に論文ニュースが始まることを告げてください。\n"
    )


def build_paper_instruction(i: int, n: int, item: dict) -> str:
    title = item["title"]
    url = item["url"]
    abs_ = item["abstract"]
    org = item.get("org") or "（所属不明）"
    authors = ", ".join(item.get("authors") or []) or "（著者情報なし）"
    return (
        "INSTRUCTION: 論文ニュースを紹介してください。直前のメッセージから違和感なく接続してください。(例: 次のニュースです。等)"
        f"全{n}報中の{i}報目\n"
        "- 出力は以下の3つを必ず含めてください：\n"
        "  - タイトル\n"
        "  - URL\n"
        "  - 要約（300字以内, 研究組織, 著者情報をなるべく含める, キャラクター設定, 口調を守る\n"
        "===\n"
        f"タイトル: {title}\n"
        f"研究組織: {org}\n"
        f"著者: {authors}\n"
        f"要約素材（英語）: {abs_}\n"
        f"URL: {url}\n"
        "===\n"
    )


def build_closing_instruction(n: int) -> str:
    return (
        "INSTRUCTION: 朝の論文ニュースの締めの一文を1通だけ出力してください。\n"
        f"- 今日は {n} 本紹介しました。\n"
    )


async def relay_stream_assistant_first(
    session_key: str, instruction_text: str, persona_id: str | None = None
):
    thread_id = session_mgr.resolve(session_key)
    persona = persona_id or default_persona_id
    async with websockets.connect(BOT_WS_URL, ping_interval=20) as bot_ws:
        async for chunk in stream_assistant_first(thread_id, instruction_text, persona):
            if chunk:
                await bot_ws.send(
                    json.dumps(
                        {"event": "token", "session_key": session_key, "delta": chunk}
                    )
                )
        await bot_ws.send(json.dumps({"event": "done", "session_key": session_key}))


async def morning_paper_per_minute_loop():
    while True:
        if not jihou_active:
            await jihou_event.wait()

        start_dt = next_7am_jst()
        await asyncio.sleep(seconds_until(start_dt))
        if not jihou_active or not jihou_session_key:
            continue

        try:
            opml_path = os.getenv("PAPER_OPML_PATH", "").strip()
            if not opml_path:
                await _emit_ws_text(
                    jihou_session_key,
                    "（お知らせ）PAPER_OPML_PATH が未設定のため、今日は論文収集ができませんでした。",
                )
                continue

            items = fetch_all_last_24h_rich(opml_path)
            MAX_ITEMS = 30
            items = items[:MAX_ITEMS]
            n = len(items)

            now_txt = datetime.datetime.now(JST).strftime("%Y-%m-%d %H:%M")
            greet_ins = build_greeting_instruction(now_txt)
            await relay_stream_assistant_first(jihou_session_key, greet_ins)

            for i, item in enumerate(items, start=1):
                slot_dt = start_dt + datetime.timedelta(minutes=i)
                await asyncio.sleep(seconds_until(slot_dt))
                inst = build_paper_instruction(i, n, item)
                await relay_stream_assistant_first(jihou_session_key, inst)

            end_dt = start_dt + datetime.timedelta(minutes=n + 1)
            await asyncio.sleep(seconds_until(end_dt))
            closing_ins = build_closing_instruction(n)
            await relay_stream_assistant_first(jihou_session_key, closing_ins)

        except Exception as e:
            print(f"[Agent] per-minute loop error: {e}")
            await asyncio.sleep(60)


@app.on_event("startup")
async def _on_startup():
    asyncio.create_task(morning_paper_per_minute_loop())


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("AGENT_PORT", "8000")))
