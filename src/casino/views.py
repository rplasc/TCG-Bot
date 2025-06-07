from discord import ui, Interaction, ButtonStyle
from src.casino.blackjack import start_blackjack
from src.casino.slots import play_slots
from src.casino.roulette import RouletteBetModal

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
        await play_slots(interaction)

    @ui.button(label="🎡 Roulette", style=ButtonStyle.green, custom_id="roulette")
    async def roulette_button(self, interaction: Interaction, button: ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ You can't use this.", ephemeral=True)
            return
        await interaction.response.send_modal(RouletteBetModal())