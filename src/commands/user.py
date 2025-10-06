from discord import Interaction, Color, Embed, Object, Member
from src.aclient import client
from src.database.db import register_user, get_xp, calculate_level, get_rank_id, get_balance, get_wins, get_rp
from src.utils.ranks import get_rank_display_name

@client.tree.command(name="level", description="View your level and XP")
async def level_command(interaction: Interaction):
    user_id = interaction.user.id
    await register_user(user_id, interaction.user.name)
    xp = await get_xp(user_id)
    level = calculate_level(xp)
    next_xp = int(((level + 1) ** 2) * 100)
    xp_to_next = next_xp - xp

    embed = Embed(title="📊 Level Progress", color=Color.purple())
    embed.add_field(name="Level", value=str(level))
    embed.add_field(name="XP", value=f"{xp} / {next_xp} (need {xp_to_next} more)", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@client.tree.command(name="rank", description="View your current rank.")
async def rank_command(interaction: Interaction):
    user_id = interaction.user.id
    await register_user(user_id, interaction.user.name)
    rank = await get_rank_id(user_id)
    rp = await get_rp(user_id)

    embed = Embed(
        title="Current Rank",
        description=f"Your current rank is {get_rank_display_name(rank)}.",
        color=Color.gold()
    )
    embed.set_footer(text=f"Current RP:{rp}")

    await interaction.response.send_message(embed=embed, ephemeral=True)

@client.tree.command(name="balance", description="Check your coin balance")
async def balance(interaction: Interaction):
    await register_user(interaction.user.id, interaction.user.name)
    coins = await get_balance(interaction.user.id)
    await interaction.response.send_message(f"💰 You have **{coins}** coins.", ephemeral=True)

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

    embed = Embed(title=f"{user.name}'s Profile", color=Color.blue())
    embed.add_field(name="Current Rank", value=f"{get_rank_display_name(rank)}", inline=True)
    embed.add_field(name="wins", value=str(wins), inline=True)
    embed.add_field(name="Level", value=str(level), inline=False)
    embed.add_field(name="Balance", value=str(coins), inline=False)

    await interaction.response.send_message(embed=embed)