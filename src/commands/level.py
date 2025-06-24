from discord import Interaction, Color, Embed, Object
from src.aclient import client
from src.database.db import register_user, get_xp, calculate_level

GUILD = Object(id=955464847028531280)

@client.tree.command(name="level", description="View your level and XP", guild=GUILD)
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
    await interaction.response.send_message(embed=embed)
