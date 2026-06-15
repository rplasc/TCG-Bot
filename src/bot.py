import os
import time
from collections import defaultdict
import discord
from src.aclient import client
from src.commands import general, leaderboard, packs, collection, codex, casino, trades, combat, user, admin
from src.database.db import give_coins, register_user, init_db
from src.combat.session_manager import session_manager

@client.event
async def on_ready():
    # Remove any leftover guild-specific command overrides so commands
    # don't show up twice (once globally, once per-guild).
    for guild in client.guilds:
        client.tree.clear_commands(guild=guild)
        await client.tree.sync(guild=guild)

    await client.tree.sync()
    await init_db()

    print(f'Logged in as {client.user.name}')

    commands = await client.tree.fetch_commands()
    print("Registered Commands:")
    for command in commands:
        print(f"- {command.name}")
    
    session_manager.start_cleanup_task()

@client.event
async def on_close():
    await session_manager.shutdown()

@client.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    user_id = message.author.id
    username = message.author.name
    
    await register_user(user_id, username)

@client.tree.error
async def on_app_command_error(interaction: discord.Interaction, error):
    if isinstance(error, discord.app_commands.CheckFailure):
        await interaction.response.send_message("🚫 You don't have permission to use this command.", ephemeral=True)
    else:
        raise error

client.run(os.getenv('DISCORD_BOT_TOKEN'))