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
from myaa.src.tools.paper_watch import fetch_all_last_24h

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
    target = now.replace(hour=0, minute=25, second=0, microsecond=0)
    if now >= target:
        target += datetime.timedelta(days=1)
    return (target - now).total_seconds()


async def morning_greeting_loop():
    while True:
        if not jihou_active:
            await jihou_event.wait()

        remain = seconds_until_next_7am_jst()
        while remain > 0 and jihou_active:
            dt = min(remain, 5)
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


async def morning_paper_loop():
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

        try:
            opml_path = os.getenv("PAPER_OPML_PATH", "").strip()
            if not opml_path:
                system_prompt = (
                    "INSTRUCTION: 朝の論文時報を1通だけ生成してください。"
                    "PAPER_OPML_PATH が未設定のため、今日は論文収集ができなかったことを簡潔に伝えてください。"
                )
            else:
                items = fetch_all_last_24h(opml_path)
                total = len(items)

                MAX_ITEMS = 30
                use = items[:MAX_ITEMS]

                lines = []
                for title, link, ts, summary in use:
                    when = ts.strftime("%Y-%m-%d %H:%M") if ts else ""
                    lines.append(f"{when}\t{title}\t{summary}\t{link}")
                payload = "\n".join(lines)

                now = datetime.datetime.now(JST).strftime("%Y-%m-%d %H:%M")
                system_prompt = (
                    "INSTRUCTION: 朝の論文ニュースを生成してください。\n"
                    f"- 現在時刻（JST）は {now} です。\n"
                    f"- 過去24時間に検出した論文は合計 {total} 件です。以下に最大 {len(use)} 件の生データを渡します。\n"
                    "- それぞれについて、次の形式で**一行**ずつ出力してください：\n"
                    "  タイトル｜日本語要約（100字以内）｜URL\n"
                    "- 日本語要約は、与えた英語アブスト要約（summary）がある場合は**忠実に要約**、無い場合は見つからなかった旨を報告してください。\n"
                    "- 箇条書きや番号は不要。記事ごとに改行で区切るだけにしてください。\n"
                    "- 記事件数が多い場合でも、与えたデータ分はすべて出力してください（上限は既にこちらでかけています）。\n"
                    "- 入力フォーマット：1行につき\n"
                    "  <投稿日JST>\\t<英語タイトル>\\t<英語サマリー（空可）>\\t<URL>\n"
                    "===\n"
                    f"{payload}\n"
                    "===\n"
                )

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
            print(f"[Agent] paper loop error: {e}")
            await asyncio.sleep(60)


@app.on_event("startup")
async def _on_startup():
    # asyncio.create_task(morning_greeting_loop())
    asyncio.create_task(morning_paper_loop())


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("AGENT_PORT", "8000")))
