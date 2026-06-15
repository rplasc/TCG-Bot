import asyncio
import random
from discord import Interaction, Embed, Color, ui, SelectOption, ButtonStyle

from src.combat.view import CombatView, ROLL_ANIM_DELAY
from src.combat import mechanics
from src.combat import hunt_events
from src.combat.hunt_session import HuntSession, LOCATIONS, get_location
from src.combat.session_manager import session_manager
from src.database.db import get_card, get_user_collection, get_all_cards, give_coins, update_xp_and_check_level


def create_hp_bar(current: int, maximum: int, length: int = 10) -> str:
    """Back-compat wrapper around the shared renderer."""
    return mechanics.hp_bar(current, maximum, length)


class HuntCombatView(CombatView):

    def __init__(self, session: HuntSession, session_manager):
        super().__init__(session, session_manager)
        self.hunt = session
        # Shorter timeout for hunts (30 minutes).
        self.timeout = 1800
        # Hunts have no forfeit button (you bank between waves instead).
        for item in list(self.children):
            if getattr(item, "custom_id", None) == "act_forfeit":
                self.remove_item(item)

    def build_embed(self, rolling: bool = False, thinking: bool = False, banner: str = "") -> Embed:
        loc = get_location(self.hunt.location)
        embed = Embed(title=f"{loc['emoji']} Hunt — {loc['name']}", color=Color.dark_green())

        if thinking:
            turn_text = "👹 The beast makes its move..."
        elif rolling:
            turn_text = "🎲 Rolling..."
        elif self.hunt.is_ai_turn():
            turn_text = "👹 The beast is circling..."
        else:
            turn_text = banner or "🎲 Your move!"
        embed.add_field(
            name=f"🌊 Wave {self.hunt.wave}",
            value=f"{turn_text}\n🎒 Haul: 💰 {self.hunt.pending_coins}  ⭐ {self.hunt.pending_xp}",
            inline=False,
        )

        _, player_val = self._fighter_field(self.hunt.player_id, "🏹 You")
        embed.add_field(name="🏹 You", value=player_val, inline=True)

        _, ai_val = self._fighter_field(self.hunt.ai_id, "👹 Beast")
        embed.add_field(name="👹 Beast", value=ai_val, inline=True)

        if self.session.log:
            embed.add_field(name="📜 Hunt Log", value="\n".join(self.session.log), inline=False)

        player_card = self.hunt.p1_card
        if player_card.get("image"):
            embed.set_thumbnail(url=player_card["image"])

        return embed

    async def _do_action(self, interaction: Interaction, action: str):
        user_id = interaction.user.id

        if user_id != self.hunt.player_id:
            await interaction.response.send_message("❌ This isn't your hunt!", ephemeral=True)
            return
        if self.hunt.is_finished():
            await interaction.response.send_message("❌ This wave is already over!", ephemeral=True)
            return
        if self.hunt.is_ai_turn():
            await interaction.response.send_message("❌ Wait for the beast to finish its turn!", ephemeral=True)
            return
        if action == "special" and not self.hunt.can_special(user_id):
            await interaction.response.send_message("❌ Your Special isn't charged yet!", ephemeral=True)
            return

        # Status tick at the start of the player's turn.
        tick = self.hunt.start_turn(user_id)
        if tick["skipped"]:
            self._refresh_buttons()
            await interaction.response.edit_message(embed=self.build_embed(), view=self)
            if self.hunt.hp[user_id] <= 0:
                await self._handle_defeat(interaction)
                return
            await self._run_ai_turn(interaction)
            return

        # Animated player action.
        await interaction.response.edit_message(embed=self.build_embed(rolling=True), view=self)
        await asyncio.sleep(ROLL_ANIM_DELAY)

        self.hunt.resolve_action(user_id, action)
        self._refresh_buttons()

        if self.hunt.hp[self.hunt.ai_id] <= 0:
            await self._handle_wave_cleared(interaction)
            return

        await interaction.edit_original_response(embed=self.build_embed(), view=self)
        await self._run_ai_turn(interaction)

    async def _run_ai_turn(self, interaction: Interaction):
        if self.hunt.is_finished():
            return
        await interaction.edit_original_response(embed=self.build_embed(thinking=True), view=self)
        try:
            await self.hunt.ai_take_turn()
        except Exception:
            await interaction.followup.send("⚠️ The beast hesitates — the hunt continues!", ephemeral=True)
            self._refresh_buttons()
            await interaction.edit_original_response(embed=self.build_embed(), view=self)
            return

        self._refresh_buttons()

        if self.hunt.hp[self.hunt.player_id] <= 0:
            await self._handle_defeat(interaction)
            return

        await interaction.edit_original_response(embed=self.build_embed(), view=self)

    async def _handle_wave_cleared(self, interaction: Interaction):
        """A beast is slain: bank the wave reward into the pot, roll an outcome event,
        and present the press-deeper / bank choice."""
        reward = self.hunt.wave_reward()
        event = hunt_events.roll_outcome_event(self.hunt)

        loc = get_location(self.hunt.location)
        embed = Embed(
            title=f"✅ Wave {self.hunt.wave} Cleared!",
            description=f"You felled **{self.hunt.p2_card['name']}** at {loc['emoji']} {loc['name']}.",
            color=Color.green(),
        )
        embed.add_field(
            name="💎 Wave Reward",
            value=f"💰 +{reward['coins']} coins\n⭐ +{reward['xp']} XP",
            inline=True,
        )
        embed.add_field(
            name="🎒 Total Haul (unbanked)",
            value=f"💰 {self.hunt.pending_coins} coins\n⭐ {self.hunt.pending_xp} XP",
            inline=True,
        )
        if event:
            embed.add_field(
                name=f"{event['emoji']} {event['title']}",
                value=event["desc"],
                inline=False,
            )
        embed.add_field(
            name="❤️ Your Condition",
            value=f"{mechanics.hp_bar(self.hunt.hp[self.hunt.player_id], self.hunt.p1_card['hp'])}\n"
                  f"{mechanics.energy_bar(self.hunt.energy[self.hunt.player_id])}",
            inline=False,
        )
        embed.set_footer(text="Press deeper for greater rewards — but death forfeits your haul.")

        view = HuntOutcomeView(self.hunt, self.session_manager)
        self.disable_all()
        await interaction.edit_original_response(embed=embed, view=view)

    async def _handle_defeat(self, interaction: Interaction):
        loc = get_location(self.hunt.location)
        embed = Embed(
            title="💀 The Hunt Ends",
            description=(
                f"**{self.hunt.p2_card['name']}** has bested you in {loc['emoji']} {loc['name']}.\n"
                f"The wilds claim your unbanked haul of "
                f"💰 {self.hunt.pending_coins} coins and ⭐ {self.hunt.pending_xp} XP."
            ),
            color=Color.red(),
        )
        embed.add_field(
            name="🗺️ Expedition",
            value=f"Waves cleared: **{self.hunt.waves_cleared}**\n🔄 Rest up and hunt again!",
            inline=False,
        )
        await self.session_manager.end_session(self.hunt.player_id, reason="hunt_defeat")
        self.disable_all()
        await interaction.edit_original_response(embed=embed, view=self)


