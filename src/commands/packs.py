import random
from discord import Embed, Interaction, Color, Object
from src.aclient import client
from src.db.db import register_user, add_to_user_collection, can_afford, deduct_coins, has_claimed_today, update_daily_claim, give_coins, user_owns_card, update_xp_and_check_level
import aiosqlite

GUILD = Object(id=955464847028531280)

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

RARITY_XP = {
    "common": 5,
    "rare": 20,
    "epic": 35,
    "legendary": 50
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

@client.tree.command(name="open_pack", description="Open a card pack for 50 coins.", guild=GUILD)
async def open_pack(interaction: Interaction):
    user_id = interaction.user.id
    username = interaction.user.name
    await register_user(user_id, username)

    PACK_COST = 50
    if not await can_afford(user_id, PACK_COST):
        await interaction.response.send_message("❌ You don't have enough coins to buy a pack.", ephemeral=True)
        return

    await deduct_coins(user_id, PACK_COST)

    pulled_cards = []
    footer_notes = []
    total_xp = 0

    legendary_pulled = False

    for _ in range(3):
        card = await draw_card()
        if not card:
            continue

        card_id = card[0]
        name = card[1]
        rarity = card[2].lower()
        xp_reward = RARITY_XP.get(rarity, 0)
        emoji = RARITY_EMOJIS.get(rarity, "")
        coin_reward = DUPLICATE_REWARDS.get(rarity, 0)

        if rarity == "legendary":
            legendary_pulled = True

        if await user_owns_card(user_id, card_id):
            await give_coins(user_id, coin_reward)
            total_xp += xp_reward
            footer_notes.append(f"{emoji} {name} (dupe) → +{coin_reward} coins, +{xp_reward} XP")
        else:
            await add_to_user_collection(user_id, card_id)
            total_xp += xp_reward
            pulled_cards.append(card)
            footer_notes.append(f"{emoji} {name} → +{xp_reward} XP")

    embed_color = Color.gold() if legendary_pulled else Color.dark_blue()
    embed = Embed(title="📦 You bought a pack!", description=f"Cost: {PACK_COST} coins", color=embed_color)

    if legendary_pulled:
        embed.title = "🌟 LEGENDARY PULL! 🌟"
        embed.description += "\n🎉 You pulled a legendary card!"

    for card in pulled_cards:
        emoji = RARITY_EMOJIS.get(card[2].lower(), "")
        embed.add_field(
            name=f"{emoji} {card[1]} [{card[2]}]",
            value=f"ATK: {card[3]} | DEF: {card[4]} | HP: {card[5]}",
            inline=False
        )
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
    emoji = RARITY_EMOJIS.get(rarity, "")
    xp_reward = RARITY_XP.get(rarity, 0)
    coin_reward = DUPLICATE_REWARDS.get(rarity, 0)

    if await user_owns_card(user_id, card_id):
        await give_coins(user_id, coin_reward)
        owned_text = f"(dupe) → +{coin_reward} coins"
    else:
        await add_to_user_collection(user_id, card_id)
        owned_text = ""

    new_level, coins_awarded = await update_xp_and_check_level(user_id, xp_reward)

    legendary_pulled = (rarity == "legendary")
    embed_color = Color.gold() if legendary_pulled else Color.blue()
    embed = Embed(
        title="🎁 Daily Card Claimed!",
        description="Come back tomorrow for another." + ("\n🌟 You pulled a legendary! 🌟" if legendary_pulled else ""),
        color=embed_color
    )
    embed.add_field(
        name=f"{emoji} {card[1]} [{card[2]}]",
        value=f"ATK: {card[3]} | DEF: {card[4]} | HP: {card[5]}\n{owned_text}",
        inline=False
    )
    image_url = card[6]
    if isinstance(image_url, str) and image_url.startswith("http"):
        embed.set_image(url=image_url)
    if new_level:
        embed.add_field(name="🆙 Level Up!", value=f"You reached Level {new_level} and earned +{coins_awarded} coins!", inline=False)
    if legendary_pulled:
        embed.set_thumbnail(url="https://media.discordapp.net/attachments/991418891832148060/1118801858090237992/shtlick.gif?ex=6842966d&is=684144ed&hm=c9a5ac854920e3c814c84cd3ff423e00af82d736c9f650f4306497d8d0e3316b&")
    embed.set_footer(text=f"+{xp_reward} XP earned")
    await interaction.response.send_message(embed=embed)
