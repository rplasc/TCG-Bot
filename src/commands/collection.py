from discord import Interaction, Embed, Color, Object
from src.aclient import client
from src.db.db import get_user_collection

GUILD = Object(id=955464847028531280)

@client.tree.command(name="mycollection", description="View your card collection", guild=GUILD)
async def my_collection(interaction: Interaction):
    cards = await get_user_collection(interaction.user.id)
    if not cards:
        await interaction.response.send_message("You don’t own any cards yet.")
        return

    embed = Embed(title=f"{interaction.user.name}'s Collection", color=Color.blue())
    for card in cards:
        embed.add_field(
            name=f"{card[1]} ({card[2]})",
            value=f"Qty: {card[4]}",
            inline=False
        )
    await interaction.response.send_message(embed=embed)
