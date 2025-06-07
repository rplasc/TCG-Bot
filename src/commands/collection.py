from discord import Interaction, Embed, Color, ui, ButtonStyle, SelectOption, Object
from src.aclient import client
from src.db.db import (get_user_collection, create_collection, get_cards_by_collection, delete_collection_by_name,
                        get_card_ids_in_collection, get_user_owned_card_ids, get_missing_cards_in_collection,
                        get_collection_id, has_claimed_collection_reward, claim_collection_reward, give_coins,
                        update_xp_and_check_level, get_card)
from src.utils.permissions import has_role
from src.utils.confirmation import ConfirmActionView

GUILD = Object(id=955464847028531280)

CARDS_PER_PAGE = 10

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

class CollectionView(ui.View):
    def __init__(self, user_id, cards, page=0, rarity_filter=None):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.cards = [c for c in cards if rarity_filter is None or c[2].lower() == rarity_filter]
        self.page = page
        self.rarity_filter = rarity_filter
        self.update_buttons()

    def update_buttons(self):
        self.clear_items()
        start = self.page * CARDS_PER_PAGE
        end = start + CARDS_PER_PAGE
        page_cards = self.cards[start:end]

        for card in page_cards:
            self.add_item(ViewCardButton(card_id=card[0], label=f"View {card[1]}"))

        if self.page > 0:
            self.add_item(ui.Button(label="⬅️ Previous", style=ButtonStyle.secondary, custom_id="prev_page"))
        if self.page < (len(self.cards) - 1) // CARDS_PER_PAGE:
            self.add_item(ui.Button(label="Next ➡️", style=ButtonStyle.secondary, custom_id="next_page"))

        # Add rarity filter dropdown
        self.add_item(RarityFilterSelect(self.user_id, self.cards, self.rarity_filter, self.page))

    async def interaction_check(self, interaction: Interaction) -> bool:
        return interaction.user.id == self.user_id

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True

class RarityFilterSelect(ui.Select):
    def __init__(self, user_id, cards, current_filter, current_page):
        options = [SelectOption(label="All", value="all", default=current_filter is None)]
        rarities = sorted(set(card[2].lower() for card in cards))
        for rarity in rarities:
            options.append(SelectOption(label=rarity.title(), value=rarity, default=current_filter == rarity))
        super().__init__(placeholder="Filter by rarity", options=options)
        self.user_id = user_id
        self.cards = cards
        self.current_page = current_page

    async def callback(self, interaction: Interaction):
        rarity = None if self.values[0] == "all" else self.values[0]
        view = CollectionView(self.user_id, self.cards, page=0, rarity_filter=rarity)
        embed = build_collection_embed(interaction.user.name, view.cards, 0)
        await interaction.response.edit_message(embed=embed, view=view)

@client.tree.command(name="my_collection", description="View your card collection", guild=GUILD)
async def my_collection(interaction: Interaction):
    cards = await get_user_collection(interaction.user.id)
    if not cards:
        await interaction.response.send_message("🗃️ You don’t own any cards yet.", ephemeral=True)
        return

    page = 0
    embed = build_collection_embed(interaction.user.name, cards, page)
    view = CollectionView(interaction.user.id, cards, page)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

def build_collection_embed(username, cards, page):
    embed = Embed(
        title=f"🗂️ {username}'s Card Collection",
        description=f"Total unique cards: {len(cards)}",
        color=Color.teal()
    )
    start = page * CARDS_PER_PAGE
    end = start + CARDS_PER_PAGE
    for card in cards[start:end]:
        if len(card) >= 7:
            embed.add_field(
                name=f"🃏 {card[1]} ({card[2].title()})",
                value=f"**ATK:** {card[3]} | **DEF:** {card[4]} | **HP:** {card[5]}",
                inline=False
            )
        else:
            embed.add_field(name="⚠️ Invalid Card", value="This card entry is incomplete.", inline=False)
    embed.set_footer(text=f"Page {page + 1} / {(len(cards) - 1) // CARDS_PER_PAGE + 1}")
    return embed

@client.event
async def on_interaction(interaction: Interaction):
    if interaction.type.name == "component":
        custom_id = interaction.data.get("custom_id")
        message = interaction.message
        if custom_id in ["prev_page", "next_page"]:
            view = message.components[0].view  # type: ignore
            if isinstance(view, CollectionView):
                new_page = view.page - 1 if custom_id == "prev_page" else view.page + 1
                new_view = CollectionView(view.user_id, view.cards, new_page, view.rarity_filter)
                embed = build_collection_embed(interaction.user.name, new_view.cards, new_page)
                await interaction.response.edit_message(embed=embed, view=new_view)

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
