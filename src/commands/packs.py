from discord import Embed, Interaction, Color
from src.aclient import client
from src.shop.logic import RARITY_EMOJIS, draw_card, RARITY_XP, RARITY_POOL_DAILY, DUPLICATE_REWARDS
from src.shop.views import ShopTypeView
from src.database.db import (register_user,add_to_user_collection, user_owns_card, give_coins, 
                             update_xp_and_check_level, can_claim_daily_reward, claim_daily_reward_with_streak
                             )
from src.utils.time import get_time_until_next_daily

@client.tree.command(name="shop", description="View all available shops")
async def shop(interaction: Interaction):
    await interaction.response.send_message(
        "🛍️ Choose the type of shop you'd like to visit:",
        view=ShopTypeView(interaction.user.id),
        ephemeral=True
    )

@client.tree.command(name="daily", description="Claim your daily free pack")
async def daily(interaction: Interaction):
    user_id = interaction.user.id
    username = interaction.user.name
    await register_user(user_id, username)

    can_claim, streak_info = await can_claim_daily_reward(user_id)
    
    if not can_claim:
        # Calculate time until next claim
        if streak_info['last_claimed']:
            cooldown = get_time_until_next_daily(streak_info['last_claimed'])
            if cooldown:
                # Show current streak info even when can't claim
                embed = Embed(
                    title="⏳ Daily Pack Already Claimed",
                    description=f"Try again in **{cooldown}**",
                    color=Color.orange()
                )
                embed.add_field(
                    name="🔥 Current Streak",
                    value=f"{streak_info['current_streak']} days",
                    inline=True
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
    try:
        streak_result = await claim_daily_reward_with_streak(user_id)
        
        if not streak_result['success']:
            await interaction.response.send_message(
                f"❌ {streak_result['message']}", 
                ephemeral=True
            )
            return

        # Draw the daily card
        card = await draw_card(pool=RARITY_POOL_DAILY)
        if not card:
            await interaction.response.send_message("❌ No cards available to draw.", ephemeral=True)
            return

        card_id = card[0]
        rarity = card[2].lower()
        emoji = RARITY_EMOJIS.get(rarity, "")
        total_xp = RARITY_XP.get(rarity, 0)
        coin_reward = DUPLICATE_REWARDS.get(rarity, 0)

        # Handle card ownership and duplicates
        if await user_owns_card(user_id, card_id):
            await give_coins(user_id, coin_reward)
            owned_text = f"(dupe) → +{coin_reward} coins"
        else:
            await add_to_user_collection(user_id, card_id)
            owned_text = ""

        # Add the card XP to the streak XP bonus
        new_level, level_coins = await update_xp_and_check_level(user_id, total_xp)

        # Determine embed color and special effects
        legendary_pulled = (rarity == "legendary")
        streak_milestone = streak_result['current_streak'] % 7 == 0 and streak_result['current_streak'] > 0
        
        if legendary_pulled:
            embed_color = Color.gold()
        elif streak_milestone:
            embed_color = Color.purple()
        else:
            embed_color = Color.blue()

        # Create the main embed
        title = "🎁 Daily Pack Claimed!"
        description = "Come back tomorrow for another!"
        
        # Add special messages
        if legendary_pulled:
            description += "\n🌟 **LEGENDARY PULL!** 🌟"
        if streak_result['streak_broken']:
            description += "\n💔 Your streak was broken, but you're starting fresh!"
        elif streak_result['current_streak'] >= 7:
            description += f"\n🔥 **{streak_result['current_streak']}-day streak!** Keep it up!"

        embed = Embed(title=title, description=description, color=embed_color)

        # Card information
        embed.add_field(
            name=f"{emoji} {card[1]} [{card[2]}]",
            value=f"ATK: {card[3]} | DEF: {card[4]} | HP: {card[5]}\n{owned_text}",
            inline=False
        )

        # Streak information
        streak_text = f"🔥 **{streak_result['current_streak']} days**"
        
        embed.add_field(
            name="Current Streak",
            value=streak_text,
            inline=True
        )
        
        embed.add_field(name="\u200b", value="\u200b", inline=True)

        # Rewards breakdown
        rewards_text = f"💰 **{streak_result['total_coins']} coins**"
        if streak_result['bonus_coins'] > 0:
            rewards_text += f"\n   ├ Base: {streak_result['base_coins']}"
            rewards_text += f"\n   └ Streak: +{streak_result['bonus_coins']}"
        
        rewards_text += f"\n + **{total_xp} XP**"
        
        embed.add_field(
            name="💎 Daily Rewards",
            value=rewards_text,
            inline=False
        )

        # Level up notification
        if new_level:
            embed.add_field(
                name="🆙 Level Up!", 
                value=f"You reached Level {new_level} and earned +{level_coins} coins!", 
                inline=False
            )

        # Milestone celebrations
        current_streak = streak_result['current_streak']
        if current_streak % 30 == 0 and current_streak > 0:
            embed.add_field(
                name="🌟 30-Day Milestone!", 
                value="Congrats, but touch some grass pls!", 
                inline=False
            )
        elif current_streak % 7 == 0 and current_streak > 0:
            embed.add_field(
                name="✨ Weekly Milestone!", 
                value="A full week of daily claims! Good job!", 
                inline=False
            )

        # Set card image
        image_url = card[6]
        if isinstance(image_url, str) and image_url.startswith("http"):
            embed.set_image(url=image_url)

        # Special thumbnails
        if legendary_pulled:
            embed.set_thumbnail(url="https://media.discordapp.net/attachments/991418891832148060/1118801858090237992/shtlick.gif?ex=6842966d&is=684144ed&hm=c9a5ac854920e3c814c84cd3ff423e00af82d736c9f650f4306497d8d0e3316b&")
        elif current_streak >= 30:
            # TODO: Add streak gif
            pass

        await interaction.response.send_message(embed=embed)

    except Exception as e:
        await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)
