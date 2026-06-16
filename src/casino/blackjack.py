import math
from discord import ui, Interaction, Embed, Color, ButtonStyle
from src.database.db import register_user, can_afford, deduct_coins, give_coins, get_balance
from src.casino.logic import draw_card, hand_total
from src.casino.types import BlackjackSession
from src.casino.wagers import validate_wager
from src.casino.rewards import CasinoResult, build_result_footer
from src.casino.events import emit_casino_event
from src.casino.modifiers import get_active_casino_modifiers, apply_casino_modifiers

active_sessions: dict[int, BlackjackSession] = {}


def _is_natural(hand: list) -> bool:
    return len(hand) == 2 and hand_total(hand) == 21


def render_blackjack_embed(session: BlackjackSession, footer: str | None = None) -> Embed:
    embed = Embed(title="🃏 Blackjack", color=Color.dark_purple())
    embed.add_field(
        name=f"Your Hand ({hand_total(session.player_hand)})",
        value=" ".join(session.player_hand),
        inline=True,
    )
    if session.finished:
        dealer_value = f"({hand_total(session.dealer_hand)})"
        dealer_cards = " ".join(session.dealer_hand)
    else:
        dealer_value = f"({hand_total([session.dealer_hand[0]])}+?)"
        dealer_cards = f"{session.dealer_hand[0]} ❓"
    embed.add_field(name=f"Dealer {dealer_value}", value=dealer_cards, inline=True)
    if footer:
        embed.set_footer(text=footer)
    return embed


async def resolve_blackjack(interaction: Interaction, session: BlackjackSession) -> tuple[str, str | None]:
    modifiers = await get_active_casino_modifiers(session.user_id, game="blackjack")

    player_natural = _is_natural(session.player_hand)
    dealer_natural = _is_natural(session.dealer_hand)

    if player_natural and dealer_natural:
        payout = session.bet
        await give_coins(session.user_id, payout)
        outcome = "push"
        result_text = "⚖️ Both have Blackjack — push! Wager returned."
        public_msg = None
    elif player_natural:
        payout = session.bet + math.floor(session.bet * 1.5)
        await give_coins(session.user_id, payout)
        outcome = "blackjack"
        result_text = f"🃏 Blackjack! You win {payout} coins (3:2)!"
        public_msg = (
            f"🃏 **{interaction.user.mention}** hit a natural Blackjack and won **{payout} coins**!"
        )
    else:
        dealer_hand = session.dealer_hand
        while hand_total(dealer_hand) < 17:
            dealer_hand.append(draw_card())

        player_total = hand_total(session.player_hand)
        dealer_total = hand_total(dealer_hand)
        effective_bet = session.bet * 2 if session.doubled_down else session.bet

        if dealer_total > 21 or player_total > dealer_total:
            payout = effective_bet * 2
            await give_coins(session.user_id, payout)
            outcome = "win"
            result_text = f"🎉 You win! (+{effective_bet} coins)"
            public_msg = None
        elif dealer_total == player_total:
            payout = effective_bet
            await give_coins(session.user_id, payout)
            outcome = "push"
            result_text = "⚖️ Push! Wager returned."
            public_msg = None
        else:
            payout = 0
            outcome = "loss"
            result_text = "😢 Dealer wins."
            public_msg = None

    wager = session.bet * 2 if session.doubled_down else session.bet
    net = payout - wager
    session.net = net

    base_result = CasinoResult(
        user_id=session.user_id,
        game="blackjack",
        wager=wager,
        payout=payout,
        net=net,
        outcome=outcome,
        metadata={
            "player_hand": session.player_hand,
            "dealer_hand": session.dealer_hand,
            "doubled_down": session.doubled_down,
        },
    )
    result_obj = apply_casino_modifiers(base_result, modifiers)

    balance = await get_balance(session.user_id)
    footer = build_result_footer(wager, payout, net, balance)

    await emit_casino_event("casino.blackjack.completed", result_obj)
    if outcome == "blackjack":
        await emit_casino_event("casino.blackjack.natural", result_obj)

    return result_text, footer, public_msg


