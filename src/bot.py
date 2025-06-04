import os
import discord
from discord import Interaction, app_commands
from src.aclient import client

@client.event
async def on_ready():
    await client.tree.sync()
    print(f'Logged in as {client.user.name}')

client.run(os.getenv('DISCORD_BOT_TOKEN'))