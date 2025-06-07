from discord import Interaction, Embed, Color, ui, ButtonStyle, SelectOption, Object
from src.aclient import client
from src.db.db import (get_user_collection, create_collection, get_cards_by_collection, delete_collection_by_name,
                        get_card_ids_in_collection, get_user_owned_card_ids, get_missing_cards_in_collection,
                        get_collection_id, has_claimed_collection_reward, claim_collection_reward, give_coins,
                        update_xp_and_check_level, get_card, remove_from_user_collection)
from src.utils.permissions import has_role
from src.utils.confirmation import ConfirmActionView

GUILD = Object(id=955464847028531280)

SELL_VALUES = {
    "common": 10,
    "rare": 20,
    "epic": 40,
    "legendary": 75
}

class CardPageView(ui.View):
    def __init__(self, user_id, cards, index=0):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.cards = cards
        self.index = index
        self.update_buttons()

    def update_buttons(self):
        self.clear_items()
        current_card = self.cards[self.index]
        self.add_item(ViewCardButton(card_id=current_card[0], label=f"View {current_card[1]}"))
        self.add_item(SellCardButton(card_id=current_card[0], rarity=current_card[2]))

        if self.index > 0:
            self.add_item(PreviousPageButton(self))
        if self.index < len(self.cards) - 1:
            self.add_item(NextPageButton(self))

    async def interaction_check(self, interaction: Interaction) -> bool:
        return interaction.user.id == self.user_id

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True

class ViewCardButton(ui.Button):
    def __init__(self, card_id, label):
        super().__init__(label=label, style=ButtonStyle.blurple, custom_id=f"viewcard_{card_id}")
        self.card_id = card_id

    async def callback(self, interaction: Interaction):
        card = await get_card(self.card_id)
        if not card:
            await interaction.response.send_message("❌ Card not found.", ephemeral=True)
            return

        embed = Embed(
            title=f"{card[1]} [{card[2]}]",
            description=f"**ATK:** {card[3]} | **DEF:** {card[4]} | **HP:** {card[5]}",
            color=Color.blue()
        )
        if isinstance(card[6], str) and card[6].startswith("http"):
            embed.set_image(url=card[6])

        await interaction.response.send_message(embed=embed, ephemeral=True)

class SellCardButton(ui.Button):
    def __init__(self, card_id, rarity):
        label = f"Sell ({SELL_VALUES.get(rarity.lower(), 5)} coins)"
        super().__init__(label=label, style=ButtonStyle.red, custom_id=f"sellcard_{card_id}")
        self.card_id = card_id
        self.rarity = rarity.lower()

    async def callback(self, interaction: Interaction):
        # Confirm the user still owns the card
        owned_cards = await get_user_collection(interaction.user.id)
        owned_card_ids = {card[0] for card in owned_cards}

        if self.card_id not in owned_card_ids:
            await interaction.response.send_message("❌ You no longer own this card.", ephemeral=True)
            return

        await remove_from_user_collection(interaction.user.id, self.card_id)
        coins = SELL_VALUES.get(self.rarity, 5)
        await give_coins(interaction.user.id, coins)
        await interaction.response.send_message(f"💰 You sold the card for {coins} coins!", ephemeral=True)


class PreviousPageButton(ui.Button):
    def __init__(self, parent_view):
        super().__init__(label="⬅️ Previous", style=ButtonStyle.secondary)
        self.parent_view = parent_view

    async def callback(self, interaction: Interaction):
        new_index = self.parent_view.index - 1
        new_view = CardPageView(self.parent_view.user_id, self.parent_view.cards, new_index)
        embed = build_single_card_embed(interaction.user.name, new_view.cards[new_index], new_index, len(self.parent_view.cards))
        await interaction.response.edit_message(embed=embed, view=new_view)

class NextPageButton(ui.Button):
    def __init__(self, parent_view):
        super().__init__(label="Next ➡️", style=ButtonStyle.secondary)
        self.parent_view = parent_view

    async def callback(self, interaction: Interaction):
        new_index = self.parent_view.index + 1
        new_view = CardPageView(self.parent_view.user_id, self.parent_view.cards, new_index)
        embed = build_single_card_embed(interaction.user.name, new_view.cards[new_index], new_index, len(self.parent_view.cards))
        await interaction.response.edit_message(embed=embed, view=new_view)

@client.tree.command(name="my_collection", description="View your card collection", guild=GUILD)
async def my_collection(interaction: Interaction):
    cards = await get_user_collection(interaction.user.id)
    if not cards:
        await interaction.response.send_message("🗃️ You don’t own any cards yet.", ephemeral=True)
        return

    index = 0
    embed = build_single_card_embed(interaction.user.name, cards[index], index, len(cards))
    view = CardPageView(interaction.user.id, cards, index)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

def build_single_card_embed(username, card, index, total):
    embed = Embed(
        title=f"🃏 {card[1]} ({card[2].title()})",
        description=f"**ATK:** {card[3]} | **DEF:** {card[4]} | **HP:** {card[5]}",
        color=Color.teal()
    )
    embed.set_footer(text=f"Card {index + 1} of {total}")
    return embed

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
