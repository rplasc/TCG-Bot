from discord import Interaction, Object
from src.aclient import client
from src.db.db import init_db

GUILD = Object(id=955464847028531280)

@client.tree.command(name="initdb", description="Initialize database", guild=GUILD)
async def init_databse(interaction: Interaction):
    await init_db()
    await interaction.response.send_message("Database initialized.")