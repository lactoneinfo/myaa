import pytz
import asyncio
import os
from dotenv import load_dotenv
import discord
from discord.ext import commands
from typing import cast, Any, Optional
import json
import websockets

from myaa.src.graph_setup import default_persona_id

JST = pytz.timezone("Asia/Tokyo")
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_BOT_TOKEN が設定されていません。")
REMINDER_SPEAKER = "時報"

AGENT_HOST = os.getenv("AGENT_HOST", "127.0.0.1")
AGENT_PORT = os.getenv("AGENT_PORT", "8000")
AGENT_WS = f"ws://{AGENT_HOST}:{AGENT_PORT}/chat_ws"


async def agent_chat_ws(
    session_key: str, user_text: str, speaker: str, persona_id: str
) -> dict:
    last: str = ""
    async with websockets.connect(AGENT_WS, ping_interval=20) as ws:
        await ws.send(
            json.dumps(
                {
                    "session_key": session_key,
                    "user_text": user_text,
                    "speaker": speaker,
                    "persona_id": persona_id,
                }
            )
        )
        async for raw in ws:
            if isinstance(raw, (bytes, bytearray)):
                ev = json.loads(raw.decode("utf-8", "replace"))
            else:
                ev = json.loads(raw)
            et = ev.get("event")
            if et == "token":
                last = ev.get("delta", "") or ""
            elif et == "done":
                break
            elif et == "error":
                raise RuntimeError(ev.get("message", "ws error"))
    return {"reply": last, "session_key": session_key}


class ChatService:
    def __init__(self, default_persona):
        self.default_persona = default_persona
        self.char_bindings: dict[str, str] = {}
        self.joined_channels: set[int] = set()
        self.jihou_channels: set[int] = set()

    def bind_character(self, session_key: str, char_id: str):
        self.char_bindings[session_key] = char_id

    def get_character(self, session_key: str) -> str:
        return self.char_bindings.get(session_key, self.default_persona)

    async def chat(self, session_key: str, user_text: str, speaker: str) -> dict | None:
        persona_id = self.get_character(session_key)
        return await agent_chat_ws(session_key, user_text, speaker, persona_id)


async def bot_ws_handler(ws):
    try:
        last: str = ""
        sk: Optional[str] = None

        async for raw in ws:
            if isinstance(raw, (bytes, bytearray)):
                ev = json.loads(raw.decode("utf-8", "replace"))
            else:
                ev = json.loads(raw)

            et = ev.get("event")
            if et == "token":
                sk = ev.get("session_key", sk)
                last = ev.get("delta", "") or ""
            elif et == "error":
                print(f"[Bot WS] agent error: {ev.get('message')}")
            elif et == "done":
                if not sk:
                    last = ""
                text = (last or "").strip()
                if text:
                    sk = ev.get("session_key")
                    if not sk:
                        continue
                    cid = int(sk.split(":")[0])
                    ch_raw = bot.get_channel(cid)
                    if ch_raw:
                        ch = cast(discord.abc.Messageable, ch_raw)
                        await ch.send(text)
                last = ""
                sk = None
            else:
                continue
    except Exception as e:
        print(f"[Bot WS] error: {e}")


async def start_bot_ws_server():
    async with websockets.serve(bot_ws_handler, "0.0.0.0", 8765):
        print("[Bot WS] listening on ws://0.0.0.0:8765")
        await asyncio.Future()


service = ChatService(default_persona=default_persona_id)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

pending_typing: dict[
    str, tuple[discord.abc.Messageable, asyncio.Event, asyncio.Task[Any]]
] = {}


async def _typing_runner(session_key: str):
    ch, stop_evt, _ = pending_typing[session_key]
    async with ch.typing():
        await stop_evt.wait()


def start_typing(session_key: str, ch: discord.abc.Messageable):
    if session_key in pending_typing:
        return
    stop_evt = asyncio.Event()
    task: asyncio.Task[Any] = asyncio.create_task(_typing_runner(session_key))
    pending_typing[session_key] = (ch, stop_evt, task)


