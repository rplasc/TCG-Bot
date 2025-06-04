from discord import Interaction, Embed, Color, Attachment, Object
from src.db.db import add_card, get_card_by_name
from src.aclient import client

GUILD = Object(id=955464847028531280)

@client.tree.command(name="add_card", description="Add card to database", guild=GUILD)
async def add_card_command(
    interaction: Interaction,
    name: str,
    rarity: str,
    attack: int,
    defense: int,
    image: Attachment,
    collection: str = None
):
    try:
        await add_card(name, rarity, attack, defense, image.url, collection_name=collection)
        await interaction.response.send_message(f"Card '{name}' added to collection '{collection or 'Default Collection'}'.")
    except ValueError as e:
        await interaction.response.send_message(str(e))

@client.tree.command(name="view_card", description="View a card by name", guild=GUILD)
async def view_card_command(interaction: Interaction, name: str):
    card = await get_card_by_name(name)
    if card:
        embed = Embed(title=f"{card[1]} (#{card[0]})", color=Color.blue())
        embed.add_field(name="Rarity", value=card[2])
        embed.add_field(name="Attack", value=card[3])
        embed.add_field(name="Defense", value=card[4])
        embed.set_image(url=card[5])
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message("Card not found.")
