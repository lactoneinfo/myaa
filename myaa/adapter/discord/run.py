import discord
import asyncio
import os
from dotenv import load_dotenv
from myaa.data.cache import AgentStateCache
from myaa.logic.domain.state import AgentState
from myaa.logic.orchestrator import Orchestrator
from myaa.logic.domain.message import Message
from myaa.logic.domain.character import available_characters, get_display_name
from myaa.logic.domain.command import ChatCommand

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DEBUG_MODE = os.getenv("DEBUG_MODE", "0") == "1"

cache = AgentStateCache()
orchestrator = Orchestrator(cache)
char_bindings: dict[str, str] = {}


class MyaaBot(discord.Client):
    async def on_ready(self):
        print(f"Logged in as {self.user}")

    async def on_message(self, discord_message: discord.Message):
        global char_bindings
        if discord_message.author.bot:
            return

        content = discord_message.content.strip()
        session_key = f"{discord_message.channel.id}:{getattr(discord_message, 'thread', None) or 0}"

        try:

            if content == "!char list":
                chars = available_characters()
                if not chars:
                    await discord_message.channel.send("⚠️ No characters available.")
                else:
                    try:
                        lines = []
                        for char_id in chars:
                            display_name = get_display_name(char_id)
                            lines.append(f"- {char_id}: {display_name}")
                        await discord_message.channel.send(
                            "🧠 Available characters:\n" + "\n".join(lines)
                        )
                    except Exception as e:
                        await discord_message.channel.send(
                            f"⚠️ Failed to load characters: {e}"
                        )
                return

            if content.startswith("!char set "):
                name = content[len("!char set ") :].strip()
                if name not in available_characters():
                    await discord_message.channel.send(
                        f"⚠️ Character '{name}' not found."
                    )
                    return
                char_bindings[session_key] = name
                await discord_message.channel.send(
                    f"✅ Character set to '{name}' for this session."
                )
                return

            if content.startswith("!chat "):
                text = content[len("!chat ") :]
                responder_id = char_bindings.get(session_key, "example")
                if responder_id not in available_characters():
                    await discord_message.channel.send(
                        f"⚠️ Character '{responder_id}' is not available."
                    )
                    return
                message = Message(
                    speaker_id=discord_message.author.display_name,
                    speaker_name=discord_message.author.display_name,
                    content=text,
                )
                command = ChatCommand(responder_id=responder_id, message=message)
                reply = await orchestrator.run(session_key, command)
                await discord_message.channel.send(reply.to_display_text())
                return

            if content == "!dump" and DEBUG_MODE:
                states: list[AgentState] = await cache.list()
                lines = []
                for s in states:
                    lines.append(f"ID: {s.id} | status: {s.status}")

                    if s.context.message is None:
                        lines.append("  msg: [No message]")
                        lines.append("  mem: []")
                        lines.append("")
                        continue

                    lines.append(f"  msg: {s.context.message.to_display_text()}")
                    lines.append(
                        f"  mem: {[m.to_display_text() for m in s.context.thread_memory]}"
                    )
                    lines.append("")

                await discord_message.channel.send(
                    "```" + "\n".join(lines)[:1900] + "```"
                )
                return
        except Exception as e:
            await discord_message.channel.send(f"⚠️ Error: {e}")
            raise


async def main():
    intents = discord.Intents.default()
    intents.message_content = True
    client = MyaaBot(intents=intents)
    if TOKEN is None:
        raise ValueError("DISCORD_BOT_TOKEN not found in environment.")
    await client.start(TOKEN)


def entrypoint():
    asyncio.run(main())
