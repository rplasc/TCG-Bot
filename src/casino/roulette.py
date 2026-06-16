import random
from discord import Interaction, ButtonStyle, ui, Embed, Color
from src.database.db import get_balance
from src.economy.service import award_coins, spend_coins
from src.economy.config import CASINO_WAGER, CASINO_PAYOUT
from src.casino.wagers import validate_wager
from src.casino.rewards import CasinoResult, build_result_footer
from src.casino.events import emit_casino_event
from src.casino.modifiers import get_active_casino_modifiers, apply_casino_modifiers

RED_NUMBERS = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
BLACK_NUMBERS = {2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35}


def _spin() -> tuple[int, str]:
    result = random.randint(0, 36)
    if result == 0:
        color = "green"
    elif result in RED_NUMBERS:
        color = "red"
    else:
        color = "black"
    return result, color


async def _resolve_and_respond(
    interaction: Interaction,
    user_id: int,
    wager: int,
    bet_type: str,
    bet_display: str,
    winning_condition,
    exact_number: int | None = None,
):
    modifiers = await get_active_casino_modifiers(user_id, game="roulette")

    await spend_coins(user_id, wager, CASINO_WAGER, {"game": "roulette", "bet_type": bet_type})
    number, color = _spin()

    won = winning_condition(number, color)
    is_exact = exact_number is not None and number == exact_number

    if is_exact:
        payout = wager * 36
        outcome = "exact_hit"
    elif won:
        payout = wager * 2
        outcome = "win"
    else:
        payout = 0
        outcome = "loss"

    if payout > 0:
        await award_coins(user_id, payout, CASINO_PAYOUT, {"game": "roulette", "outcome": outcome})

    net = payout - wager
    base_result = CasinoResult(
        user_id=user_id,
        game="roulette",
        wager=wager,
        payout=payout,
        net=net,
        outcome=outcome,
        metadata={"bet_type": bet_type, "number": number, "color": color},
    )
    result = apply_casino_modifiers(base_result, modifiers)

    balance = await get_balance(user_id)
    embed_color = Color.green() if payout > 0 else Color.red()
    embed = Embed(title="🎡 Roulette Result", color=embed_color)
    embed.add_field(name="Result", value=f"**{number}** ({color})", inline=True)
    embed.add_field(name="Your Bet", value=bet_display, inline=True)

    if payout > 0:
        embed.add_field(name="🎉 Payout", value=f"{payout} coins", inline=False)
    else:
        embed.add_field(name="😢 No Win", value="Better luck next time.", inline=False)

    embed.set_footer(text=build_result_footer(wager, payout, net, balance))

    await emit_casino_event("casino.roulette.spin", result)
    if outcome == "exact_hit":
        await emit_casino_event("casino.roulette.exact_hit", result)

    await interaction.response.send_message(embed=embed, ephemeral=True)

    if outcome == "exact_hit":
        await interaction.followup.send(
            f"🎡 **{interaction.user.mention}** hit the exact number **{number}** on roulette and won **{payout} coins**!",
            ephemeral=False,
        )


class RouletteWagerModal(ui.Modal, title="Roulette – Place Wager"):
    amount = ui.TextInput(label="Wager amount", placeholder="e.g. 100", required=True)

    def __init__(self, bet_type: str, bet_display: str, winning_condition, exact_number: int | None = None):
        super().__init__()
        self.bet_type = bet_type
        self.bet_display = bet_display
        self.winning_condition = winning_condition
        self.exact_number = exact_number

    async def on_submit(self, interaction: Interaction):
        ok, result = await validate_wager(interaction.user.id, self.amount.value)
        if not ok:
            await interaction.response.send_message(result, ephemeral=True)
            return
        await _resolve_and_respond(
            interaction,
            interaction.user.id,
            result,
            self.bet_type,
            self.bet_display,
            self.winning_condition,
            self.exact_number,
        )


class ExactNumberModal(ui.Modal, title="Roulette – Exact Number"):
    number = ui.TextInput(label="Number (0–36)", placeholder="e.g. 17", required=True)
    amount = ui.TextInput(label="Wager amount", placeholder="e.g. 100", required=True)

    async def on_submit(self, interaction: Interaction):
        try:
            n = int(self.number.value.strip())
            if not 0 <= n <= 36:
                raise ValueError
        except ValueError:
            await interaction.response.send_message("❌ Enter a number between 0 and 36.", ephemeral=True)
            return

        ok, result = await validate_wager(interaction.user.id, self.amount.value)
        if not ok:
            await interaction.response.send_message(result, ephemeral=True)
            return

        await _resolve_and_respond(
            interaction,
            interaction.user.id,
            result,
            "exact",
            f"Exact: **{n}**",
            lambda num, *_: num == n,
            exact_number=n,
        )


class RouletteBetView(ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=60)
        self.user_id = user_id

    def _check(self, interaction: Interaction) -> bool:
        return interaction.user.id == self.user_id

    async def _open_wager(self, interaction: Interaction, bet_type: str, bet_display: str, condition):
        if not self._check(interaction):
            await interaction.response.send_message("❌ Not your session.", ephemeral=True)
            return
        await interaction.response.send_modal(RouletteWagerModal(bet_type, bet_display, condition))

    @ui.button(label="🔴 Red", style=ButtonStyle.red, row=0)
    async def bet_red(self, interaction: Interaction, _: ui.Button):
        await self._open_wager(interaction, "red", "Color: Red", lambda _n, c: c == "red")

    @ui.button(label="⚫ Black", style=ButtonStyle.secondary, row=0)
    async def bet_black(self, interaction: Interaction, _: ui.Button):
        await self._open_wager(interaction, "black", "Color: Black", lambda _n, c: c == "black")

    @ui.button(label="🔢 Even", style=ButtonStyle.blurple, row=0)
    async def bet_even(self, interaction: Interaction, _: ui.Button):
        await self._open_wager(interaction, "even", "Even numbers (2–36)", lambda n, _c: n != 0 and n % 2 == 0)

    @ui.button(label="🔢 Odd", style=ButtonStyle.blurple, row=0)
    async def bet_odd(self, interaction: Interaction, _: ui.Button):
        await self._open_wager(interaction, "odd", "Odd numbers (1–35)", lambda n, _c: n % 2 == 1)

    @ui.button(label="📉 Low (1–18)", style=ButtonStyle.green, row=1)
    async def bet_low(self, interaction: Interaction, _: ui.Button):
        await self._open_wager(interaction, "low", "Low (1–18)", lambda n, _c: 1 <= n <= 18)

    @ui.button(label="📈 High (19–36)", style=ButtonStyle.green, row=1)
    async def bet_high(self, interaction: Interaction, _: ui.Button):
        await self._open_wager(interaction, "high", "High (19–36)", lambda n, _c: 19 <= n <= 36)

    @ui.button(label="🎯 Exact Number (36×)", style=ButtonStyle.danger, row=1)
    async def bet_exact(self, interaction: Interaction, _: ui.Button):
        if not self._check(interaction):
            await interaction.response.send_message("❌ Not your session.", ephemeral=True)
            return
        await interaction.response.send_modal(ExactNumberModal())
