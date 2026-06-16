import random
import aiosqlite
from discord import Embed, Color, Interaction
from src.database.db import (
    register_user, add_to_user_collection, can_afford,
    user_owns_card, update_xp_and_check_level, get_card
)
from src.economy.service import award_coins, spend_coins
from src.economy.config import SHOP_PACK_PURCHASE, SHOP_CARD_PURCHASE, SHOP_DUPLICATE_REFUND

RARITY_POOL = {
    "common": 70,
    "rare": 20,
    "epic": 9,
    "legendary": 1,
}

RARITY_POOL_DAILY = {
    "common": 51,
    "rare": 31,
    "epic": 16,
    "legendary": 2
}

RARITY_POOL_BOOSTED = {
    "common": 50,
    "rare": 30,
    "epic": 15,
    "legendary": 5
}

RARITY_XP = {
    "common": 10,
    "rare": 30,
    "epic": 70,
    "legendary": 100
}

RARITY_EMOJIS = {
    "common": "🟩",
    "rare": "🟦",
    "epic": "🟪",
    "legendary": "🟨"
}

DUPLICATE_REWARDS = {
    "common": 10,
    "rare": 15,
    "epic": 30,
    "legendary": 50
}

CARD_SHOP_PRICES = {
    "common": 30,
    "rare": 50,
    "epic": 100,
    "legendary": 200
}
SHOP_PACKS = {
    "single": {"label": "Single Pack", "cards": 1, "cost": 50, "pool": RARITY_POOL},
    "triple": {"label": "Triple Pack", "cards": 3, "cost": 100, "pool": RARITY_POOL},
    "quintuple": {"label": "Quintuple Pack", "cards": 5, "cost": 200, "pool": RARITY_POOL},
    "boosted": {"label": "Boosted Pack", "cards": 3, "cost": 150, "pool": RARITY_POOL_BOOSTED},
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

async def handle_shop_purchase(interaction: Interaction, user_id: int, pack: dict):
    username = interaction.user.name
    await register_user(user_id, username)

    if not await can_afford(user_id, pack["cost"]):
        await interaction.response.send_message("❌ Not enough coins!", ephemeral=True)
        return

    await spend_coins(user_id, pack["cost"], SHOP_PACK_PURCHASE, {"pack": pack.get("label")})

    pulled_cards = []
    total_xp = 0
    legendary_pulled = False
    footer_notes = []

    for _ in range(pack["cards"]):
        card = await draw_card(pool=pack["pool"])
        if not card:
            continue
        card_id = card[0]
        rarity = card[2].lower()
        name = card[1]
        xp_reward = RARITY_XP.get(rarity, 0)
        coins = DUPLICATE_REWARDS.get(rarity, 0)
        emoji = RARITY_EMOJIS.get(rarity, "")

        if await user_owns_card(user_id, card_id):
            await award_coins(user_id, coins, SHOP_DUPLICATE_REFUND, {"card_id": card_id, "rarity": rarity})
            total_xp += xp_reward
            footer_notes.append(f"{emoji} {name} (dupe) → +{coins} coins, +{xp_reward} XP")
        else:
            await add_to_user_collection(user_id, card_id)
            total_xp += xp_reward
            pulled_cards.append(card)
            footer_notes.append(f"{emoji} {name} → +{xp_reward} XP")

        if rarity == "legendary":
            legendary_pulled = True

    embed_color = Color.gold() if legendary_pulled else Color.dark_teal()
    embed = Embed(title=f"🎒 {pack['label']} Opened!", color=embed_color)

    for card in pulled_cards:
        emoji = RARITY_EMOJIS.get(card[2].lower(), "")
        embed.add_field(name=f"{emoji} {card[1]} [{card[2]}]", value=f"ATK: {card[3]} | DEF: {card[4]} | HP: {card[5]}", inline=False)
        image_url = card[6]
        if isinstance(image_url, str) and image_url.startswith("http"):
            embed.set_image(url=image_url)

    new_level, coins_awarded = await update_xp_and_check_level(user_id, total_xp)
    if new_level:
        embed.add_field(name="🆙 Level Up!", value=f"You reached Level {new_level} and earned +{coins_awarded} coins!", inline=False)

    if legendary_pulled:
        embed.set_thumbnail(url="https://media.discordapp.net/attachments/991418891832148060/1118801858090237992/shtlick.gif?ex=6842966d&is=684144ed&hm=c9a5ac854920e3c814c84cd3ff423e00af82d736c9f650f4306497d8d0e3316b&")

    footer_notes.append(f"Total XP: {total_xp}")
    embed.set_footer(text=" | ".join(footer_notes[-2:]))

    await interaction.response.send_message(embed=embed, ephemeral=True)

async def handle_card_purchase(interaction: Interaction, card_id: int):
    user_id = interaction.user.id
    await register_user(user_id, interaction.user.name)

    card = await get_card(card_id)
    if not card:
        await interaction.response.send_message("❌ That card is no longer available.", ephemeral=True)
        return

    rarity = card[2].lower()
    price = CARD_SHOP_PRICES.get(rarity, 50)

    if not await can_afford(user_id, price):
        await interaction.response.send_message("❌ Not enough coins!", ephemeral=True)
        return

    if await user_owns_card(user_id, card_id):
        await interaction.response.send_message("⚠️ You already own this card!", ephemeral=True)
        return

    await spend_coins(user_id, price, SHOP_CARD_PURCHASE, {"card_id": card_id, "rarity": rarity})
    await add_to_user_collection(user_id, card_id)
    rarity = card[2].lower()
    xp_reward = RARITY_XP.get(rarity, 0)

    new_level, coins_awarded = await update_xp_and_check_level(user_id, xp_reward)

    await interaction.response.send_message(f"✅ Purchased **{card[1]}** for {price} coins!", ephemeral=True)
    return card, xp_reward, new_level, coins_awarded
