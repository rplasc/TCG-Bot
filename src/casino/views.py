from discord import ui, Interaction, ButtonStyle
from src.casino.blackjack import start_blackjack

class CasinoView(ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=30)
        self.user_id = user_id

    @ui.button(label="🃏 Blackjack", style=ButtonStyle.green, custom_id="blackjack_button")
    async def blackjack_button(self, interaction: Interaction, button: ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ You can't use this.", ephemeral=True)
            return

        await start_blackjack(interaction)
    
    @ui.button(label="🎰 Slots", style=ButtonStyle.green, custom_id="slots")
    async def slots_button(self, interaction: Interaction, button: ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Not your casino session.", ephemeral=True)
            return
        from src.casino.slots import play_slots
        await play_slots(interaction)
