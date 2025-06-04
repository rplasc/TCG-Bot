import discord
from dotenv import load_dotenv
from discord import Intents, app_commands

load_dotenv()  # take environment variables from .env.

# Creates client with Discord
class aclient(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents = intents)
        self.tree = app_commands.CommandTree(self)
        self.current_channel = None
        self.activity = discord.Activity(type = discord.ActivityType.custom,name='gambling')
        self.isPrivate = False       
    
client = aclient()