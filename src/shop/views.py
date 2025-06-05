from discord import ui, SelectOption, Interaction
from .logic import SHOP_PACKS, handle_shop_purchase

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
