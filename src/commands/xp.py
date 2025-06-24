from discord import Interaction, Embed, Color, Object
from src.aclient import client
from src.database.db import register_user, get_xp, get_top_users_by_rank
from src.utils.ranks import get_rank_display_name

GUILD = Object(id=955464847028531280)

@client.tree.command(name="xp", description="Check your total XP", guild=GUILD)
async def xp(interaction: Interaction):
    await register_user(interaction.user.id, interaction.user.name)
    current_xp = await get_xp(interaction.user.id)
    await interaction.response.send_message(f"⭐ You have {current_xp} XP.")

@client.tree.command(name="leaderboard", description="View the Rank leaderboard", guild=GUILD)
async def leaderboard(interaction: Interaction):
    top_users = await get_top_users_by_rank(10)

    if not top_users:
        await interaction.response.send_message("🏁 No users have earned ranks yet.")
        return

    embed = Embed(title="🏆 Ranking Leaderboard", color=Color.gold())
    for i, (name, rank, wins) in enumerate(top_users, start=1):
        embed.add_field(name=f"{i}. {name}", value=f"Rank: {get_rank_display_name(rank)}, Wins: {wins} ", inline=False)

    await interaction.response.send_message(embed=embed)