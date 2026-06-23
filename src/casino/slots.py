import random
import asyncio
from discord import Interaction, Embed, Color, ui, ButtonStyle
from src.database.db import register_user, user_owns_card, add_to_user_collection, get_balance
from src.economy.service import award_coins, spend_coins
from src.economy.config import CASINO_WAGER, CASINO_PAYOUT
from src.shop.logic import draw_card, RARITY_EMOJIS
from src.casino.types import SlotSession
from src.casino.wagers import max_wager_for
from src.casino.rewards import CasinoResult, build_result_footer
from src.casino.events import emit_casino_event
from src.casino.modifiers import get_active_casino_modifiers, apply_casino_modifiers
from src.events.service import casino_payout_multiplier

SLOT_SYMBOLS = ["🍒", "🍋", "🍇", "🔔", "⭐", "💎"]
JACKPOT = "💎"
STAR = "⭐"

# Per-wager integer payouts: {wager: {outcome_key: payout}}
# outcome keys: "pair", "triple_fruit", "triple_star", "jackpot"
_PAYTABLE: dict[int, dict[str, int]] = {
    5:   {"pair": 7,   "triple_fruit": 15,  "triple_star": 30,  "jackpot": 50},
    25:  {"pair": 37,  "triple_fruit": 75,  "triple_star": 150, "jackpot": 250},
    100: {"pair": 150, "triple_fruit": 300, "triple_star": 600, "jackpot": 1000},
}

_PAYTABLE_OUTCOMES = "Any pair\nTriple 🍒🍋🍇🔔\nTriple ⭐\nTriple 💎 + card"
_PAYTABLE_PAYOUTS  = "7 · 37 · 150\n15 · 75 · 300\n30 · 150 · 600\n50 · 250 · 1000"


def spin_slots() -> list[str]:
    return [random.choice(SLOT_SYMBOLS) for _ in range(3)]


def evaluate_spin(result: list[str]) -> tuple[str, str]:
    """Return (outcome_key, display_label). outcome_key is '' for no win."""
    s0, s1, s2 = result
    if s0 == s1 == s2 == JACKPOT:
        return "jackpot", "💎 JACKPOT!"
    if s0 == s1 == s2 == STAR:
        return "triple_star", "⭐ Triple Stars!"
    if s0 == s1 == s2:
        return "triple_fruit", "🎉 Triple Match!"
    if s0 == s1 or s1 == s2 or s0 == s2:
        return "pair", "✨ Pair!"
    return "", "😢 No match"


async def run_slot_spin(interaction: Interaction, session: SlotSession, edit: bool = False):
    user_id = session.user_id
    await register_user(user_id, interaction.user.name)

    modifiers = await get_active_casino_modifiers(user_id, game="slots")

    await spend_coins(user_id, session.wager, CASINO_WAGER, {"game": "slots"})

    fake_embed = Embed(title="🎰 Slot Machine", description="Spinning...", color=Color.dark_gray())
    fake_embed.add_field(name="Spin", value="🔄 | 🔄 | 🔄", inline=False)

    if edit:
        await interaction.response.edit_message(embed=fake_embed, view=None)
    else:
        await interaction.response.send_message(embed=fake_embed, ephemeral=True)

    await asyncio.sleep(1.5)

    result = spin_slots()
    outcome_key, outcome_label = evaluate_spin(result)

    paytable = _PAYTABLE[session.wager]
    payout = paytable.get(outcome_key, 0)
    if payout > 0:
        payout = int(round(payout * casino_payout_multiplier("slots")))
    card_awarded = False
    card_id = None

    if payout > 0:
        await award_coins(user_id, payout, CASINO_PAYOUT, {"game": "slots", "outcome": outcome_key or "loss"})

    card_message = None
    if outcome_key == "jackpot":
        card = await draw_card()
        if card and not await user_owns_card(user_id, card[0]):
            await add_to_user_collection(user_id, card[0])
            emoji = RARITY_EMOJIS.get(card[2].lower(), "")
            card_message = f"🃏 You won: {emoji} {card[1]}"
            card_awarded = True
            card_id = card[0]
        else:
            card_message = "🃏 Card draw: duplicate (no new card)"

    net = payout - session.wager
    session.net += net
    session.spins += 1

    base_result = CasinoResult(
        user_id=user_id,
        game="slots",
        wager=session.wager,
        payout=payout,
        net=net,
        outcome=outcome_key or "loss",
        metadata={
            "symbols": result,
            "card_awarded": card_awarded,
            "card_id": card_id,
            "spin": session.spins,
        },
    )
    result_obj = apply_casino_modifiers(base_result, modifiers)

    balance = await get_balance(user_id)
    embed = Embed(title="🎰 Slot Machine", color=Color.gold() if payout > 0 else Color.greyple())
    embed.add_field(name="Spin", value=" | ".join(result), inline=False)
    embed.add_field(name=outcome_label, value=f"+{payout} coins" if payout > 0 else "No payout", inline=False)
    if card_message:
        embed.add_field(name="Card Reward", value=card_message, inline=False)
    net_session_str = f"+{session.net}" if session.net >= 0 else str(session.net)
    embed.set_footer(
        text=f"{build_result_footer(session.wager, payout, net, balance)} | Session net: {net_session_str} | Spins: {session.spins}/5"
    )

    await emit_casino_event("casino.slots.spin", result_obj)
    if outcome_key == "jackpot":
        await emit_casino_event("casino.slots.jackpot", result_obj)
        if card_awarded:
            await emit_casino_event("casino.reward.card_awarded", result_obj)

    view = SlotView(session)
    if edit:
        await interaction.edit_original_response(embed=embed, view=view)
    else:
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    if outcome_key == "jackpot":
        await interaction.followup.send(
            f"🎰 **{interaction.user.mention}** hit the JACKPOT on slots and won **{payout} coins**!",
            ephemeral=False,
        )


