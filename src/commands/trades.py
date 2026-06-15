from discord import Interaction, Member, Embed, Color
from src.aclient import client
from src.database.db import get_user_collection
from src.trades.views import TradeView
from src.utils.ui import error_embed

@client.tree.command(name="trade", description="Trade a card with another player")
async def trade(interaction: Interaction, target: Member):
    if interaction.user.id == target.id:
        await interaction.response.send_message(
            embed=error_embed("You can't trade with yourself."), ephemeral=True)
        return

    user_cards = await get_user_collection(interaction.user.id)
    target_cards = await get_user_collection(target.id)

    if not user_cards or not target_cards:
        await interaction.response.send_message(
            embed=error_embed("Both players must own at least one card."), ephemeral=True)
        return

    embed = Embed(
        title="🔁 New Trade",
        description=(
            f"Trading with {target.mention}.\n\n"
            "1. Pick a card from **your** collection.\n"
            "2. Pick the card you want from **theirs**.\n"
            "3. Optionally add coins, then **Submit Trade**."
        ),
        color=Color.blurple()
    )
    view = TradeView(interaction.user.id, target.id, user_cards, target_cards)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
