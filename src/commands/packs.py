from discord import Embed, Interaction, Color, Object
from src.aclient import client
from src.shop.logic import (RARITY_EMOJIS, draw_card, RARITY_XP, RARITY_POOL_DAILY, DUPLICATE_REWARDS)
from src.shop.views import ShopTypeView
from src.database.db import (register_user, update_daily_claim, get_last_daily_claim, add_to_user_collection, user_owns_card,
                        give_coins, update_xp_and_check_level)
from src.utils.time import get_time_until_next_daily

GUILD = Object(id=955464847028531280)

@client.tree.command(name="shop", description="View all available shops", guild=GUILD)
async def shop(interaction: Interaction):
    await interaction.response.send_message(
        "🛍️ Choose the type of shop you'd like to visit:",
        view=ShopTypeView(interaction.user.id),
        ephemeral=True
    )

@client.tree.command(name="daily", description="Claim your daily free pack", guild=GUILD)
async def daily(interaction: Interaction):
    user_id = interaction.user.id
    username = interaction.user.name
    await register_user(user_id, username)

    last_claimed = await get_last_daily_claim(user_id)
    if last_claimed:
        cooldown = get_time_until_next_daily(last_claimed)
        if cooldown:
            await interaction.response.send_message(
                f"⏳ You’ve already claimed your daily card.\nTry again in **{cooldown}**.",
                ephemeral=True
            )
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
