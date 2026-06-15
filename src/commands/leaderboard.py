from discord import Interaction, Embed, Color
from src.aclient import client
from src.database.db import get_top_users_by_rank, get_user_rank_position, register_user
from src.utils.ranks import get_rank_display_name

MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}

@client.tree.command(name="leaderboard", description="View the Rank leaderboard")
async def leaderboard(interaction: Interaction):
    await register_user(interaction.user.id, interaction.user.name)
    top_users = await get_top_users_by_rank(10)

    if not top_users:
        await interaction.response.send_message("🏁 No users have earned ranks yet.")
        return

    lines = []
    for i, (name, rank, wins) in enumerate(top_users, start=1):
        prefix = MEDALS.get(i, f"**{i}.**")
        lines.append(f"{prefix} {name} — {get_rank_display_name(rank)} • {wins} wins")

    embed = Embed(
        title="🏆 Ranking Leaderboard",
        description="\n".join(lines),
        color=Color.gold()
    )

    position = await get_user_rank_position(interaction.user.id)
    if position:
        place, rank, wins = position
        embed.set_footer(text=f"Your position: #{place} • {get_rank_display_name(rank)} • {wins} wins")

    await interaction.response.send_message(embed=embed)
