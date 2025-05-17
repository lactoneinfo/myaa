import os
import asyncio
import discord
from dotenv import load_dotenv
from myaa.src.session_manager import SessionManager
from myaa.src.graph_setup import stream_chat, list_graph_states

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

session_mgr = SessionManager()
char_bindings: dict[str, str] = {}


class MyaaBot(discord.Client):
    async def on_ready(self):
        print(f"Logged in as {self.user}")

    async def on_message(self, msg: discord.Message):
        if msg.author.bot:
            return

        content = msg.content.strip()
        session_key = f"{msg.channel.id}:{getattr(msg, 'thread', None) or 0}"

        if content == "!char list":
            chars = ["example", "assistant"]
            # TODO:
            await msg.channel.send("🧠 Available: " + ", ".join(chars))
            return

        if content.startswith("!char set "):
            char_id = content[len("!char set ") :].strip()
            char_bindings[session_key] = char_id
            await msg.channel.send(f"✅ Character set to '{char_id}' for this session.")
            return

        if content.startswith("!chat "):
            user_text = content[len("!chat ") :]
            responder_id = char_bindings.get(session_key, "example")
            thread_id = session_mgr.resolve(session_key)
            final_text = ""
            async for chunk in _run_graph(thread_id, user_text, responder_id):
                final_text = chunk
            await msg.channel.send(final_text)
            return
        
        if content == "!dump":
            dump_text = list_graph_states(session_mgr)
            await msg.channel.send("```" + dump_text[:1900] + "```")
            return


async def _run_graph(thread_id: str, user_text: str, responder_id: str):
    # Thin async wrapper around the sync generator for Discord streaming
    # loop = asyncio.get_running_loop()
    for chunk in stream_chat(thread_id, user_text, responder_id):
        yield chunk


async def main():
    intents = discord.Intents.default()
    intents.message_content = True
    client = MyaaBot(intents=intents)
    if TOKEN is None:
        raise RuntimeError("DISCORD_BOT_TOKEN not set")
    await client.start(TOKEN)


def entrypoint():
    asyncio.run(main())
