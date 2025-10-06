from src.aclient import client
from discord import Interaction, Object
from src.casino.views import CasinoView

@client.tree.command(name="casino", description="Play gambling games")
async def casino(interaction: Interaction):
    await interaction.response.send_message(
        "🎰 Welcome to the Casino! Choose a game:",
        view=CasinoView(interaction.user.id),
        ephemeral=True
    )
