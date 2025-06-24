from discord import ui, SelectOption, Interaction, ButtonStyle, Embed, Color
from .logic import SHOP_PACKS, handle_shop_purchase, handle_card_purchase, CARD_SHOP_PRICES, RARITY_EMOJIS
from src.db.db import get_daily_shop_cards
from src.utils.time import format_duration, get_seconds_until_next_rotation

class ShopView(ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=60)
        self.add_item(ShopSelect(user_id))

class ShopSelect(ui.Select):
    def __init__(self, user_id):
        self.user_id = user_id
        options = [
            SelectOption(label=v["label"], value=k, description=f"{v['cards']} cards — {v['cost']} coins")
            for k, v in SHOP_PACKS.items()
        ]
        super().__init__(placeholder="Select a pack to buy", options=options)

    async def callback(self, interaction: Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ You can’t use this menu.", ephemeral=True)
            return

        pack_key = self.values[0]
        pack = SHOP_PACKS[pack_key]
        await handle_shop_purchase(interaction, interaction.user.id, pack)

class ShopTypeView(ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.add_item(ShopTypeSelect(user_id))

class ShopTypeSelect(ui.Select):
    def __init__(self, user_id):
        self.user_id = user_id
        options = [
            SelectOption(label="🃏 Pack Shop", value="packs", description="Buy packs with multiple cards"),
            SelectOption(label="🛒 Card Shop", value="cards", description="Buy individual cards (rotates daily)")
        ]
        super().__init__(placeholder="Select a shop type", options=options)

    async def callback(self, interaction: Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This isn't your menu.", ephemeral=True)
            return

        if self.values[0] == "packs":
            await interaction.response.edit_message(
                content="🃏 Welcome to the Card Pack Shop!",
                view=ShopView(self.user_id),
                embed=None
            )
        else:
            cards = await get_daily_shop_cards()
            if not cards:
                await interaction.response.edit_message(content="🛒 No cards available today!", view=None)
                return

            rotation_in = format_duration(get_seconds_until_next_rotation())
            embed = Embed(
                title="🛒 Daily Card Shop",
                description=f"Available for purchase today only!\n⏳ Next rotation in: **{rotation_in}**",
                color=Color.orange()
            )
            view = ui.View()
            for card in cards:
                rarity = card[2].lower()
                price = CARD_SHOP_PRICES.get(rarity, 50)
                emoji = RARITY_EMOJIS.get(rarity, "")
                button = ui.Button(
                    label=f"Buy {card[1]} ({rarity.title()}) - {price} coins",
                    style=ButtonStyle.green,
                    custom_id=f"buycard_{card[0]}"
                )
                view.add_item(button)

                embed.add_field(
                    name=f"{emoji} {card[1]} [{card[2]}]",
                    value=f"ATK: {card[3]} | DEF: {card[4]} | HP: {card[5]}",
                    inline=False
                )

            async def button_callback(interaction: Interaction):
                card_id = int(interaction.data['custom_id'].split("_")[1])
                card, xp, level, coins_awarded = await handle_card_purchase(interaction, card_id)

                if card:
                    rarity = card[2].lower()
                    emoji = RARITY_EMOJIS.get(rarity, "")
                    embed = Embed(
                        title="🎉 Card Purchased!",
                        description=f"{interaction.user.mention} just bought {emoji} **{card[1]}**!",
                        color=Color.green()
                    )
                    embed.add_field(name="Stats", value=f"ATK: {card[3]} | DEF: {card[4]} | HP: {card[5]}", inline=False)
                    embed.set_footer(text=f"+{xp} XP")
                    if card[6].startswith("http"):
                        embed.set_image(url=card[6])

                    if level:
                        embed.add_field(name="🆙 Level Up!", value=f"You're now level {level}! (+{coins_awarded} coins)", inline=False)

                    await interaction.edit_original_response(view=None)
                    await interaction.followup.send(embed=embed, ephemeral=False)

            for item in view.children:
                item.callback = button_callback

            await interaction.response.edit_message(content=None, embed=embed, view=view)
