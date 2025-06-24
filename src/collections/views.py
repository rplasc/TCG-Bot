from discord import ui, Interaction, ButtonStyle, Embed, Color
from src.db.db import get_card, remove_from_user_collection, get_user_collection, give_coins

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
        self.add_item(SellCardButton(card_id=current_card[0], rarity=current_card[2], parent_view=self))

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
    def __init__(self, card_id, rarity, parent_view=None):
        label = f"Sell ({SELL_VALUES.get(rarity.lower(), 5)} coins)"
        super().__init__(label=label, style=ButtonStyle.red, custom_id=f"sellcard_{card_id}")
        self.card_id = card_id
        self.rarity = rarity.lower()
        self.parent_view = parent_view

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
        self.disabled = True
        self.label = "Sold ✅"
        await interaction.response.edit_message(view=self.parent_view)
        await interaction.followup.send(f"💰 You sold the card for {coins} coins!", ephemeral=True)

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

def build_single_card_embed(username, card, index, total):
    embed = Embed(
        title=f"🃏 {card[1]} ({card[2].title()})",
        description=f"**ATK:** {card[3]} | **DEF:** {card[4]} | **HP:** {card[5]}",
        color=Color.teal()
    )
    embed.set_footer(text=f"Card {index + 1} of {total}")
    return embed