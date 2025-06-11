from discord import Interaction, Member, Object
from src.aclient import client
from src.db.db import get_user_collection
from src.trades.views import TradeView

GUILD = Object(id=955464847028531280)

@client.tree.command(name="trade", description="Trade a card with another player", guild=GUILD)
async def trade(interaction: Interaction, target: Member):
    if interaction.user.id == target.id:
        await interaction.response.send_message("❌ You can't trade with yourself.", ephemeral=True)
        return

    user_cards = await get_user_collection(interaction.user.id)
    target_cards = await get_user_collection(target.id)

    if not user_cards or not target_cards:
        await interaction.response.send_message("❌ Both players must own at least one card.", ephemeral=True)
        return

    view = TradeView(interaction.user.id, target.id, user_cards, target_cards)
    await interaction.response.send_message(
        f"{interaction.user.mention}, select a card from your collection and one from {target.mention}.",
        view=view,
        ephemeral=True
    )
