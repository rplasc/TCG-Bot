from discord import Interaction, Embed, Color, Object
from src.aclient import client
from src.database.db import (get_user_collection, get_cards_by_collection, get_card_ids_in_collection, 
                        get_user_owned_card_ids, get_missing_cards_in_collection,
                        get_collection_id, has_claimed_collection_reward, claim_collection_reward, give_coins,
                        update_xp_and_check_level)
from src.collections.views import CardPageView, build_single_card_embed

@client.tree.command(name="my_collection", description="View your card collection")
async def my_collection(interaction: Interaction):
    cards = await get_user_collection(interaction.user.id)
    if not cards:
        await interaction.response.send_message("🗃️ You don’t own any cards yet.", ephemeral=True)
        return

    index = 0
    embed = build_single_card_embed(interaction.user.name, cards[index], index, len(cards))
    view = CardPageView(interaction.user.id, cards, index)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

@client.tree.command(name="view_collection", description="View all cards in a specific collection")
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

@client.tree.command(name="collection_progress", description="See your progress for a specific collection")
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

@client.tree.command(name="my_missing_cards", description="View uncollected cards from a collection")
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
