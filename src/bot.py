import os
import discord
from src.aclient import client
from src.commands import cards, general, packs, collection, codex

@client.event
async def on_ready():
    await client.tree.sync()

    GUILD = discord.Object(id=955464847028531280)
    await client.tree.sync(guild=GUILD)
    print(f'Logged in as {client.user.name}')

    commands = await client.tree.fetch_commands(guild=GUILD)
    print("Registered Commands:")
    for command in commands:
        print(f"- {command.name}")

client.run(os.getenv('DISCORD_BOT_TOKEN'))