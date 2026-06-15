from discord import ui, Interaction, Embed, ButtonStyle, SelectOption, Color, TextStyle
from src.database.db import (
    remove_from_user_collection, add_to_user_collection,
    can_afford, deduct_coins, give_coins, get_card
)

class TradeView(ui.View):
    def __init__(self, user_id, target_id, user_cards, target_cards):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.target_id = target_id
        self.user_cards = user_cards
        self.target_cards = target_cards
        self.selected_user_card = None
        self.selected_target_card = None
        self.coins_offered = 0

        self.user_dropdown = TradeDropdown("Your Card", user_cards, self)
        self.target_dropdown = TradeDropdown("Target Card", target_cards, self)
        self.coin_input = TradeCoinInput(self)
        self.submit_button = SubmitTradeButton(self)

        self.add_item(self.user_dropdown)
        self.add_item(self.target_dropdown)
        self.add_item(AddCoinsButton(self))
        self.add_item(self.submit_button)
        self.add_item(CancelTradeButton(self))

class TradeDropdown(ui.Select):
    def __init__(self, label: str, cards: list, parent_view: TradeView):
        self.label_type = label
        self.parent_view = parent_view
        options = [SelectOption(label=f"{card[1]} [{card[2]}]", value=str(card[0])) for card in cards]
        super().__init__(placeholder=label, options=options, min_values=1, max_values=1)

    async def callback(self, interaction: Interaction):
        card_id = int(self.values[0])
        if self.label_type == "Your Card":
            self.parent_view.selected_user_card = card_id
        else:
            self.parent_view.selected_target_card = card_id
        await interaction.response.defer()

class TradeCoinInput(ui.TextInput):
    def __init__(self, parent_view: TradeView):
        self.parent_view = parent_view
        super().__init__(
            label="Coins to offer (optional)",
            placeholder="e.g. 100",
            required=False,
            style=TextStyle.short,
            custom_id="coin_input"
        )

    async def callback(self, interaction: Interaction):
        try:
            value = self.value.strip()
            self.parent_view.coins_offered = int(value) if value else 0
            await interaction.response.send_message("✅ Coins updated.", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Invalid coin amount.", ephemeral=True)

class SubmitTradeButton(ui.Button):
    def __init__(self, parent_view: TradeView):
        super().__init__(label="📨 Submit Trade", style=ButtonStyle.green)
        self.parent_view = parent_view

    async def callback(self, interaction: Interaction):
        pv = self.parent_view
        if interaction.user.id != pv.user_id:
            await interaction.response.send_message("❌ Only the trade initiator can submit.", ephemeral=True)
            return

        if not pv.selected_user_card or not pv.selected_target_card:
            await interaction.response.send_message("❌ Please select both cards.", ephemeral=True)
            return

        if pv.coins_offered < 0:
            await interaction.response.send_message("❌ Invalid coin offer.", ephemeral=True)
            return

        if pv.coins_offered > 0 and not await can_afford(pv.user_id, pv.coins_offered):
            await interaction.response.send_message("❌ You don't have enough coins.", ephemeral=True)
            return

        offered_card = await get_card(pv.selected_user_card)
        requested_card = await get_card(pv.selected_target_card)

        offer_text = f"🃏 {offered_card[1]} [{offered_card[2]}]"
        request_text = f"🃏 {requested_card[1]} [{requested_card[2]}]"
        
        if pv.coins_offered:
            offer_text += f"\n💰 {pv.coins_offered} coins"
        
        # Send the confirmation to target user
        embed = Embed(title="🔁 Trade Request", color=Color.blue())
        embed.add_field(name="From", value=f"<@{pv.user_id}>", inline=True)
        embed.add_field(name="To", value=f"<@{pv.target_id}>", inline=True)
        embed.add_field(name="They offer", value=offer_text, inline=False)
        embed.add_field(name="They want", value=request_text, inline=False)

        view = ConfirmTradeView(pv.user_id, pv.target_id, pv.selected_user_card, pv.selected_target_card, pv.coins_offered)
        await interaction.channel.send(content=f"<@{pv.target_id}>", embed=embed, view=view)

class ConfirmTradeView(ui.View):
    def __init__(self, user_id, target_id, offered_card, requested_card, coins_offered):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.target_id = target_id
        self.offered_card = offered_card
        self.requested_card = requested_card
        self.coins_offered = coins_offered

    @ui.button(label="✅ Accept", style=ButtonStyle.success)
    async def accept(self, interaction: Interaction, button: ui.Button):
        if interaction.user.id != self.target_id:
            await interaction.response.send_message("❌ Only the trade recipient can accept.", ephemeral=True)
            return

        await remove_from_user_collection(self.user_id, self.offered_card)
        await remove_from_user_collection(self.target_id, self.requested_card)
        await add_to_user_collection(self.user_id, self.requested_card)
        await add_to_user_collection(self.target_id, self.offered_card)

        if self.coins_offered > 0:
            await deduct_coins(self.user_id, self.coins_offered)
            await give_coins(self.target_id, self.coins_offered)

        for item in self.children:
            item.disabled = True
        await interaction.message.edit(view=self)

        await interaction.response.send_message("✅ Trade completed!", ephemeral=False)

    @ui.button(label="❌ Decline", style=ButtonStyle.danger)
    async def decline(self, interaction: Interaction, button: ui.Button):
        if interaction.user.id != self.target_id:
            await interaction.response.send_message("❌ Only the trade recipient can decline.", ephemeral=True)
            return

        for item in self.children:
            item.disabled = True
        await interaction.message.edit(view=self)

        await interaction.response.send_message("❌ Trade declined.", ephemeral=False)

class CancelTradeButton(ui.Button):
    def __init__(self, parent_view):
        super().__init__(label="✖ Cancel", style=ButtonStyle.secondary)
        self.parent_view = parent_view

    async def callback(self, interaction: Interaction):
        if interaction.user.id != self.parent_view.user_id:
            await interaction.response.send_message("❌ Only the trade initiator can cancel.", ephemeral=True)
            return
        for item in self.parent_view.children:
            item.disabled = True
        self.parent_view.stop()
        await interaction.response.edit_message(content="❌ Trade cancelled.", embed=None, view=self.parent_view)

class AddCoinsButton(ui.Button):
    def __init__(self, parent_view):
        super().__init__(label="➕ Add Coins", style=ButtonStyle.blurple)
        self.parent_view = parent_view

    async def callback(self, interaction: Interaction):
        await interaction.response.send_modal(OfferCoinsModal(self.parent_view))

class OfferCoinsModal(ui.Modal, title="Add Coins to Offer"):
    coins = ui.TextInput(label="Coins to offer", placeholder="e.g. 100", required=True)

    def __init__(self, parent_view):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: Interaction):
        try:
            amount = int(self.coins.value)
            if amount < 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message("❌ Invalid coin amount.", ephemeral=True)
            return

        self.parent_view.coins_offered = amount
        await interaction.response.send_message(f"✅ Added {amount} coins to the offer.", ephemeral=True)
