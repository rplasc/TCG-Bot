from discord import Interaction, Color, Embed, Member
from src.aclient import client
from src.database.db import (register_user, get_xp, calculate_level, get_rank_id, get_balance,
                             get_wins, get_rp, get_user_collection)
from src.utils.ranks import get_rank_display_name, calculate_rank_table
from src.utils.ui import progress_bar


@client.tree.command(name="profile", description="View a player's rank, level, balance and progress.")
async def profile_command(interaction: Interaction, user: Member = None):
    if not user:
        user = interaction.user

    user_id = user.id
    await register_user(user_id, user.name)
    rank = await get_rank_id(user_id)
    rp = await get_rp(user_id)
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

    # Level/XP progress to the next level.
    current_floor = int((level ** 2) * 100)
    next_xp = int(((level + 1) ** 2) * 100)
    earned = xp - current_floor
    span = next_xp - current_floor
    embed.add_field(
        name=f"📈 XP — Level {level} → {level + 1}",
        value=f"{progress_bar(earned, span)}\n**{earned} / {span} XP** ({next_xp - xp} to go)",
        inline=False,
    )

    # Rank/RP progress to the next rank (or max-rank note).
    rank_info = calculate_rank_table().get(rank)
    rp_to_next = rank_info["rp_to_next"] if rank_info else 0
    if rp_to_next > 0:
        embed.add_field(
            name="🎖️ RP — Rank Progress",
            value=f"{progress_bar(rp, rp_to_next)}\n**{rp} / {rp_to_next} RP** ({rp_to_next - rp} to next rank)",
            inline=False,
        )
    else:
        embed.add_field(name="🎖️ RP — Rank Progress", value=f"{rp} RP (max rank reached)", inline=False)

    await interaction.response.send_message(embed=embed)
