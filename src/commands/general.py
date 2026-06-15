import difflib
from discord import Interaction, app_commands
from src.aclient import client
from src.database.db import get_card_by_name, get_all_cards, get_user_collection
from src.utils.ui import card_embed, error_embed


async def card_name_autocomplete(interaction: Interaction, current: str):
    cards = await get_all_cards()
    current = current.lower()
    return [
        app_commands.Choice(name=card[1], value=card[1])
        for card in cards if current in card[1].lower()
    ][:25]


@client.tree.command(name="view_card", description="View a card by name")
@app_commands.autocomplete(name=card_name_autocomplete)
async def view_card_command(interaction: Interaction, name: str):
    card = await get_card_by_name(name)
    if card:
        owned_ids = {c[0] for c in await get_user_collection(interaction.user.id)}
        embed = card_embed(card, owned=card[0] in owned_ids)
        await interaction.response.send_message(embed=embed)
        return

    # Suggest the closest matches on a miss.
    all_names = [c[1] for c in await get_all_cards()]
    suggestions = difflib.get_close_matches(name, all_names, n=3, cutoff=0.5)
    message = f"No card named **{name}** was found."
    if suggestions:
        message += "\n\nDid you mean: " + ", ".join(f"**{s}**" for s in suggestions) + "?"
    await interaction.response.send_message(
        embed=error_embed(message, title="Card not found"), ephemeral=True
    )