class BlackjackView(ui.View):
    def __init__(self, session: BlackjackSession):
        super().__init__(timeout=60)
        self.session = session

    async def on_timeout(self):
        active_sessions.pop(self.session.user_id, None)

    @ui.button(label="Hit", style=ButtonStyle.green)
    async def hit(self, interaction: Interaction, _: ui.Button):
        session = active_sessions.get(interaction.user.id)
        if not session or session.finished:
            await interaction.response.send_message("❌ No active session.", ephemeral=True)
            return

        session.player_hand.append(draw_card())
        total = hand_total(session.player_hand)

        if total > 21:
            session.finished = True
            active_sessions.pop(session.user_id, None)
            wager = session.bet * 2 if session.doubled_down else session.bet
            balance = await get_balance(session.user_id)
            footer = build_result_footer(wager, 0, -wager, balance)

            modifiers = await get_active_casino_modifiers(session.user_id, game="blackjack")
            base_result = CasinoResult(
                user_id=session.user_id,
                game="blackjack",
                wager=wager,
                payout=0,
                net=-wager,
                outcome="bust",
                metadata={"player_hand": session.player_hand, "dealer_hand": session.dealer_hand},
            )
            apply_casino_modifiers(base_result, modifiers)
            await emit_casino_event("casino.blackjack.completed", base_result)

            await interaction.response.edit_message(
                embed=render_blackjack_embed(session, footer=f"💥 Bust! {footer}"), view=None
            )
        else:
            await interaction.response.edit_message(embed=render_blackjack_embed(session), view=self)

    @ui.button(label="Stand", style=ButtonStyle.blurple)
    async def stand(self, interaction: Interaction, _: ui.Button):
        session = active_sessions.get(interaction.user.id)
        if not session or session.finished:
            await interaction.response.send_message("❌ No active session.", ephemeral=True)
            return

        session.finished = True
        active_sessions.pop(session.user_id, None)
        result_text, footer, public_msg = await resolve_blackjack(interaction, session)
        await interaction.response.edit_message(
            embed=render_blackjack_embed(session, footer=f"{result_text} | {footer}"), view=None
        )
        if public_msg:
            await interaction.followup.send(public_msg, ephemeral=False)

    @ui.button(label="Double Down", style=ButtonStyle.danger)
    async def double_down(self, interaction: Interaction, _: ui.Button):
        session = active_sessions.get(interaction.user.id)
        if not session or session.finished:
            await interaction.response.send_message("❌ No active session.", ephemeral=True)
            return
        if session.doubled_down:
            await interaction.response.send_message("❌ Already doubled down.", ephemeral=True)
            return
        if not await can_afford(interaction.user.id, session.bet):
            await interaction.response.send_message("❌ Not enough coins to double down.", ephemeral=True)
            return

        await deduct_coins(interaction.user.id, session.bet)
        session.doubled_down = True
        session.player_hand.append(draw_card())
        session.finished = True
        active_sessions.pop(session.user_id, None)

        total = hand_total(session.player_hand)
        if total > 21:
            wager = session.bet * 2
            balance = await get_balance(session.user_id)
            footer = build_result_footer(wager, 0, -wager, balance)

            modifiers = await get_active_casino_modifiers(session.user_id, game="blackjack")
            base_result = CasinoResult(
                user_id=session.user_id,
                game="blackjack",
                wager=wager,
                payout=0,
                net=-wager,
                outcome="bust",
                metadata={"player_hand": session.player_hand, "dealer_hand": session.dealer_hand, "doubled_down": True},
            )
            apply_casino_modifiers(base_result, modifiers)
            await emit_casino_event("casino.blackjack.completed", base_result)

            await interaction.response.edit_message(
                embed=render_blackjack_embed(session, footer=f"💥 Bust! {footer}"), view=None
            )
        else:
            result_text, footer, public_msg = await resolve_blackjack(interaction, session)
            await interaction.response.edit_message(
                embed=render_blackjack_embed(session, footer=f"{result_text} | {footer}"), view=None
            )
            if public_msg:
                await interaction.followup.send(public_msg, ephemeral=False)


async def start_blackjack(interaction: Interaction):
    user_id = interaction.user.id
    if user_id in active_sessions:
        await interaction.response.send_message("❗ You already have an active Blackjack session.", ephemeral=True)
        return
    await register_user(user_id, interaction.user.name)

    class WagerModal(ui.Modal, title="Blackjack – Place Wager"):
        wager = ui.TextInput(label="Enter wager (5–500)", placeholder="e.g. 100", required=True)

        async def on_submit(self, interaction: Interaction):
            ok, result = await validate_wager(user_id, self.wager.value)
            if not ok:
                await interaction.response.send_message(result, ephemeral=True)
                return
            await deduct_coins(user_id, result)
            await play_blackjack(interaction, result)

    await interaction.response.send_modal(WagerModal())


async def play_blackjack(interaction: Interaction, bet: int):
    session = BlackjackSession(user_id=interaction.user.id, bet=bet)
    active_sessions[session.user_id] = session

    if _is_natural(session.player_hand):
        session.finished = True
        result_text, footer, public_msg = await resolve_blackjack(interaction, session)
        await interaction.response.send_message(
            embed=render_blackjack_embed(session, footer=f"{result_text} | {footer}"),
            view=None,
            ephemeral=True,
        )
        if public_msg:
            await interaction.followup.send(public_msg, ephemeral=False)
        return

    view = BlackjackView(session)
    await interaction.response.send_message(embed=render_blackjack_embed(session), view=view, ephemeral=True)
