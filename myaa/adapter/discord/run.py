import os
from dotenv import load_dotenv
import discord
from discord.ext import commands

from myaa.src.session_manager import SessionManager
from myaa.src.graph_setup import stream_chat, stream_chat_debug, list_graph_states

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_BOT_TOKEN が設定されていません。")

session_mgr = SessionManager()


class ChatService:
    def __init__(self, session_mgr: SessionManager):
        self.session_mgr = session_mgr
        self.debug_map: dict[str, bool] = {}
        self.char_bindings: dict[str, str] = {}
        self.joined_channels: set[int] = set()

    def toggle_debug(self, session_key: str) -> bool:
        current = self.debug_map.get(session_key, False)
        self.debug_map[session_key] = not current
        return not current

    def get_debug(self, session_key: str) -> bool:
        return self.debug_map.get(session_key, False)

    def bind_character(self, session_key: str, char_id: str):
        self.char_bindings[session_key] = char_id

    def get_character(self, session_key: str) -> str:
        return self.char_bindings.get(session_key, "example")

    async def chat(self, session_key: str, user_text: str) -> str | None:
        thread_id = self.session_mgr.resolve(session_key)
        debug = self.get_debug(session_key)
        persona_id = self.get_character(session_key)
        last_reply: str | None = None
        async for chunk in stream_chat(thread_id, user_text, persona_id):
            last_reply = chunk
        if debug:
            async for chunk in stream_chat_debug(thread_id, user_text, persona_id):
                print(chunk)
        return last_reply

    def dump(self) -> str:
        return list_graph_states(self.session_mgr)


service = ChatService(session_mgr)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


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
    service.joined_channels.discard(ctx.channel.id)
    await ctx.send(f"👋 {char_id} が退出しました。")


@bot.command()
async def debug(ctx: commands.Context):
    key = make_session_key(ctx)
    new_state = service.toggle_debug(key)
    await ctx.send(f"🔧 Debug mode: {'ON' if new_state else 'OFF'}")


@bot.command(name="char")
async def char(ctx: commands.Context, character_id: str):
    key = make_session_key(ctx)
    service.bind_character(key, character_id)
    await ctx.send(f"🔖 Character set to `{character_id}`")


@bot.command()
async def chat(ctx: commands.Context, *, text: str):
    key = make_session_key(ctx)
    if key not in service.debug_map:
        service.debug_map[key] = False
    async with ctx.channel.typing():
        reply = await service.chat(key, text)
    if reply:
        await ctx.send(reply)


@bot.command()
async def dump(ctx: commands.Context):
    dump_text = service.dump()
    if len(dump_text) > 1900:
        dump_text = dump_text[:1900] + "\n…（省略）"
    await ctx.send(f"```{dump_text}```")


@bot.event
async def on_message(msg: discord.Message):
    await bot.process_commands(msg)
    if msg.author.bot:
        return
    if msg.content.startswith("!"):
        return
    if msg.channel.id not in service.joined_channels:
        return
    session_key = make_session_key(msg)
    user_text = msg.content
    reply = await service.chat(session_key, user_text)
    if reply:
        await msg.channel.send(reply)

def entrypoint():
    assert TOKEN is not None
    bot.run(TOKEN)
