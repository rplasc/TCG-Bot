import os
import discord
from src.aclient import client
from src.db.db import init_db, add_card, get_card

@client.event
async def on_ready():
    await client.tree.sync()
    print(f'Logged in as {client.user.name}')

@client.tree.command(name="initdb")
async def init_databse(interaction: discord.Interaction):
    await init_db()
    await interaction.response.send_message("Database initialized.")

@client.tree.command(name="addcard", description="Add card to database")
async def add_card_command(interaction: discord.Interaction, name: str, rarity: str, attack: int, defense: int, image: discord.Attachment):
    await add_card(name, rarity, attack, defense, image.url)
    await interaction.response.send_message(f"Card '{name}' added to database!")

@client.tree.command(name="viewcard", description="View a card")
async def view_card_command(interaction: discord.Interaction, card_id: int):
    card = await get_card(card_id)
    if card:
        embed = discord.Embed(title=f"{card[1]} (#{card[0]})", color=discord.Color.blue())
        embed.add_field(name="Rarity", value=card[2])
        embed.add_field(name="Attack", value=card[3])
        embed.add_field(name="Defense", value=card[4])
        embed.set_image(url=card[5])
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message("Card not found!")

client.run(os.getenv('DISCORD_BOT_TOKEN'))