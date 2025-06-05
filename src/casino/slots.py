import random
from discord import Interaction, Embed, Color
from src.db.db import can_afford, deduct_coins, give_coins, register_user, user_owns_card, add_to_user_collection
from src.shop.logic import draw_card
from src.shop.logic import RARITY_EMOJIS

SLOT_EMOJIS = ["🍒", "🍋", "🍇", "🔔", "⭐", "💎"]  # Common to rare
JACKPOT_EMOJI = "💎"
WAGER_AMOUNT = 5

def spin_slots():
    return [random.choice(SLOT_EMOJIS) for _ in range(3)]

def is_jackpot(result):
    return all(symbol == JACKPOT_EMOJI for symbol in result)

def is_pair(result):
    return any(result.count(symbol) == 2 for symbol in result)

async def play_slots(interaction: Interaction):
    user_id = interaction.user.id
    await register_user(user_id, interaction.user.name)

    if not await can_afford(user_id, WAGER_AMOUNT):
        await interaction.response.send_message("❌ Not enough coins to play.", ephemeral=True)
        return

    await deduct_coins(user_id, WAGER_AMOUNT)
    result = spin_slots()

    embed = Embed(title="🎰 Slot Machine", color=Color.gold())
    embed.add_field(name="Spin", value=" | ".join(result), inline=False)

    if is_jackpot(result):
        # Jackpot: win coins + card
        reward = 25
        await give_coins(user_id, reward)
        card = await draw_card()
        if card and not await user_owns_card(user_id, card[0]):
            await add_to_user_collection(user_id, card[0])
            emoji = RARITY_EMOJIS.get(card[2].lower(), "")
            embed.add_field(name="🎉 JACKPOT!", value=f"+{reward} coins\n🃏 You won a card: {emoji} {card[1]}", inline=False)
        else:
            embed.add_field(name="🎉 JACKPOT!", value=f"+{reward} coins (card was a duplicate)", inline=False)

    elif is_pair(result):
        reward = 10
        await give_coins(user_id, reward)
        embed.add_field(name="✨ Match!", value=f"+{reward} coins", inline=False)

    else:
        embed.add_field(name="😢", value="No win this time.", inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)
