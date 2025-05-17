import os
from dotenv import load_dotenv
import discord
from discord.ext import commands

# 依存モジュール（疎結合のチャットサービスとセッション管理）
from myaa.src.session_manager import SessionManager
from myaa.src.graph_setup import stream_chat, stream_chat_debug, list_graph_states


load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_BOT_TOKEN が設定されていません。")

# セッション管理とチャットサービス
session_mgr = SessionManager()


class ChatService:
    def __init__(self, session_mgr: SessionManager):
        self.session_mgr = session_mgr
        self.debug_map: dict[str, bool] = {}
        self.char_bindings: dict[str, str] = {}

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

    async def chat(self, session_key: str, user_text: str, speaker: str) -> str | None:
        thread_id = self.session_mgr.resolve(session_key)
        debug = self.get_debug(session_key)
        last_reply: str | None = None
        async for chunk in stream_chat(thread_id, user_text, speaker):
            last_reply = chunk
        if debug:
            async for chunk in stream_chat_debug(thread_id, user_text, speaker):
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


# セッションキー作成ユーティリティ
def make_session_key(ctx: commands.Context) -> str:
    channel_id = ctx.channel.id
    # スレッドの場合は同じIDを使う
    thread_id = channel_id
    return f"{channel_id}:{thread_id}"


@bot.command()
async def debug(ctx: commands.Context):
    key = make_session_key(ctx)
    new_state = service.toggle_debug(key)
    await ctx.send(f"🔧 Debug mode: {'ON' if new_state else 'OFF'}")


@bot.command()
async def bind(ctx: commands.Context, character_id: str):
    key = make_session_key(ctx)
    service.bind_character(key, character_id)
    await ctx.send(f"🔖 Character bound: `{character_id}`")


@bot.command()
async def chat(ctx: commands.Context, *, text: str):
    key = make_session_key(ctx)
    if key not in service.debug_map:
        service.debug_map[key] = False
    speaker = ctx.author.display_name
    async with ctx.channel.typing():
        reply = await service.chat(key, text, speaker)
    if reply:
        await ctx.send(reply)


@bot.command()
async def dump(ctx: commands.Context):
    dump_text = service.dump()
    if len(dump_text) > 1900:
        dump_text = dump_text[:1900] + "\n…（省略）"
    await ctx.send(f"```{dump_text}```")


def entrypoint():
    assert TOKEN is not None
    bot.run(TOKEN)
