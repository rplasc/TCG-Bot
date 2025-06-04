import random
from discord import Embed, Interaction, Color, Object
from src.aclient import client
from src.db.db import register_user, add_to_user_collection, get_card
import aiosqlite

GUILD = Object(id=955464847028531280)

RARITY_POOL = {
    "common": 70,
    "rare": 20,
    "epic": 8,
    "legendary": 2,
}

async def draw_card():
    # Choose a rarity
    rarities = list(RARITY_POOL.keys())
    weights = list(RARITY_POOL.values())
    chosen_rarity = random.choices(rarities, weights=weights)[0]

    async with aiosqlite.connect("data/cards.db") as db:
        cursor = await db.execute("SELECT * FROM cards WHERE rarity = ?", (chosen_rarity,))
        cards = await cursor.fetchall()
        if not cards:
            return None
        return random.choice(cards)

@client.tree.command(name="openpack", description="Open a card pack!", guild=GUILD)
async def open_pack(interaction: Interaction):
    await register_user(interaction.user.id, interaction.user.name)

    pulled_cards = []
    for _ in range(5):  # 5 cards per pack
        card = await draw_card()
        if card:
            await add_to_user_collection(interaction.user.id, card[0])
            pulled_cards.append(card)

    embed = Embed(title="📦 You opened a pack!", color=Color.gold())
    for card in pulled_cards:
        embed.add_field(name=f"{card[1]} [{card[2]}]", value=f"ATK: {card[3]} | DEF: {card[4]}", inline=False)
        embed.set_image(url=card[5])  # shows last card's image

    await interaction.response.send_message(embed=embed)
