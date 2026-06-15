from discord import Interaction, Color, Embed, Member
from src.aclient import client
from src.database.db import (register_user, get_xp, calculate_level, get_rank_id, get_balance,
                             get_wins, get_rp, get_user_collection)
from src.utils.ranks import get_rank_display_name, calculate_rank_table
from src.utils.ui import progress_bar

@client.tree.command(name="level", description="View your level and XP")
async def level_command(interaction: Interaction):
    user_id = interaction.user.id
    await register_user(user_id, interaction.user.name)
    xp = await get_xp(user_id)
    level = calculate_level(xp)
    current_floor = int((level ** 2) * 100)
    next_xp = int(((level + 1) ** 2) * 100)
    xp_to_next = next_xp - xp
    earned = xp - current_floor
    span = next_xp - current_floor

    embed = Embed(title="📊 Level Progress", color=Color.purple())
    embed.add_field(name="Level", value=f"**{level}**", inline=True)
    embed.add_field(name="Total XP", value=f"{xp:,}", inline=True)
    embed.add_field(
        name=f"Progress to Level {level + 1}",
        value=f"{progress_bar(earned, span)}\n**{earned} / {span} XP** ({xp_to_next} to go)",
        inline=False
    )
    embed.set_footer(text="Earn XP from packs, daily claims, and battles.")
    await interaction.response.send_message(embed=embed, ephemeral=True)

@client.tree.command(name="rank", description="View your current rank.")
async def rank_command(interaction: Interaction):
    user_id = interaction.user.id
    await register_user(user_id, interaction.user.name)
    rank = await get_rank_id(user_id)
    rp = await get_rp(user_id)

    embed = Embed(
        title="🎖️ Current Rank",
        description=f"You are **{get_rank_display_name(rank)}**.",
        color=Color.gold()
    )

    rank_info = calculate_rank_table().get(rank)
    rp_to_next = rank_info["rp_to_next"] if rank_info else 0
    if rp_to_next > 0:
        embed.add_field(
            name="Rank Progress",
            value=f"{progress_bar(rp, rp_to_next)}\n**{rp} / {rp_to_next} RP** ({rp_to_next - rp} to next rank)",
            inline=False
        )
    else:
        # Max rank — no further progression.
        embed.add_field(name="Rank Points", value=f"{rp} RP (max rank reached)", inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)

@client.tree.command(name="balance", description="Check your coin balance")
async def balance(interaction: Interaction):
    await register_user(interaction.user.id, interaction.user.name)
    coins = await get_balance(interaction.user.id)
    embed = Embed(
        title="💰 Balance",
        description=f"You have **{coins:,}** coins.",
        color=Color.gold()
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

@client.tree.command(name="profile", description="View a user's current data.")
async def profile_command(interaction: Interaction, user: Member = None):
    if not user:
        user = interaction.user

    user_id = user.id
    await register_user(user_id, user.name)
    rank = await get_rank_id(user.id)
    xp = await get_xp(user_id)
    level = calculate_level(xp)
    wins = await get_wins(user_id)
    coins = await get_balance(user_id)
    card_count = len(await get_user_collection(user_id))

    embed = Embed(title=f"{user.display_name}'s Profile", color=Color.blue())
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.add_field(name="🎖️ Rank", value=f"{get_rank_display_name(rank)}", inline=True)
    embed.add_field(name="🏆 Wins", value=str(wins), inline=True)
    embed.add_field(name="📊 Level", value=str(level), inline=True)
    embed.add_field(name="💰 Balance", value=f"{coins:,} coins", inline=True)
    embed.add_field(name="🃏 Cards Owned", value=str(card_count), inline=True)

    await interaction.response.send_message(embed=embed)
