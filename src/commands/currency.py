from discord import Interaction, Object
from src.database.db import register_user, get_balance
from src.aclient import client

GUILD = Object(id=955464847028531280)

@client.tree.command(name="balance", description="Check your coin balance", guild=GUILD)
async def balance(interaction: Interaction):
    await register_user(interaction.user.id, interaction.user.name)
    coins = await get_balance(interaction.user.id)
    await interaction.response.send_message(f"💰 You have **{coins}** coins.", ephemeral=True)
