from src.aclient import client
from discord import Interaction, Embed, Color
from src.casino.views import CasinoView
from src.casino.sports_view import open_sportsbook

@client.tree.command(name="casino", description="Play gambling games")
async def casino(interaction: Interaction):
    embed = Embed(
        title="🎰 Welcome to the Casino!",
        description="Pick a game below. Each game lets you wager your coins — bet responsibly!",
        color=Color.dark_gold()
    )
    embed.add_field(name="🃏 Blackjack", value="Beat the dealer to 21.", inline=False)
    embed.add_field(name="🎰 Slots", value="Spin for matching symbols.", inline=False)
    embed.add_field(name="🎡 Roulette", value="Bet on a color or number.", inline=False)
    embed.add_field(name="🏟️ Sports Bet", value="Back a team in the daily matchup against other players.", inline=False)
    await interaction.response.send_message(
        embed=embed,
        view=CasinoView(interaction.user.id),
        ephemeral=True
    )


@client.tree.command(name="sportsbet", description="Bet on today's matchup against other players")
async def sportsbet(interaction: Interaction):
    await open_sportsbook(interaction)
