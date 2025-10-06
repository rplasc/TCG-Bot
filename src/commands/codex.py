from discord import Interaction, Embed, Color, ui, ButtonStyle
from src.aclient import client
from src.database.db import get_all_cards, get_user_collection

CARDS_PER_PAGE = 10

class CodexView(ui.View):
    def __init__(self, interaction: Interaction, cards: list, owned_ids: list):
        super().__init__(timeout=60)
        self.cards = cards
        self.owned_ids = owned_ids
        self.interaction = interaction
        self.page = 1
        self.total_pages = (len(cards) + CARDS_PER_PAGE - 1) // CARDS_PER_PAGE

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
            embed.add_field(
                name=f"{owned} {card[1]} [{card[2]}]",
                value=f"ATK: {card[3]} | DEF: {card[4]} | HP: {card[5]}\nCollection: {card[6] or 'Unknown'}",
                inline=False
            )
            embed.set_footer(text=f"You own {len(self.owned_ids)} / {len(self.cards)} cards")
        return embed

    @ui.button(label="◀ Previous", style=ButtonStyle.primary)
    async def previous(self, interaction: Interaction, button: ui.Button):
        if interaction.user.id != self.interaction.user.id:
            await interaction.response.send_message("You can't control someone else's Codex.", ephemeral=True)
            return

        self.page -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self,)

    @ui.button(label="Next ▶", style=ButtonStyle.primary)
    async def next(self, interaction: Interaction, button: ui.Button):
        if interaction.user.id != self.interaction.user.id:
            await interaction.response.send_message("You can't control someone else's Codex.", ephemeral=True)
            return

        self.page += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

@client.tree.command(name="codex", description="View all cards in the game")
async def codex(interaction: Interaction):
    cards = await get_all_cards()
    user_cards = await get_user_collection(interaction.user.id)
    owned_ids = {card[0] for card in user_cards}

    if not cards:
        await interaction.response.send_message("No cards found in the database.")
        return

    view = CodexView(interaction, cards, owned_ids)
    embed = view.get_embed()
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
