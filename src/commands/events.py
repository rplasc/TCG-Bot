from discord import Interaction, Embed, Color

from src.aclient import client
from src.events.service import active_events, format_effects


def build_events_embed(events) -> Embed:
    if not events:
        return Embed(
            title="🎉 Active Events",
            description="No events are active right now. Check back soon!",
            color=Color.greyple(),
        )
    embed = Embed(title="🎉 Active Events", color=Color.purple())
    for e in events:
        embed.add_field(
            name=f"{e.emoji} {e.name} ({e.cadence})",
            value=f"{e.description}\n*{format_effects(e)}*",
            inline=False,
        )
    return embed


@client.tree.command(name="event", description="Show the currently active events")
async def event(interaction: Interaction):
    await interaction.response.send_message(
        embed=build_events_embed(active_events()), ephemeral=True
    )
