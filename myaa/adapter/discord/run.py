import discord
import asyncio
import os
from dotenv import load_dotenv
from myaa.data.cache import AgentStateCache
from myaa.logic.orchestrator import Orchestrator
from myaa.logic.domain.message import Message

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

cache = AgentStateCache()
orchestrator = Orchestrator(cache)


class MyaaBot(discord.Client):
    async def on_ready(self):
        print(f"Logged in as {self.user}")

    async def on_message(self, discord_message: discord.Message):
        if discord_message.author.bot:
            return

        content = discord_message.content.strip()
        session_key = f"{discord_message.channel.id}:{getattr(discord_message, 'thread', None) or 0}"
        try:

            if content.startswith("!chat "):
                text = content[len("!chat ") :]
                message = Message(
                    speaker=discord_message.author.display_name,
                    content=text,
                )
                reply = await orchestrator.run(session_key, message)
                await discord_message.channel.send(reply.to_display_text())

            elif content == "!state":
                states = [s.id for s in await cache.list()]
                await message.channel.send(f"cached AS: {states}")

            elif content == "!dump":
                states = await cache.list()
                print(cache._session_map)
                print(cache._store.keys())
                lines = []
                for s in states:
                    lines.append(f"ID: {s.id} | status: {s.status}")
                    lines.append(f"  msg: {s.context.message.to_display_text()}")
                    lines.append(
                        f"  mem: {[m.to_display_text() for m in s.context.thread_memory]}"
                    )
                    lines.append("")
                await discord_message.channel.send(
                    "```" + "\n".join(lines)[:1900] + "```"
                )
        except Exception as e:
            await discord_message.channel.send(f"⚠️ Error: {e}")
            raise


async def main():
    intents = discord.Intents.default()
    intents.message_content = True
    client = MyaaBot(intents=intents)
    await client.start(TOKEN)


def entrypoint():
    asyncio.run(main())
