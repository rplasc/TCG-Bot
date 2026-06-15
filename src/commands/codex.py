from discord import Interaction, Embed, Color, ui, ButtonStyle, app_commands
from src.aclient import client
from src.database.db import get_all_cards, get_user_collection
from src.shop.logic import RARITY_EMOJIS
from src.utils.ui import error_embed

CARDS_PER_PAGE = 10

class CodexView(ui.View):
    def __init__(self, interaction: Interaction, cards: list, owned_ids: list):
        super().__init__(timeout=60)
        self.cards = cards
        self.owned_ids = owned_ids
        self.interaction = interaction
        self.page = 1
        self.total_pages = max(1, (len(cards) + CARDS_PER_PAGE - 1) // CARDS_PER_PAGE)

        self.update_buttons()

    def update_buttons(self):
        self.previous.disabled = self.page == 1
        self.next.disabled = self.page == self.total_pages

    def get_embed(self):
        start = (self.page - 1) * CARDS_PER_PAGE
        end = start + CARDS_PER_PAGE
        embed = Embed(title=f"📘 Codex — Page {self.page}/{self.total_pages}", color=Color.purple())

        for card in self.cards[start:end]:
            owned = "✅" if card[0] in self.owned_ids else "❌"
            emoji = RARITY_EMOJIS.get(str(card[2]).lower(), "")
            embed.add_field(
                name=f"{owned} {emoji} {card[1]} [{str(card[2]).title()}]",
                value=f"ATK: {card[3]} | DEF: {card[4]} | HP: {card[5]}\nCollection: {card[6] or 'Unknown'}",
                inline=False
            )
        embed.set_footer(text=f"You own {len(self.owned_ids)} / {len(self.cards)} shown cards")
        return embed

    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user.id != self.interaction.user.id:
            await interaction.response.send_message(
                "You can't control someone else's Codex.", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True

    @ui.button(label="◀ Previous", style=ButtonStyle.primary)
    async def previous(self, interaction: Interaction, button: ui.Button):
        self.page -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @ui.button(label="Next ▶", style=ButtonStyle.primary)
    async def next(self, interaction: Interaction, button: ui.Button):
        self.page += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)


async def codex_search_autocomplete(interaction: Interaction, current: str):
    cards = await get_all_cards()
    current = current.lower()
    return [
        app_commands.Choice(name=card[1], value=card[1])
        for card in cards if current in card[1].lower()
    ][:25]


@client.tree.command(name="codex", description="View all cards in the game")
@app_commands.describe(search="Filter by card name or collection")
@app_commands.autocomplete(search=codex_search_autocomplete)
async def codex(interaction: Interaction, search: str = None):
    cards = await get_all_cards()
    user_cards = await get_user_collection(interaction.user.id)
    owned_ids = {card[0] for card in user_cards}

    if not cards:
        await interaction.response.send_message(
            embed=error_embed("No cards found in the database.", title="Empty Codex"),
            ephemeral=True
        )
        return

    if search:
        term = search.lower()
        cards = [c for c in cards if term in str(c[1]).lower() or term in str(c[6] or "").lower()]
        if not cards:
            await interaction.response.send_message(
                embed=error_embed(f"No cards match **{search}**.", title="No matches"),
                ephemeral=True
            )
            return

    view = CodexView(interaction, cards, owned_ids)
    embed = view.get_embed()
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