class SlotView(ui.View):
    def __init__(self, session: SlotSession):
        super().__init__(timeout=60)
        self.session = session

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True

    @ui.button(label="🔁 Spin Again", style=ButtonStyle.green)
    async def respin(self, interaction: Interaction, button: ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message("❌ Not your session.", ephemeral=True)
            return
        if self.session.spins >= self.session.max_spins:
            await interaction.response.send_message("⏳ You've used all spins for this session.", ephemeral=True)
            self.stop()
            return
        await run_slot_spin(interaction, self.session, edit=True)


class WagerSelectView(ui.View):
    def __init__(self, user_id: int, max_wager: int):
        super().__init__(timeout=30)
        self.user_id = user_id
        self.max_wager = max_wager
        # Disable any wager button whose amount (leading number in its label)
        # exceeds the player's level cap.
        for child in self.children:
            label = getattr(child, "label", "") or ""
            lead = label.split(" ", 1)[0]
            if lead.isdigit() and int(lead) > max_wager:
                child.disabled = True

    def _check(self, interaction: Interaction) -> bool:
        return interaction.user.id == self.user_id

    async def _start(self, interaction: Interaction, wager: int):
        if not self._check(interaction):
            await interaction.response.send_message("❌ Not your session.", ephemeral=True)
            return
        if wager > self.max_wager:
            await interaction.response.send_message(
                f"❌ Your max wager is {self.max_wager} coins at your level.", ephemeral=True
            )
            return
        self.stop()
        session = SlotSession(user_id=self.user_id, wager=wager)
        await run_slot_spin(interaction, session, edit=False)

    @ui.button(label="5 🪙 Low", style=ButtonStyle.secondary)
    async def low(self, interaction: Interaction, _: ui.Button):
        await self._start(interaction, 5)

    @ui.button(label="25 🪙 Standard", style=ButtonStyle.blurple)
    async def standard(self, interaction: Interaction, _: ui.Button):
        await self._start(interaction, 25)

    @ui.button(label="100 🪙 High Roller", style=ButtonStyle.danger)
    async def high_roller(self, interaction: Interaction, _: ui.Button):
        await self._start(interaction, 100)


async def play_slots(interaction: Interaction):
    max_wager = await max_wager_for(interaction.user.id, game="slots")
    embed = Embed(title="🎰 Slot Machine – Choose Wager", color=Color.dark_gold())
    embed.description = "Pick your stake to start spinning."
    embed.add_field(name="Outcome", value=_PAYTABLE_OUTCOMES, inline=True)
    embed.add_field(name="5🪙 · 25🪙 · 100🪙", value=_PAYTABLE_PAYOUTS, inline=True)
    view = WagerSelectView(user_id=interaction.user.id, max_wager=max_wager)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
