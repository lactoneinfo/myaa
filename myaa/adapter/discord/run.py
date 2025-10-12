import datetime as dt
import pytz
import asyncio
import os
from dotenv import load_dotenv
import discord
from discord.ext import commands, tasks
from typing import cast
import aiohttp

from myaa.src.graph_setup import default_persona_id

JST = pytz.timezone("Asia/Tokyo")
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_BOT_TOKEN が設定されていません。")
REMINDER_SPEAKER = "時報"

AGENT_HOST = os.getenv("AGENT_HOST", "127.0.0.1")
AGENT_PORT = os.getenv("AGENT_PORT", "8000")
AGENT_HTTP = f"http://{AGENT_HOST}:{AGENT_PORT}"


async def agent_chat_http(
    session_key: str, user_text: str, speaker: str, persona_id: str, debug: bool
) -> dict | None:
    async with aiohttp.ClientSession() as sess:
        async with sess.post(
            f"{AGENT_HTTP}/chat",
            json={
                "session_key": session_key,
                "user_text": user_text,
                "speaker": speaker,
                "persona_id": persona_id,
                "debug": debug,
            },
        ) as r:
            r.raise_for_status()
            res = await r.json()
            return res


async def agent_dump_http() -> str:
    async with aiohttp.ClientSession() as sess:
        async with sess.get(f"{AGENT_HTTP}/dump") as r:
            r.raise_for_status()
            data = await r.json()
            return data.get("text", "")


class ChatService:
    def __init__(self, default_persona):
        self.default_persona = default_persona
        self.debug_map: dict[str, bool] = {}
        self.char_bindings: dict[str, str] = {}
        self.joined_channels: set[int] = set()
        self.jihou_channels: set[int] = set()

    def toggle_debug(self, session_key: str) -> bool:
        current = self.debug_map.get(session_key, False)
        self.debug_map[session_key] = not current
        return not current

    def get_debug(self, session_key: str) -> bool:
        return self.debug_map.get(session_key, False)

    def bind_character(self, session_key: str, char_id: str):
        self.char_bindings[session_key] = char_id

    def get_character(self, session_key: str) -> str:
        return self.char_bindings.get(session_key, self.default_persona)

    async def chat(self, session_key: str, user_text: str, speaker: str) -> dict | None:
        debug = self.get_debug(session_key)
        persona_id = self.get_character(session_key)
        return await agent_chat_http(session_key, user_text, speaker, persona_id, debug)

    async def dump(self) -> str:
        return await agent_dump_http()


service = ChatService(default_persona=default_persona_id)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

pending_typing: dict[
    str, tuple[discord.abc.Messageable, asyncio.Event, asyncio.Task]
] = {}


async def _typing_runner(session_key: str):
    ch, stop_evt, _ = pending_typing[session_key]
    async with ch.typing():
        await stop_evt.wait()


def start_typing(session_key: str, ch: discord.abc.Messageable):
    if session_key in pending_typing:
        return
    stop_evt = asyncio.Event()
    task = asyncio.create_task(_typing_runner(session_key))
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


@tasks.loop(seconds=60)
async def midnight_lights_off():
    """毎日 0:00 に時報チャンネルへ『消灯して』プロンプトを送る"""
    now = dt.datetime.now(JST)
    if not (now.hour == 0 and now.minute == 0):
        return

    for cid in list(service.jihou_channels):
        ch_raw = bot.get_channel(cid)
        if ch_raw is None:
            service.jihou_channels.discard(cid)
            continue

        session_key = f"{cid}:{cid}"
        prompt = (
            "INSTRUCTION: 0時になりました。ツールを使用して部屋の照明を消灯してください。"
            "\nキャラクターとして適当なコメントを添えてください。"
        )
        ch = cast(discord.abc.Messageable, ch_raw)
        async with ch.typing():
            reply = await service.chat(session_key, prompt, speaker=REMINDER_SPEAKER)
        if reply:
            await ch.send(reply)


@midnight_lights_off.before_loop
async def _wait_ready():
    await bot.wait_until_ready()


@bot.event
async def on_ready():
    user = bot.user
    assert user is not None, "User should be set in on_ready()"
    print(f"Logged in as {user} (ID: {user.id})")
    if not midnight_lights_off.is_running():
        midnight_lights_off.start()


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


@bot.command()
async def debug(ctx: commands.Context):
    if os.getenv("DEBUG_MODE") != "1":
        await ctx.send(
            "⚠️ This command is disabled. Set DEBUG_MODE=1 in your .env to enable it."
        )
        return
    key = make_session_key(ctx)
    new_state = service.toggle_debug(key)
    await ctx.send(f"🔧 Debug mode: {'ON' if new_state else 'OFF'}")


@bot.command(name="char")
async def char(ctx: commands.Context, character_id: str):
    key = make_session_key(ctx)
    service.bind_character(key, character_id)
    await ctx.send(f"🔖 Character set to `{character_id}`")


@bot.command()
async def jihou(ctx: commands.Context, mode: str | None = None):
    """!jihou        → 0 時時報 ON
    !jihou off    → OFF"""
    cid = ctx.channel.id
    if mode == "off":
        service.jihou_channels.discard(cid)
        await ctx.send("🔕 時報を停止しました")
        return

    if cid in service.joined_channels:
        await ctx.send(
            "⚠️ ここは !join 済みなので時報にできません（!leave してください）"
        )
        return

    service.jihou_channels.add(cid)
    await ctx.send("🔔 このチャンネルで毎日 0 時に消灯するよ！")


@bot.command()
async def dump(ctx: commands.Context):
    if os.getenv("DEBUG_MODE") != "1":
        await ctx.send(
            "⚠️ This command is disabled. Set DEBUG_MODE=1 in your .env to enable it."
        )
        return
    dump_text = await service.dump()
    if len(dump_text) > 1900:
        dump_text = dump_text[:1900] + "\n…（省略）"
    await ctx.send(f"```{dump_text}```")


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
    bot.run(TOKEN)
