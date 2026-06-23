"""Discord UI for the daily pari-mutuel sports-betting game."""

from discord import Interaction, ButtonStyle, ui, Embed, Color

from src.casino.sportsbook import (
    get_or_create_today_match,
    compute_odds,
    check_bet_allowed,
    record_bet,
)
from src.casino.wagers import validate_wager
from src.economy.service import spend_coins
from src.economy.config import SPORTS_BET_WAGER
from src.database.db import get_balance, get_user_bet_side


async def build_match_embed(match: dict, viewer_id: int | None = None) -> Embed:
    odds = await compute_odds(match)
    embed = Embed(
        title="🏟️ Daily Sports Betting",
        description=(
            f"Place your bets on today's matchup! Odds are pari-mutuel — they shift as "
            f"coins flow in, and the whole pool (minus a small house cut) is split among "
            f"the winning side at the end of the day."
        ),
        color=Color.blue(),
    )
    embed.add_field(
        name=f"🅰️ {match['team_a']}",
        value=f"Odds **{odds['a']}x**\nPool: {odds['pool_a']} coins",
        inline=True,
    )
    embed.add_field(
        name=f"🅱️ {match['team_b']}",
        value=f"Odds **{odds['b']}x**\nPool: {odds['pool_b']} coins",
        inline=True,
    )
    embed.add_field(
        name="💰 Total Pool",
        value=f"{odds['pool_a'] + odds['pool_b']} coins",
        inline=False,
    )

    if viewer_id is not None:
        side = await get_user_bet_side(match["id"], viewer_id)
        if side:
            backed = match["team_a"] if side == "a" else match["team_b"]
            embed.set_footer(text=f"You're backing {backed}. Settles at 8 AM PST.")
        else:
            embed.set_footer(text="You haven't bet yet. Settles at 8 AM PST.")
    return embed


class SportsWagerModal(ui.Modal, title="Sports Bet – Place Wager"):
    amount = ui.TextInput(label="Wager amount", placeholder="e.g. 100", required=True)

    def __init__(self, match: dict, side: str):
        super().__init__()
        self.match = match
        self.side = side

    async def on_submit(self, interaction: Interaction):
        user_id = interaction.user.id

        # Re-fetch the match so odds/teams are current at submit time.
        match = await get_or_create_today_match()

        ok, result = await validate_wager(user_id, self.amount.value, game="sports")
        if not ok:
            await interaction.response.send_message(result, ephemeral=True)
            return
        amount = result

        # Enforce the single-side rule before taking any coins.
        allowed, msg = await check_bet_allowed(user_id, match, self.side)
        if not allowed:
            await interaction.response.send_message(msg, ephemeral=True)
            return

        # Charge the player first, then record the bet so a failed charge never
        # leaves an orphan bet row.
        spent = await spend_coins(
            user_id, amount, SPORTS_BET_WAGER,
            {"match_id": match["id"], "side": self.side},
        )
        if not spent:
            await interaction.response.send_message("❌ You don't have enough coins.", ephemeral=True)
            return
        await record_bet(user_id, match, self.side, amount)

        backed = match["team_a"] if self.side == "a" else match["team_b"]
        balance = await get_balance(user_id)
        embed = await build_match_embed(match, viewer_id=user_id)
        await interaction.response.edit_message(embed=embed, view=SportsBetView(match))
        await interaction.followup.send(
            f"✅ Bet **{amount}** coins on **{backed}**! Balance: {balance} coins.",
            ephemeral=True,
        )


class SportsBetView(ui.View):
    def __init__(self, match: dict):
        super().__init__(timeout=120)
        self.match = match
        self.bet_a.label = f"🅰️ Bet {match['team_a']}"
        self.bet_b.label = f"🅱️ Bet {match['team_b']}"

    @ui.button(style=ButtonStyle.primary, custom_id="sports_bet_a")
    async def bet_a(self, interaction: Interaction, _: ui.Button):
        await interaction.response.send_modal(SportsWagerModal(self.match, "a"))

    @ui.button(style=ButtonStyle.primary, custom_id="sports_bet_b")
    async def bet_b(self, interaction: Interaction, _: ui.Button):
        await interaction.response.send_modal(SportsWagerModal(self.match, "b"))


async def open_sportsbook(interaction: Interaction):
    """Entry point used by both the /sportsbet command and the casino menu button."""
    match = await get_or_create_today_match()
    embed = await build_match_embed(match, viewer_id=interaction.user.id)
    await interaction.response.send_message(embed=embed, view=SportsBetView(match))
