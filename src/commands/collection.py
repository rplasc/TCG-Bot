from discord import Interaction, Embed, Color, Object
from src.aclient import client
from src.db.db import get_user_collection, create_collection, get_cards_by_collection, delete_collection_by_name
from src.utils.permissions import has_role
from src.utils.confirmation import ConfirmActionView

GUILD = Object(id=955464847028531280)

@client.tree.command(name="my_collection", description="View your card collection", guild=GUILD)
async def my_collection(interaction: Interaction):
    cards = await get_user_collection(interaction.user.id)
    if not cards:
        await interaction.response.send_message("You don’t own any cards yet.")
        return

    embed = Embed(title=f"{interaction.user.name}'s Collection", color=Color.blue())
    for card in cards:
        embed.add_field(
            name=f"{card[1]} ({card[2]})",
            value=f"Qty: {card[4]}",
            inline=False
        )
    await interaction.response.send_message(embed=embed)

@client.tree.command(name="create_collection", description="Create a new card collection", guild=GUILD)
@has_role("ChopperDevTeam")
async def createcollection(interaction: Interaction, name: str):
    await create_collection(name)
    await interaction.response.send_message(f"✅ Collection '{name}' created.")

@client.tree.command(name="view_collection", description="View all cards in a specific collection", guild=GUILD)
async def view_collection(interaction: Interaction, name: str):
    cards = await get_cards_by_collection(name)
    if not cards:
        await interaction.response.send_message("❌ No cards found in this collection.")
        return

    embed = Embed(title=f"📚 Collection: {name}", color=Color.green())
    for card in cards:
        embed.add_field(
            name=f"{card[1]} [#{card[0]}]",
            value=f"Rarity: {card[2]}, ATK: {card[3]}, DEF: {card[4]}",
            inline=False
        )
    await interaction.response.send_message(embed=embed)

@client.tree.command(name="delete_collection", description="Delete a collection by name", guild=GUILD)
@has_role("ChopperDevTeam")
async def delete_collection_command(interaction: Interaction, name: str):
    embed = Embed(
        title="⚠️ Confirm Collection Deletion",
        description=f"Are you sure you want to delete the collection `{name}`?",
        color=Color.red()
    )

    async def perform_deletion(_: Interaction):
        return await delete_collection_by_name(name)

    view = ConfirmActionView(
        user_id=interaction.user.id,
        action_fn=perform_deletion,
        success_message=f"✅ Collection '{name}' has been deleted.",
        failure_message=f"❌ Collection '{name}' was not found or couldn't be deleted.",
    )

    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)