import random
import asyncio
from discord import Interaction, Embed, Color, ui, ButtonStyle
from src.db.db import can_afford, deduct_coins, give_coins, register_user, user_owns_card, add_to_user_collection, get_balance
from src.shop.logic import draw_card
from src.shop.logic import RARITY_EMOJIS
from src.casino.types import SlotSession

SLOT_EMOJIS = ["🍒", "🍋", "🍇", "🔔", "⭐", "💎"]  # Common to rare
JACKPOT_EMOJI = "💎"

def spin_slots():
    return [random.choice(SLOT_EMOJIS) for _ in range(3)]

def is_jackpot(result):
    return all(symbol == JACKPOT_EMOJI for symbol in result)

def is_pair(result):
    return any(result.count(symbol) == 2 for symbol in result)

async def run_slot_spin(interaction: Interaction, session: SlotSession, edit=False):
    user_id = session.user_id
    await register_user(user_id, interaction.user.name)

    if not await can_afford(user_id, session.wager):
        await interaction.response.send_message("❌ Not enough coins to play.", ephemeral=True)
        return

    await deduct_coins(user_id, session.wager)

    # Step 1: Show fake spin
    fake_embed = Embed(title="🎰 Slot Machine", description="Spinning...", color=Color.dark_gray())
    fake_embed.add_field(name="Spin", value="🔄 | 🔄 | 🔄", inline=False)

    if edit:
        await interaction.response.edit_message(embed=fake_embed, view=None)
    else:
        await interaction.response.send_message(embed=fake_embed, ephemeral=True)

    await asyncio.sleep(1.5)

    # Step 2: Real result
    result = spin_slots()
    embed = Embed(title="🎰 Slot Machine", color=Color.gold())
    embed.add_field(name="Spin", value=" | ".join(result), inline=False)

    reward = 0
    card_message = None

    if is_jackpot(result):
        reward = 50
        await give_coins(user_id, reward)
        card = await draw_card()
        if card and not await user_owns_card(user_id, card[0]):
            await add_to_user_collection(user_id, card[0])
            emoji = RARITY_EMOJIS.get(card[2].lower(), "")
            card_message = f"+{reward} coins\n🃏 You won: {emoji} {card[1]}"
        else:
            card_message = f"+{reward} coins (duplicate card)"
        embed.add_field(name="🎉 JACKPOT!", value=card_message, inline=False)

    elif is_pair(result):
        reward = 10
        await give_coins(user_id, reward)
        embed.add_field(name="✨ Match!", value=f"+{reward} coins", inline=False)

    else:
        embed.add_field(name="😢", value="No win this time.", inline=False)

    session.spins += 1
    view = SlotView(session)

    balance = await get_balance(user_id)
    embed.set_footer(text=f"💰 Your balance: {balance} coins")

    if edit:
        await interaction.edit_original_response(embed=embed, view=view)
    else:
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

class SlotView(ui.View):
    def __init__(self, session: SlotSession):
        super().__init__(timeout=60)
        self.session = session 

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True

    @ui.button(label="🔁 Respin", style=ButtonStyle.green)
    async def respin(self, interaction: Interaction, button: ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message("❌ Not your session.", ephemeral=True)
            return
        
        if self.session.spins >= 5:
            await interaction.response.send_message("⏳ You've hit the spin limit for this session.", ephemeral=True)
            self.stop()
            return

        await run_slot_spin(interaction, self.session, edit=True)

async def play_slots(interaction: Interaction):
    session = SlotSession(user_id=interaction.user.id)
    await run_slot_spin(interaction, session, edit=False)
