"""Shared UI helpers for building consistent embeds across commands.

Card tuples used throughout the bot follow the convention:
    [0]=id, [1]=name, [2]=rarity, [3]=attack, [4]=defense, [5]=hp, [6]=image|collection
Because index 6 varies (image url for some queries, collection name for others),
``card_embed`` only treats it as an image when it looks like an http(s) url.
"""

from discord import Embed, Color, ui, Interaction, ButtonStyle
from src.shop.logic import RARITY_EMOJIS

# Rarity -> embed accent color, used to color per-card embeds.
RARITY_COLORS = {
    "common": Color.light_grey(),
    "rare": Color.blue(),
    "epic": Color.purple(),
    "legendary": Color.gold(),
}


def rarity_color(rarity):
    """Return the accent color for a rarity, defaulting to teal."""
    return RARITY_COLORS.get((rarity or "").lower(), Color.teal())


def card_embed(card, *, title_prefix="🃏", footer=None, owned=None, image=None):
    """Build a standard embed for a single card.

    ``card`` is a DB row tuple (see module docstring). ``owned`` adds an owned/
    unowned indicator to the title when not ``None``. ``image`` overrides the
    image url; otherwise index 6 is used if it looks like a url.
    """
    rarity = card[2]
    emoji = RARITY_EMOJIS.get((rarity or "").lower(), "")
    owned_tag = ""
    if owned is True:
        owned_tag = " ✅"
    elif owned is False:
        owned_tag = " ❌"

    embed = Embed(
        title=f"{title_prefix} {card[1]} {emoji}{owned_tag}".strip(),
        description=(
            f"**Rarity:** {str(rarity).title()}\n"
            f"**ATK:** {card[3]} | **DEF:** {card[4]} | **HP:** {card[5]}"
        ),
        color=rarity_color(rarity),
    )

    if image is None and len(card) > 6 and isinstance(card[6], str) and card[6].startswith("http"):
        image = card[6]
    if image:
        embed.set_image(url=image)

    if footer:
        embed.set_footer(text=footer)
    return embed


def progress_bar(current, total, segments=20, filled="🟩", empty="⬜"):
    """Return an emoji progress bar string for ``current``/``total``."""
    if total <= 0:
        return empty * segments
    ratio = max(0.0, min(1.0, current / total))
    fill = int(segments * ratio)
    return filled * fill + empty * (segments - fill)


def error_embed(message, title="Something went wrong"):
    """Build a consistent red error embed."""
    return Embed(title=f"❌ {title}", description=message, color=Color.red())


class FieldPaginator(ui.View):
    """A reusable paginated embed for a flat list of fields.

    ``entries`` is a list of ``(name, value)`` tuples rendered as embed fields,
    ``per_page`` per page. Only ``user_id`` may use the navigation buttons.
    """

    def __init__(self, *, user_id, title, entries, color=None, per_page=10,
                 description=None, inline=False, footer_suffix=None):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.title = title
        self.entries = entries
        self.color = color or Color.blurple()
        self.per_page = per_page
        self.description = description
        self.inline = inline
        self.footer_suffix = footer_suffix
        self.page = 1
        self.total_pages = max(1, (len(entries) + per_page - 1) // per_page)
        # Hide navigation entirely when everything fits on one page.
        if self.total_pages == 1:
            self.clear_items()
        else:
            self._update_buttons()

    def _update_buttons(self):
        self.previous.disabled = self.page == 1
        self.next.disabled = self.page == self.total_pages

    def get_embed(self):
        start = (self.page - 1) * self.per_page
        page_entries = self.entries[start:start + self.per_page]
        embed = Embed(title=self.title, description=self.description, color=self.color)
        for name, value in page_entries:
            embed.add_field(name=name, value=value, inline=self.inline)
        footer = f"Page {self.page}/{self.total_pages}"
        if self.footer_suffix:
            footer += f" • {self.footer_suffix}"
        embed.set_footer(text=footer)
        return embed

    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This isn't your menu.", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True

    @ui.button(label="◀ Previous", style=ButtonStyle.primary)
    async def previous(self, interaction: Interaction, button: ui.Button):
        self.page -= 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @ui.button(label="Next ▶", style=ButtonStyle.primary)
    async def next(self, interaction: Interaction, button: ui.Button):
        self.page += 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)