class HuntOutcomeView(ui.View):
    """Between-wave choice: press deeper or bank the haul and leave."""

    def __init__(self, session: HuntSession, session_manager):
        super().__init__(timeout=180)
        self.hunt = session
        self.session_manager = session_manager

    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user.id != self.hunt.player_id:
            await interaction.response.send_message("❌ This isn't your hunt.", ephemeral=True)
            return False
        return True

    @ui.button(label="⚒️ Hunt Deeper", style=ButtonStyle.danger)
    async def hunt_deeper(self, interaction: Interaction, button: ui.Button):
        ai_card = await get_random_ai_card()
        self.hunt.next_wave(ai_card)

        view = HuntCombatView(self.hunt, self.session_manager)
        embed = view.build_embed(banner=f"⚔️ A **{self.hunt.p2_card['name']}** blocks your path!")
        await interaction.response.edit_message(embed=embed, view=view)

    @ui.button(label="🎒 Bank & Leave", style=ButtonStyle.success)
    async def bank_and_leave(self, interaction: Interaction, button: ui.Button):
        coins = self.hunt.pending_coins
        xp = self.hunt.pending_xp

        await give_coins(self.hunt.player_id, coins)
        new_level, level_coins = await update_xp_and_check_level(self.hunt.player_id, xp)

        loc = get_location(self.hunt.location)
        embed = Embed(
            title="🎒 Haul Secured!",
            description=f"You return from {loc['emoji']} {loc['name']} with your spoils.",
            color=Color.gold(),
        )
        embed.add_field(
            name="🏆 Expedition Summary",
            value=f"Waves cleared: **{self.hunt.waves_cleared}**\n"
                  f"💰 {coins} coins\n⭐ {xp} XP",
            inline=False,
        )
        if new_level:
            embed.add_field(
                name="🆙 Level Up!",
                value=f"You reached **Level {new_level}** and earned **+{level_coins} coins**!",
                inline=False,
            )

        await self.session_manager.end_session(self.hunt.player_id, reason="hunt_banked")
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)


