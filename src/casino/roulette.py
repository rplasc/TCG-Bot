import random
from discord import Interaction, ButtonStyle, ui, Embed, Color
from src.database.db import can_afford, deduct_coins, give_coins

RED_NUMBERS = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
BLACK_NUMBERS = {2,4,6,8,10,11,13,15,17,20,22,24,26,28,29,31,33,35}

class RouletteButton(ui.Button):
    def __init__(self):
        super().__init__(label="🎡 Roulette", style=ButtonStyle.green)

    async def callback(self, interaction: Interaction):
        await interaction.response.send_modal(RouletteBetModal())

class RouletteBetModal(ui.Modal, title="Roulette Bet"):
    bet = ui.TextInput(label="Your Bet (color or number)", placeholder="e.g. red or 17", required=True)

    amount = ui.TextInput(label="Bet amount", placeholder="e.g. 100", required=True)

    async def on_submit(self, interaction: Interaction):
        bet_value = self.bet.value.strip().lower()
        bet_number = None
        bet_color = None
        amount = int(self.amount.value)

        if bet_value.isdigit():
            bet_number = int(bet_value)
            if not 0 <= bet_number <= 36:
                await interaction.response.send_message("❌ Invalid number. Enter a number between 0 and 36.", ephemeral=True)
                return
        elif bet_value in {"red", "black", "green"}:
            bet_color = bet_value
        else:
            await interaction.response.send_message("❌ Invalid input. Enter a color (red, black, green) or a number (0–36).", ephemeral=True)
            return

        if not await can_afford(interaction.user.id, amount):
            await interaction.response.send_message("❌ You can't afford this bet.", ephemeral=True)
            return

        await deduct_coins(interaction.user.id, amount)

        result = random.randint(0, 36)
        result_color = "green" if result == 0 else "red" if result in RED_NUMBERS else "black"

        payout = 0
        if bet_number is not None and bet_number == result:
            payout = amount * 36
        elif bet_color == result_color:
            payout = amount * 2

        if payout > 0:
            await give_coins(interaction.user.id, payout)

        embed = Embed(title="🎡 Roulette Result", color=Color.green() if payout > 0 else Color.red())
        embed.add_field(name="Result", value=f"{result} ({result_color})", inline=False)
        embed.add_field(name="Your Bet", value=f"Color: {bet_color or 'None'}, Number: {bet_number or 'None'}\nAmount: {amount}", inline=False)
        embed.add_field(name="Payout", value=f"{'+' if payout > 0 else ''}{payout} coins", inline=False)
        await interaction.response.send_message("🎡 Spinning the wheel...", ephemeral=True)
        await interaction.followup.send(
            content=f"🎲 {interaction.user.mention} spun the wheel!",
            embed=embed
        )
