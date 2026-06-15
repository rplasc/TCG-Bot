import asyncio
import logging
from discord import ui, Interaction, Embed, ButtonStyle, Color

from src.combat.session import CombatSession, ACTION_STRIKE, ACTION_GUARD, ACTION_SPECIAL
from src.combat import mechanics
from src.database.db import give_coins, get_rank_id, update_rp_and_check_rank, add_win
from src.utils.ranks import calculate_match_multiplier, get_rp_change

logger = logging.getLogger(__name__)

# Constants
PVP_COIN_REWARD = 10
ROLL_ANIM_DELAY = 0.6  # seconds the "rolling…" frame is shown


def create_hp_bar(current: int, maximum: int, length: int = 10) -> str:
    """Back-compat wrapper around the shared renderer."""
    return mechanics.hp_bar(current, maximum, length)


class CombatView(ui.View):

    def __init__(self, session: CombatSession, session_manager):
        super().__init__(timeout=3600)
        self.session = session
        self.session_manager = session_manager
        self._refresh_buttons()

    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user.id not in [self.session.p1_id, self.session.p2_id]:
            await interaction.response.send_message("❌ You're not part of this battle.", ephemeral=True)
            return False
        return True

    def disable_all(self):
        for item in self.children:
            item.disabled = True

    def _refresh_buttons(self):
        """Enable/disable action buttons based on whose turn it is and energy."""
        turn_id = self.session.turn
        can_special = self.session.can_special(turn_id)
        for item in self.children:
            cid = getattr(item, "custom_id", None)
            if cid == "act_special":
                item.disabled = not can_special

    # --- Rendering -------------------------------------------------------

    def _fighter_field(self, user_id: int, label: str, mention: str = "") -> tuple:
        card = self.session.get_card(user_id)
        hp = self.session.hp[user_id]
        archetype = mechanics.get_archetype(card)
        icon = mechanics.ARCHETYPE_ICONS.get(archetype, "")
        status = mechanics.status_icons(self.session.statuses[user_id], self.session.shield[user_id])

        lines = []
        if mention:
            lines.append(mention)
        lines.append(f"**{card['name']}** {icon}{archetype}")
        lines.append(mechanics.hp_bar(hp, card["hp"]))
        lines.append(mechanics.energy_bar(self.session.energy[user_id]))
        lines.append(f"🗡️ {card['attack']}  🛡️ {card['defense']}")
        if status:
            lines.append(f"Status: {status}")
        return label, "\n".join(lines)

    def build_embed(self, rolling: bool = False, banner: str = "") -> Embed:
        embed = Embed(title="⚔️ Turn-Based Combat", color=Color.blurple())

        if rolling:
            turn_text = f"🎲 <@{self.session.turn}> is rolling..."
        else:
            turn_text = banner or f"<@{self.session.turn}>"
        embed.add_field(name="Turn", value=turn_text, inline=False)

        name1, val1 = self._fighter_field(self.session.p1_id, "🃏 Player 1", f"<@{self.session.p1_id}>")
        name2, val2 = self._fighter_field(self.session.p2_id, "🃏 Player 2", f"<@{self.session.p2_id}>")
        embed.add_field(name=name1, value=val1, inline=True)
        embed.add_field(name=name2, value=val2, inline=True)

        if self.session.log:
            embed.add_field(name="📜 Combat Log", value="\n".join(self.session.log), inline=False)

        card = self.session.get_card(self.session.turn)
        if card.get("image"):
            embed.set_thumbnail(url=card["image"])

        return embed

    # --- Action buttons --------------------------------------------------

    async def _do_action(self, interaction: Interaction, action: str):
        user_id = interaction.user.id

        if self.session.is_finished():
            await interaction.response.send_message("❌ This battle has ended!", ephemeral=True)
            return
        if not self.session.is_player_turn(user_id):
            await interaction.response.send_message("❌ It's not your turn!", ephemeral=True)
            return
        if action == ACTION_SPECIAL and not self.session.can_special(user_id):
            await interaction.response.send_message("❌ Your Special isn't charged yet!", ephemeral=True)
            return

        # Tick statuses at the start of the turn (burn / stun).
        tick = self.session.start_turn(user_id)
        if tick["skipped"]:
            self._refresh_buttons()
            embed = self.build_embed()
            if self.session.is_finished():
                await self._finish_and_edit(interaction, embed, responded=False)
                return
            await interaction.response.edit_message(embed=embed, view=self)
            return

        # Animated "rolling…" frame, then the resolved result.
        await interaction.response.edit_message(embed=self.build_embed(rolling=True), view=self)
        await asyncio.sleep(ROLL_ANIM_DELAY)

        self.session.resolve_action(user_id, action)
        self._refresh_buttons()
        embed = self.build_embed()

        if self.session.hp[self.session.p1_id] <= 0 or self.session.hp[self.session.p2_id] <= 0:
            await self._finish_and_edit(interaction, embed, responded=True)
            return

        await interaction.edit_original_response(embed=embed, view=self)

    @ui.button(label="⚔️ Strike", style=ButtonStyle.primary, custom_id="act_strike")
    async def strike_button(self, interaction: Interaction, button: ui.Button):
        await self._do_action(interaction, ACTION_STRIKE)

    @ui.button(label="🛡️ Guard", style=ButtonStyle.secondary, custom_id="act_guard")
    async def guard_button(self, interaction: Interaction, button: ui.Button):
        await self._do_action(interaction, ACTION_GUARD)

    @ui.button(label="✨ Special", style=ButtonStyle.success, custom_id="act_special")
    async def special_button(self, interaction: Interaction, button: ui.Button):
        await self._do_action(interaction, ACTION_SPECIAL)

    async def _finish_and_edit(self, interaction: Interaction, embed: Embed, responded: bool):
        await self._handle_battle_end(interaction, embed)
        if responded:
            await interaction.edit_original_response(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)

    async def _handle_battle_end(self, interaction: Interaction, embed: Embed):
        winner = self.session.p1_id if self.session.hp[self.session.p2_id] <= 0 else self.session.p2_id
        loser = self.session.p1_id if winner != self.session.p1_id else self.session.p2_id

        try:
            winner_rank_id = await get_rank_id(winner)
            loser_rank_id = await get_rank_id(loser)
            multiplier = calculate_match_multiplier(winner_rank_id, loser_rank_id)

            # Rewards for winner
            await give_coins(winner, PVP_COIN_REWARD)
            rp_gain = get_rp_change(winner_rank_id, True, multiplier)
            new_rank_winner = await update_rp_and_check_rank(winner, rp_gain)
            await add_win(winner)

            # RP loss for loser (rp_loss is negative)
            rp_loss = get_rp_change(loser_rank_id, False, multiplier)
            new_rank_loser = await update_rp_and_check_rank(loser, rp_loss)

            embed.title = "🏆 Combat Ended"
            embed.color = Color.green()
            embed.add_field(
                name="👊 Battle Complete",
                value=f"<@{winner}> has won the fight!\n💰 Earned {PVP_COIN_REWARD} coins",
                inline=False
            )
            embed.add_field(
                name="📊 RP Change",
                value=f"<@{winner}> +{rp_gain} RP\n<@{loser}> -{abs(rp_loss)} RP",
                inline=False
            )

            if new_rank_winner:
                embed.add_field(
                    name="🆙 Rank Up!",
                    value=f"<@{winner}> has ranked up to **{new_rank_winner}**!",
                    inline=False
                )

            if new_rank_loser:
                embed.add_field(
                    name="📉 Rank Demotion",
                    value=f"<@{loser}> has been demoted to **{new_rank_loser}**.",
                    inline=False
                )

            await self.session_manager.end_session(interaction.user.id, reason="victory")
            self.disable_all()

        except Exception:
            logger.exception(
                "Error processing PVP rewards (winner=%s, loser=%s)", winner, loser
            )
            embed.add_field(
                name="⚠️ Error",
                value="There was an error processing rewards. Please contact an admin.",
                inline=False
            )
            await self.session_manager.end_session(interaction.user.id, reason="error")
            self.disable_all()

    @ui.button(label="🏳️ Forfeit", style=ButtonStyle.danger, custom_id="act_forfeit")
    async def forfeit_button(self, interaction: Interaction, button: ui.Button):
        # Show confirmation
        view = ForfeitConfirmView(self, interaction.user.id)
        await interaction.response.send_message(
            "⚠️ Are you sure you want to forfeit? You will lose the match!",
            view=view,
            ephemeral=True
        )


