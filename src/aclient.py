from dotenv import load_dotenv
from discord import Client, Intents, app_commands, Activity, ActivityType

load_dotenv()  # take environment variables from .env.

# Creates client with Discord
class aclient(Client):
    def __init__(self) -> None:
        intents = Intents.default()
        intents.message_content = True
        super().__init__(intents = intents)
        self.tree = app_commands.CommandTree(self)
        self.current_channel = None
        self.activity = Activity(type = ActivityType.watching,name='the casino')
        self.isPrivate = False       
    
client = aclient()