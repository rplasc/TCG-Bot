from discord import Interaction, Embed, Color, Object
from src.aclient import client
from src.db.db import get_user_collection, create_collection, get_cards_by_collection, delete_collection_by_name, get_card_ids_in_collection, get_user_owned_card_ids, get_missing_cards_in_collection, get_collection_id, has_claimed_collection_reward, claim_collection_reward, give_coins, update_xp_and_check_level
from src.utils.permissions import has_role
from src.utils.confirmation import ConfirmActionView

GUILD = Object(id=955464847028531280)

@client.tree.command(name="my_collection", description="View your card collection", guild=GUILD)
async def my_collection(interaction: Interaction):
    cards = await get_user_collection(interaction.user.id)
    if not cards:
        await interaction.response.send_message("🗃️ You don’t own any cards yet.")
        return

    embed = Embed(
        title=f"🗂️ {interaction.user.name}'s Card Collection",
        description=f"Total unique cards: {len(cards)}",
        color=Color.teal()
    )

    for card in cards:
        if len(card) >= 7:
            name = card[1]
            rarity = card[2]
            atk = card[3]
            defense = card[4]
            hp = card[5]

            embed.add_field(
                name=f"🃏 {name} ({rarity.title()})",
                value=f"**ATK:** {atk} | **DEF:** {defense} | **HP:** {hp}",
                inline=False
            )
        else:
            embed.add_field(name="⚠️ Invalid Card", value="This card entry is incomplete.", inline=False)

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

@client.tree.command(name="collection_progress", description="See your progress for a specific collection", guild=GUILD)
async def collection_progress(interaction: Interaction, collection: str):
    user_id = interaction.user.id
    username = interaction.user.name

    all_ids = await get_card_ids_in_collection(collection)
    if not all_ids:
        await interaction.response.send_message(f"❌ No cards found in the collection '{collection}'.", ephemeral=True)
        return

    owned_ids = await get_user_owned_card_ids(user_id)
    owned_in_collection = set(all_ids) & set(owned_ids)

    total = len(all_ids)
    owned = len(owned_in_collection)
    percent = round((owned / total) * 100)

    collection_id = await get_collection_id(collection)

    if owned == total:
        if not await has_claimed_collection_reward(user_id, collection_id):
            await claim_collection_reward(user_id, collection_id)
            await give_coins(user_id, 200)
            new_level, coins_awarded = await update_xp_and_check_level(user_id, 250)
            if new_level:
                embed.add_field(name="🆙 Level Up!", value=f"You reached Level {new_level} and earned +{coins_awarded} coins!", inline=False)

            embed.add_field(name="🎁 Reward", value="You earned 200 coins and 250 XP!", inline=False)
        else:
            embed.add_field(name="🎁", value="You've already claimed the reward for this collection.", inline=False)

    bar_segments = 20
    filled = int(bar_segments * (owned / total))
    progress_bar = "🟩" * filled + "⬜" * (bar_segments - filled)

    embed = Embed(
        title=f"📊 Collection Progress: {collection.title()}",
        description=f"**{owned}/{total}** cards owned — **{percent}% complete**",
        color=Color.green()
    )
    embed.add_field(name="Progress", value=progress_bar, inline=False)
    await interaction.response.send_message(embed=embed)

@client.tree.command(name="my_missing_cards", description="View uncollected cards from a collection", guild=GUILD)
async def my_missing_cards(interaction: Interaction, collection: str):
    user_id = interaction.user.id
    missing = await get_missing_cards_in_collection(user_id, collection)

    if not missing:
        await interaction.response.send_message(f"🎉 You own all cards in '{collection.title()}'!", ephemeral=True)
        return

    description = "\n".join(f"• {name}" for name in missing)
    embed = Embed(
        title=f"📋 Missing Cards in {collection.title()}",
        description=description[:4000],
        color=Color.red()
    )
    await interaction.response.send_message(embed=embed)