def stop_typing(session_key: str):
    tpl = pending_typing.get(session_key)
    if not tpl:
        return
    _, stop_evt, task = tpl
    stop_evt.set()
    pending_typing.pop(session_key, None)


async def dispatch_chat_and_send(session_key: str, user_text: str, speaker: str):
    try:
        res = await service.chat(session_key, user_text, speaker)
        reply = res.get("reply") if res else None
    except Exception as e:
        reply = f"（エラー）{e}"

    try:
        cid = int(session_key.split(":")[0])
        ch_raw = bot.get_channel(cid)
        if ch_raw:
            ch = cast(discord.abc.Messageable, ch_raw)
            if reply:
                await ch.send(reply)
    finally:
        stop_typing(session_key)


@bot.event
async def on_ready():
    user = bot.user
    assert user is not None, "User should be set in on_ready()"
    print(f"Logged in as {user} (ID: {user.id})")


def make_session_key(ctx_or_msg) -> str:
    if isinstance(ctx_or_msg, discord.Message):
        cid = ctx_or_msg.channel.id
        return f"{cid}:{cid}"
    channel_id = ctx_or_msg.channel.id
    return f"{channel_id}:{channel_id}"


@bot.command()
async def join(ctx: commands.Context):
    key = make_session_key(ctx)
    char_id = service.get_character(key)
    service.joined_channels.add(ctx.channel.id)
    await ctx.send(f"✅ {char_id} がログインしました。")


@bot.command()
async def leave(ctx: commands.Context):
    key = make_session_key(ctx)
    char_id = service.get_character(key)

    prompt = (
        "INSTRUCTION: ログアウトします。"
        "save_user_memory を使用して、このセッションで会話した全ユーザー(AI自身を除く)の会話履歴を保存してください。\n"
        "キャラクターとして適当なコメントを添えてください。"
    )

    async with ctx.channel.typing():
        res = await service.chat(key, prompt, speaker=char_id)
    if res and (reply := res.get("reply")):
        await ctx.send(reply)

    service.joined_channels.discard(ctx.channel.id)
    await ctx.send(f"👋 {char_id} が退出しました。")


@bot.command(name="char")
async def char(ctx: commands.Context, character_id: str):
    key = make_session_key(ctx)
    service.bind_character(key, character_id)
    await ctx.send(f"🔖 Character set to `{character_id}`")


@bot.command()
async def jihou(ctx: commands.Context, mode: str | None = None):
    cid = ctx.channel.id
    if mode == "off":
        service.jihou_channels.discard(cid)
        await ctx.send("🔕 時報を停止しました")
        async with websockets.connect(AGENT_WS, ping_interval=20) as ws:
            await ws.send(json.dumps({"event": "jihou_unregister"}))
        return

    if cid in service.joined_channels:
        await ctx.send(
            "⚠️ ここは !join 済みなので時報にできません（!leave してください）"
        )
        return

    service.jihou_channels.add(cid)
    await ctx.send("🔔 時報を登録しました")

    session_key = f"{cid}:{cid}"
    async with websockets.connect(AGENT_WS, ping_interval=20) as ws:
        await ws.send(
            json.dumps({"event": "jihou_register", "session_key": session_key})
        )


@bot.event
async def on_message(msg: discord.Message):
    await bot.process_commands(msg)
    if msg.author == bot.user or msg.content.startswith("!"):
        return
    if (
        msg.channel.id not in service.joined_channels
        and msg.channel.id not in service.jihou_channels
    ):
        return
    if msg.author.bot and msg.author != bot.user:
        await asyncio.sleep(2)
    session_key = make_session_key(msg)
    user_text = msg.content
    speaker = msg.author.display_name
    start_typing(session_key, msg.channel)
    asyncio.create_task(dispatch_chat_and_send(session_key, user_text, speaker))


def entrypoint():
    assert TOKEN is not None

    async def main():
        bot_task = asyncio.create_task(bot.start(TOKEN))
        ws_task = asyncio.create_task(start_bot_ws_server())
        await asyncio.gather(bot_task, ws_task)

    asyncio.run(main())
