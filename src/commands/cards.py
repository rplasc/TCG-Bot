from discord import Interaction, Embed, Color, Attachment, Object
from src.db.db import add_card, get_card
from src.aclient import client

GUILD = Object(id=955464847028531280)

@client.tree.command(name="addcard", description="Add card to database", guild=GUILD)
async def add_card_command(interaction: Interaction, name: str, rarity: str, attack: int, defense: int, image: Attachment):
    await add_card(name, rarity, attack, defense, image.url)
    await interaction.response.send_message(f"Card '{name}' added to database!")

@client.tree.command(name="viewcard", description="View a card", guild=GUILD)
async def view_card_command(interaction: Interaction, card_id: int):
    card = await get_card(card_id)
    if card:
        embed = Embed(title=f"{card[1]} (#{card[0]})", color=Color.blue())
        embed.add_field(name="Rarity", value=card[2])
        embed.add_field(name="Attack", value=card[3])
        embed.add_field(name="Defense", value=card[4])
        embed.set_image(url=card[5])
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message("Card not found!")