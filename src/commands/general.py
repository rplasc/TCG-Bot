from discord import Interaction, Object, Embed, Color
from src.aclient import client
from src.database.db import get_card_by_name

@client.tree.command(name="view_card", description="View a card by name")
async def view_card_command(interaction: Interaction, name: str):
    card = await get_card_by_name(name)
    if card:
        embed = Embed(title=f"{card[1]} (#{card[0]})", color=Color.blue())
        embed.add_field(name="Rarity", value=card[2])
        embed.add_field(name="Attack", value=card[3])
        embed.add_field(name="Defense", value=card[4])
        embed.add_field(name="HP", value=card[5])

        image_url = card[6]
        if isinstance(image_url, str) and image_url.startswith("http"):
            embed.set_image(url=image_url)

        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message("Card not found.")