from discord import Interaction, Embed, Color, app_commands, ui, ButtonStyle
from src.aclient import client
from src.database.db import (get_user_collection, get_cards_by_collection, get_card_ids_in_collection,
                        get_user_owned_card_ids, get_missing_cards_in_collection,
                        get_collection_id, has_claimed_collection_reward, claim_collection_reward,
                        update_xp_and_check_level, get_all_collection_names)
from src.economy.service import award_coins
from src.economy.config import COLLECTION_REWARD
from src.collections.views import CardPageView, build_single_card_embed
from src.shop.logic import RARITY_EMOJIS
from src.utils.ui import FieldPaginator, progress_bar, error_embed


async def collection_autocomplete(interaction: Interaction, current: str):
    names = await get_all_collection_names()
    current = current.lower()
    return [
        app_commands.Choice(name=n, value=n)
        for n in names if current in n.lower()
    ][:25]


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
@app_commands.autocomplete(name=collection_autocomplete)
async def view_collection(interaction: Interaction, name: str):
    cards = await get_cards_by_collection(name)
    if not cards:
        await interaction.response.send_message(
            embed=error_embed(f"No cards found in the collection **{name}**.", title="Not found"),
            ephemeral=True
        )
        return

    entries = [
        (
            f"{RARITY_EMOJIS.get(str(card[2]).lower(), '')} {card[1]} [#{card[0]}]",
            f"Rarity: {str(card[2]).title()} • ATK: {card[3]} | DEF: {card[4]} | HP: {card[5]}"
        )
        for card in cards
    ]
    view = FieldPaginator(
        user_id=interaction.user.id,
        title=f"📚 Collection: {name.title()}",
        entries=entries,
        color=Color.green(),
        footer_suffix=f"{len(cards)} cards",
    )
    await interaction.response.send_message(embed=view.get_embed(), view=view)

@client.tree.command(name="collection_progress", description="See your progress for a specific collection")
@app_commands.autocomplete(collection=collection_autocomplete)
async def collection_progress(interaction: Interaction, collection: str):
    user_id = interaction.user.id

    all_ids = await get_card_ids_in_collection(collection)
    if not all_ids:
        await interaction.response.send_message(
            embed=error_embed(f"No cards found in the collection **{collection}**.", title="Not found"),
            ephemeral=True
        )
        return

    owned_ids = await get_user_owned_card_ids(user_id)
    owned_in_collection = set(all_ids) & set(owned_ids)

    total = len(all_ids)
    owned = len(owned_in_collection)
    percent = round((owned / total) * 100)

    collection_id = await get_collection_id(collection)

    embed = Embed(
        title=f"📊 Collection Progress: {collection.title()}",
        description=f"**{owned}/{total}** cards owned — **{percent}% complete**",
        color=Color.green()
    )
    embed.add_field(name="Progress", value=progress_bar(owned, total), inline=False)

    missing_view = None
    if owned == total:
        if not await has_claimed_collection_reward(user_id, collection_id):
            await claim_collection_reward(user_id, collection_id)
            await award_coins(user_id, 200, COLLECTION_REWARD, {"collection": collection, "collection_id": collection_id})
            new_level, coins_awarded = await update_xp_and_check_level(user_id, 250)
            embed.add_field(name="🎁 Reward", value="You earned **200 coins** and **250 XP**!", inline=False)
            if new_level:
                embed.add_field(name="🆙 Level Up!", value=f"You reached Level {new_level} and earned +{coins_awarded} coins!", inline=False)
        else:
            embed.add_field(name="🎁 Reward", value="You've already claimed the reward for this collection.", inline=False)
    else:
        # Offer the uncollected-cards list via a button instead of a separate command.
        missing_view = MissingCardsView(user_id, collection)

    await interaction.response.send_message(embed=embed, view=missing_view)


def build_missing_cards_view(user_id: int, collection: str, missing: list[str]) -> FieldPaginator:
    """Paginated list of a collection's uncollected card names."""
    chunk = 20
    entries = [
        (
            f"Cards {i + 1}–{min(i + chunk, len(missing))}",
            "\n".join(f"• {name}" for name in missing[i:i + chunk]),
        )
        for i in range(0, len(missing), chunk)
    ]
    return FieldPaginator(
        user_id=user_id,
        title=f"📋 Missing Cards in {collection.title()}",
        entries=entries,
        color=Color.red(),
        per_page=1,
        footer_suffix=f"{len(missing)} missing",
    )


class MissingCardsView(ui.View):
    """A single button on /collection_progress that reveals the uncollected cards."""

    def __init__(self, user_id: int, collection: str):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.collection = collection

    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your menu.", ephemeral=True)
            return False
        return True

    @ui.button(label="📋 Show missing cards", style=ButtonStyle.secondary)
    async def show_missing(self, interaction: Interaction, button: ui.Button):
        missing = await get_missing_cards_in_collection(self.user_id, self.collection)
        if not missing:
            await interaction.response.send_message(
                f"🎉 You own all cards in **{self.collection.title()}**!", ephemeral=True)
            return
        view = build_missing_cards_view(self.user_id, self.collection, missing)
        await interaction.response.send_message(embed=view.get_embed(), view=view, ephemeral=True)
