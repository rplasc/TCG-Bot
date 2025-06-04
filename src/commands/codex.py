from discord import app_commands, Interaction, Embed, Color, ui, ButtonStyle, Object
from src.aclient import client
from src.db.db import get_all_cards

GUILD = Object(id=955464847028531280)

CARDS_PER_PAGE = 5

class CodexView(ui.View):
    def __init__(self, interaction: Interaction, cards: list):
        super().__init__(timeout=60)
        self.cards = cards
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
            embed.add_field(
                name=f"{card[1]} [#{card[0]}]",
                value=f"Rarity: {card[2]}\nATK: {card[3]} | DEF: {card[4]}\nCollection: {card[5] or 'Unknown'}",
                inline=False
            )
        return embed

    @ui.button(label="◀ Previous", style=ButtonStyle.primary)
    async def previous(self, interaction: Interaction, button: ui.Button):
        if interaction.user.id != self.interaction.user.id:
            await interaction.response.send_message("You can't control someone else's Codex.", ephemeral=True)
            return

        self.page -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @ui.button(label="Next ▶", style=ButtonStyle.primary)
    async def next(self, interaction: Interaction, button: ui.Button):
        if interaction.user.id != self.interaction.user.id:
            await interaction.response.send_message("You can't control someone else's Codex.", ephemeral=True)
            return

        self.page += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)


@client.tree.command(name="codex", description="View all cards in the game", guild=GUILD)
async def codex(interaction: Interaction):
    cards = await get_all_cards()

    if not cards:
        await interaction.response.send_message("No cards found in the database.")
        return

    view = CodexView(interaction, cards)
    embed = view.get_embed()
    await interaction.response.send_message(embed=embed, view=view)