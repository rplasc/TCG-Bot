import random
from discord import Embed, Interaction, Color, Object
from src.aclient import client
from src.db.db import register_user, add_to_user_collection, can_afford, deduct_coins, has_claimed_today, update_daily_claim, add_xp, give_coins, user_owns_card
import aiosqlite

GUILD = Object(id=955464847028531280)

RARITY_POOL = {
    "common": 70,
    "rare": 20,
    "epic": 8,
    "legendary": 2,
}

RARITY_POOL_DAILY = {
    "common": 50,
    "rare": 30,
    "epic": 15,
    "legendary": 5
}

RARITY_XP = {
    "common": 5,
    "rare": 20,
    "epic": 35,
    "legendary": 50
}

async def draw_card(pool=None):
    pool = pool or RARITY_POOL
    rarities = list(pool.keys())
    weights = list(pool.values())
    chosen_rarity = random.choices(rarities, weights=weights)[0]

    async with aiosqlite.connect("data/cards.db") as db:
        cursor = await db.execute("SELECT * FROM cards WHERE rarity = ?", (chosen_rarity,))
        cards = await cursor.fetchall()
        if not cards:
            print(f"[WARN] No cards found for rarity: {chosen_rarity}")
            return None
        return random.choice(cards)

@client.tree.command(name="open_pack", description="Open a card pack for 35 coins.", guild=GUILD)
async def open_pack(interaction: Interaction):
    user_id = interaction.user.id
    username = interaction.user.name
    await register_user(user_id, username)

    PACK_COST = 35
    if not await can_afford(user_id, PACK_COST):
        await interaction.response.send_message("❌ You don't have enough coins to buy a pack.", ephemeral=True)
        return

    await deduct_coins(user_id, PACK_COST)

    pulled_cards = []
    total_xp = 0
    duplicate_coins = 15  # or scale by rarity if you prefer

    for _ in range(1):
        card = await draw_card()
        if not card:
            continue

        card_id = card[0]
        rarity = card[2].lower()
        xp_reward = RARITY_XP.get(rarity, 0)

    if await user_owns_card(user_id, card_id):
        await give_coins(user_id, duplicate_coins)
        await add_xp(user_id, xp_reward)
        total_xp += xp_reward
        footer_note = f"Duplicate! +{duplicate_coins} coins, +{xp_reward} XP"
    else:
        await add_to_user_collection(user_id, card_id)
        total_xp += xp_reward
        pulled_cards.append(card)
        footer_note = f"+{xp_reward} XP earned"

    await add_xp(user_id, total_xp)

    embed = Embed(title="📦 You bought a pack!", description=f"Cost: {PACK_COST} coins", color=Color.gold())
    for card in pulled_cards:
        embed.add_field(name=f"{card[1]} [{card[2]}]", value=f"ATK: {card[3]} | DEF: {card[4]}", inline=False)
        image_url = card[6]
        if isinstance(image_url, str) and image_url.startswith("http"):
            embed.set_image(url=image_url)

    embed.set_footer(text=f"{footer_note} | Total XP: {total_xp}")
    await interaction.response.send_message(embed=embed)

@client.tree.command(name="daily", description="Claim your daily free pack", guild=GUILD)
async def daily(interaction: Interaction):
    user_id = interaction.user.id
    username = interaction.user.name
    await register_user(user_id, username)

    if await has_claimed_today(user_id):
        await interaction.response.send_message("⏱ You’ve already claimed your daily card. Try again tomorrow!", ephemeral=True)
        return

    await update_daily_claim(user_id)

    card = await draw_card(pool=RARITY_POOL_DAILY)
    if not card:
        await interaction.response.send_message("❌ No cards available to draw.", ephemeral=True)
        return

    card_id = card[0]
    rarity = card[2].lower()
    xp_reward = RARITY_XP.get(rarity, 0)

    if await user_owns_card(user_id, card_id):
        await give_coins(user_id, 15)
        await add_xp(user_id, xp_reward)
        footer = f"Duplicate! +15 coins, +{xp_reward} XP"
    else:
        await add_to_user_collection(user_id, card_id)
        await add_xp(user_id, xp_reward)
        footer = f"+{xp_reward} XP earned"

    embed = Embed(title="🎁 Daily Card Claimed!", description="Come back tomorrow for another.", color=Color.blue())
    embed.add_field(
        name=f"{card[1]} [{card[2]}]",
        value=f"ATK: {card[3]} | DEF: {card[4]} | HP: {card[5]}",
        inline=False
    )
    embed.set_image(url=card[6])
    embed.set_footer(text=f"+{xp_reward} XP earned")
    await interaction.response.send_message(embed=embed)
