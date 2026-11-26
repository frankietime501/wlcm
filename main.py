# main.py
import logging
import os
import time

import discord

from config import BOT_TOKEN, WELCOME_CHANNEL_ID, ID_CODE_PREFIX, LOG_LEVEL
from database import init_db, get_or_create_member_code
from image_generator import generate_id_card

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
log = logging.getLogger("bot")

HEARTBEAT = "/tmp/bot_alive"

intents = discord.Intents.default()
intents.members = True          # only what we need

bot = discord.Client(intents=intents)


@bot.event
async def on_ready():
    init_db()
    open(HEARTBEAT, "w").close()
    log.info("Logged in as %s (ID: %s) | guilds: %d",
             bot.user, bot.user.id, len(bot.guilds))

    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        log.warning("BOT_TOKEN is still the placeholder — set it via env or config.py")
    if WELCOME_CHANNEL_ID == 123456789012345678:
        log.warning("WELCOME_CHANNEL_ID is still the placeholder — set it via env or config.py")


@bot.event
async def on_member_join(member: discord.Member):
    if member.bot:
        return

    channel = member.guild.get_channel(WELCOME_CHANNEL_ID)
    if channel is None:
        log.warning("Channel %d not found in guild %d",
                    WELCOME_CHANNEL_ID, member.guild.id)
        return

    code = get_or_create_member_code(member.guild.id, member.id, ID_CODE_PREFIX)
    welcome_text = f"Welcome Agent {member.mention} to FBI!"

    try:
        file = await generate_id_card(member, code)
        await channel.send(content=welcome_text, file=file)
        log.info("Sent ID card for %s (%d) code=%s", member, member.id, code)
    except Exception:
        log.exception("Failed to send ID card for %s", member)
        try:
            await channel.send(content=welcome_text)
        except Exception:
            log.exception("Fallback message also failed")


@bot.event
async def on_disconnect():
    try:
        os.remove(HEARTBEAT)
    except FileNotFoundError:
        pass


if __name__ == "__main__":
    # touch heartbeat initially so healthcheck has something
    open(HEARTBEAT, "w").close()
    bot.run(BOT_TOKEN, log_handler=None)