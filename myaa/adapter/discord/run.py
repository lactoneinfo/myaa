import discord
import asyncio
import os
import time
from dotenv import load_dotenv
from myaa.data.cache import AgentStateCache
from myaa.logic.orchestrator import Orchestrator  # ← これだけでOK

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

cache = AgentStateCache()
orchestrator = Orchestrator(cache)


class MyaaBot(discord.Client):
    async def on_ready(self):
        print(f"Logged in as {self.user}")

    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        content = message.content.strip()
        session_key = f"{message.channel.id}:{getattr(message, 'thread', None) or 0}"

        if content.startswith("!chat "):
            text = content[len("!chat ") :]
            try:
                print(f"[Adapter] Received !chat: {text}")
                reply = await orchestrator.run(session_key, text)
                await message.channel.send(f"🤖: {reply}")
            except Exception as e:
                await message.channel.send(f"⚠️ Error: {e}")
                raise

        elif content == "!state":
            states = [s.id for s in await cache.list()]
            await message.channel.send(f"cached AS: {states}")

        elif content == "!dump":
            states = await cache.list()
            lines = []
            for s in states:
                lines.append(f"ID: {s.id} | status: {s.status}")
                lines.append(f"  msg: {s.context.message}")
                lines.append(f"  mem: {s.context.thread_memory}")
                lines.append(
                    f"  updated: {time.strftime('%H:%M:%S', time.localtime(s.updated_at))}"
                )
                lines.append("")
            dump_text = "```" + "\n".join(lines)[:1900] + "```"
            await message.channel.send(dump_text or "cache empty")


async def main():
    intents = discord.Intents.default()
    intents.message_content = True
    client = MyaaBot(intents=intents)
    await client.start(TOKEN)


def entrypoint():
    asyncio.run(main())
