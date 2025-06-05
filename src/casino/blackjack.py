from dataclasses import dataclass, field
from discord import ui, Interaction, Embed, Color, ButtonStyle
from src.db.db import register_user, can_afford, deduct_coins, give_coins
from src.casino.logic import draw_card, hand_total
from src.casino.types import BlackjackSession

# Key: user_id → Value: BlackjackSession
active_sessions = {}

def render_blackjack_embed(session: BlackjackSession, footer=None):
    embed = Embed(title="🃏 Blackjack", color=Color.dark_purple())
    embed.add_field(name="Your Hand", value=f"{' '.join(session.player_hand)} = {hand_total(session.player_hand)}", inline=True)
    dealer_visible = ' '.join(session.dealer_hand if session.finished else [session.dealer_hand[0], "❓"])
    embed.add_field(name="Dealer", value=dealer_visible, inline=True)
    if footer:
        embed.set_footer(text=footer)
    return embed

async def resolve_blackjack(interaction: Interaction, session: BlackjackSession):
    dealer_hand = session.dealer_hand
    while hand_total(dealer_hand) < 17:
        dealer_hand.append(draw_card())

    player_total = hand_total(session.player_hand)
    dealer_total = hand_total(dealer_hand)

    if dealer_total > 21 or player_total > dealer_total:
        await give_coins(session.user_id, session.bet * 2)
        return f"🎉 You win! (+{session.bet} coins)"
    elif dealer_total == player_total:
        await give_coins(session.user_id, session.bet)
        return f"⚖️ Tie! Your bet was returned."
    else:
        return f"😢 Dealer wins. You lost your bet."
    
class BlackjackView(ui.View):
    def __init__(self, session: BlackjackSession):
        super().__init__(timeout=60)
        self.session = session

    async def on_timeout(self):
        session = active_sessions.get(self.session.user_id)
        if session:
            session.finished = True
            active_sessions.pop(session.user_id, None)

    @ui.button(label="Hit", style=ButtonStyle.green)
    async def hit(self, interaction: Interaction, button: ui.Button):
        session = active_sessions.get(interaction.user.id)

        if not session or session.finished:
            await interaction.response.send_message("❌ No active session.", ephemeral=True)
            return

        self.session.player_hand.append(draw_card())
        total = hand_total(self.session.player_hand)

        if total > 21:
            self.session.finished = True
            active_sessions.pop(self.session.user_id, None)
            await interaction.response.edit_message(embed=render_blackjack_embed(self.session, "💥 Bust! You lose."), view=None)
        else:
            await interaction.response.edit_message(embed=render_blackjack_embed(self.session), view=self)

    @ui.button(label="Stand", style=ButtonStyle.blurple)
    async def stand(self, interaction: Interaction, button: ui.Button):
        session = active_sessions.get(interaction.user.id)

        if not session or session.finished:
            await interaction.response.send_message("❌ No active session.", ephemeral=True)
            return

        self.session.finished = True
        active_sessions.pop(self.session.user_id, None)
        result = await resolve_blackjack(interaction, self.session)
        await interaction.response.edit_message(embed=render_blackjack_embed(self.session, result), view=None)

async def start_blackjack(interaction: Interaction):
    user_id = interaction.user.id
    if user_id in active_sessions:
        await interaction.response.send_message("❗ You're already in a Blackjack game.", ephemeral=True)
        return
    await register_user(user_id, interaction.user.name)

    class WagerModal(ui.Modal, title="Place Your Wager"):
        wager = ui.TextInput(label="Enter amount to bet", placeholder="e.g. 100", required=True)

        async def on_submit(self, interaction: Interaction):
            try:
                bet = int(self.wager.value)
                if bet <= 0:
                    raise ValueError
            except ValueError:
                await interaction.response.send_message("❌ Invalid amount.", ephemeral=True)
                return

            if not await can_afford(user_id, bet):
                await interaction.response.send_message("❌ You don’t have enough coins.", ephemeral=True)
                return

            await deduct_coins(user_id, bet)
            await play_blackjack(interaction, bet)

    await interaction.response.send_modal(WagerModal())

async def play_blackjack(interaction: Interaction, bet: int):
    session = BlackjackSession(user_id=interaction.user.id, bet=bet)
    active_sessions[session.user_id] = session
    view = BlackjackView(session)
    embed = render_blackjack_embed(session)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