class ForfeitConfirmView(ui.View):

    def __init__(self, parent_view: CombatView, user_id: int):
        super().__init__(timeout=30)
        self.parent_view = parent_view
        self.user_id = user_id

    @ui.button(label="✅ Yes, Forfeit", style=ButtonStyle.danger)
    async def confirm_forfeit(self, interaction: Interaction, button: ui.Button):
        """Confirm forfeit."""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This isn't your decision.", ephemeral=True)
            return

        loser = interaction.user.id
        winner = self.parent_view.session.get_opponent(loser)
        self.parent_view.session.completed = True

        embed = Embed(
            title="🏳️ Combat Forfeited",
            description=f"<@{loser}> has forfeited.\n<@{winner}> wins by forfeit!",
            color=Color.red()
        )

        await self.parent_view.session_manager.end_session(loser, reason="forfeit")
        self.parent_view.disable_all()

        # Edit the original combat message
        try:
            await interaction.message.channel.last_message.edit(embed=embed, view=self.parent_view)
        except Exception:
            pass

        await interaction.response.edit_message(content="✅ You have forfeited the match.", view=None)

    @ui.button(label="❌ Cancel", style=ButtonStyle.secondary)
    async def cancel_forfeit(self, interaction: Interaction, button: ui.Button):
        await interaction.response.edit_message(content="Forfeit cancelled. Continue fighting!", view=None)