# --- Setup: location + card selection ---------------------------------------

class HuntSetupView(ui.View):

    def __init__(self, user_id: int):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.selected_card = None
        self.selected_location = "tundra"

        location_options = [
            SelectOption(
                label=f"{loc['emoji']} {loc['name']}",
                value=key,
                description=loc["description"],
                default=(key == self.selected_location),
            )
            for key, loc in LOCATIONS.items()
        ]
        self.add_item(LocationDropdown(location_options, self))

    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This isn't your hunt menu.", ephemeral=True)
            return False
        return True

    @ui.button(label="📋 Select Card", style=ButtonStyle.secondary)
    async def select_card_button(self, interaction: Interaction, button: ui.Button):
        cards = await get_user_collection(self.user_id)
        if not cards:
            await interaction.response.send_message("❌ You have no cards to hunt with!", ephemeral=True)
            return

        view = HuntCardSelectView(self.user_id, cards, self)
        embed = Embed(
            title="🃏 Choose Your Hunter",
            description="Select a card to take on the hunt",
            color=Color.blurple(),
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @ui.button(label="🏹 Begin Hunt", style=ButtonStyle.success)
    async def start_hunt_button(self, interaction: Interaction, button: ui.Button):
        if not self.selected_card:
            await interaction.response.send_message("❌ Please select a card first!", ephemeral=True)
            return

        await start_hunt(interaction, self.user_id, self.selected_card, self.selected_location)


class LocationDropdown(ui.Select):

    def __init__(self, options, parent_view):
        super().__init__(placeholder="Choose a hunting ground", options=options)
        self.parent_view = parent_view

    async def callback(self, interaction: Interaction):
        self.parent_view.selected_location = self.values[0]
        loc = get_location(self.values[0])
        await interaction.response.send_message(
            f"✅ Hunting ground set to {loc['emoji']} **{loc['name']}** — {loc['description']}",
            ephemeral=True,
        )


class HuntCardSelectView(ui.View):

    def __init__(self, user_id: int, cards, parent_setup_view):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.parent_setup_view = parent_setup_view

        options = [
            SelectOption(
                label=f"{card[1]} [{card[2]}]",
                value=str(card[0]),
                description=f"ATK:{card[3]} DEF:{card[4]} HP:{card[5]}",
            )
            for card in cards[:25]  # Discord limit
        ]
        self.add_item(CardDropdown(options, self))

    async def interaction_check(self, interaction: Interaction) -> bool:
        return interaction.user.id == self.user_id


class CardDropdown(ui.Select):

    def __init__(self, options, parent_view):
        super().__init__(placeholder="Select your card", options=options)
        self.parent_view = parent_view

    async def callback(self, interaction: Interaction):
        card_id = int(self.values[0])
        card = await get_card(card_id)

        card_data = {
            "id": card[0],
            "name": card[1],
            "rarity": card[2],
            "attack": card[3],
            "defense": card[4],
            "hp": card[5],
            "image": card[6] if len(card) > 6 else None,
        }

        self.parent_view.parent_setup_view.selected_card = card_data
        await interaction.response.send_message(f"✅ Selected **{card_data['name']}**!", ephemeral=True)


async def get_random_ai_card() -> dict:
    all_cards = await get_all_cards()
    if not all_cards:
        return {
            "id": 0,
            "name": "Wild Beast",
            "rarity": "common",
            "attack": 10,
            "defense": 5,
            "hp": 30,
            "image": None,
        }

    card = random.choice(all_cards)
    return {
        "id": card[0],
        "name": card[1],
        "rarity": card[2],
        "attack": card[3],
        "defense": card[4],
        "hp": card[5],
        # get_all_cards() returns collection name at index 6, not an image URL.
        "image": None,
    }


async def start_hunt(interaction: Interaction, player_id: int, player_card: dict, location: str):
    ai_card = await get_random_ai_card()

    session = HuntSession(player_id, player_card, ai_card, location)

    # Register session with manager.
    session_manager.active_sessions[player_id] = session

    view = HuntCombatView(session, session_manager)
    loc = get_location(location)
    embed = view.build_embed(
        banner=f"🏹 You enter {loc['emoji']} **{loc['name']}** — a **{session.p2_card['name']}** appears!"
    )

    await interaction.response.edit_message(content="", embed=embed, view=view)
