import random
from discord import ui, Interaction, Embed, ButtonStyle, Color
from src.combat.session import CombatSession
from src.database.db import give_coins, get_rank_id, update_rp_and_check_rank, add_win
from src.utils.ranks import calculate_match_multiplier, get_rp_change

# Constants
PVP_COIN_REWARD = 10

def create_hp_bar(current: int, maximum: int, length: int = 10) -> str:
    filled = int((current / maximum) * length) if maximum > 0 else 0
    filled = max(0, min(length, filled))  # Clamp between 0 and length
    return f"[{'█' * filled}{'░' * (length - filled)}] {current}/{maximum}"

class CombatView(ui.View):
    
    def __init__(self, session: CombatSession, session_manager):
        super().__init__(timeout=3600)
        self.session = session
        self.session_manager = session_manager

    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user.id not in [self.session.p1_id, self.session.p2_id]:
            await interaction.response.send_message("❌ You're not part of this battle.", ephemeral=True)
            return False
        return True

    def disable_all(self):
        for item in self.children:
            item.disabled = True

    def build_embed(self) -> Embed:
        embed = Embed(title="⚔️ Turn-Based Combat", color=Color.blurple())

        embed.add_field(name="Your Turn", value=f"<@{self.session.turn}>", inline=False)

        p1 = self.session.p1_id
        p2 = self.session.p2_id

        card1 = self.session.p1_card
        card2 = self.session.p2_card
        
        p1_hp = self.session.hp[p1]
        p2_hp = self.session.hp[p2]

        embed.add_field(
            name="🃏 Player 1",
            value=(
                f"<@{p1}>\n"
                f"**{card1['name']}**\n"
                f"❤️ {create_hp_bar(p1_hp, card1['hp'])}\n"
                f"🗡️ ATK: {card1['attack']}\n"
                f"🛡️ DEF: {card1['defense']}"
            ),
            inline=True
        )

        embed.add_field(
            name="🃏 Player 2",
            value=(
                f"<@{p2}>\n"
                f"**{card2['name']}**\n"
                f"❤️ {create_hp_bar(p2_hp, card2['hp'])}\n"
                f"🗡️ ATK: {card2['attack']}\n"
                f"🛡️ DEF: {card2['defense']}"
            ),
            inline=True
        )

        return embed

    @ui.button(label="🎲 Roll", style=ButtonStyle.primary)
    async def roll_button(self, interaction: Interaction, button: ui.Button):
        user_id = interaction.user.id
        
        # Check if session is finished
        if self.session.is_finished():
            await interaction.response.send_message("❌ This battle has ended!", ephemeral=True)
            return

        if not self.session.is_player_turn(user_id):
            await interaction.response.send_message("❌ It's not your turn!", ephemeral=True)
            return

        roll = random.randint(1, 6)
        damage, mod = self.session.apply_roll(user_id, roll)

        description = f"🎲 You rolled a **{roll}**!\n"
        if mod == 0:
            description += "💨 You missed!"
        else:
            description += f"⚡ Hit modifier: ×{mod:.2f}\n💥 Damage dealt: **{damage}**"

        embed = self.build_embed()
        embed.add_field(name="🎯 Result", value=description, inline=False)

        # Check if battle is over
        if self.session.hp[self.session.p1_id] == 0 or self.session.hp[self.session.p2_id] == 0:
            await self._handle_battle_end(interaction, embed)
            return

        await interaction.response.edit_message(embed=embed, view=self)

    async def _handle_battle_end(self, interaction: Interaction, embed: Embed):
        winner = self.session.p1_id if self.session.hp[self.session.p2_id] == 0 else self.session.p2_id
        loser = self.session.p1_id if winner != self.session.p1_id else self.session.p2_id

        try:
            winner_rank_id = await get_rank_id(winner)
            loser_rank_id = await get_rank_id(loser)
            multiplier = calculate_match_multiplier(winner_rank_id, loser_rank_id)

            # Rewards for winner
            await give_coins(winner, PVP_COIN_REWARD)
            rp_gain = get_rp_change(winner, True, multiplier)
            new_rank_winner = await update_rp_and_check_rank(winner, rp_gain)
            await add_win(winner)

            # RP loss for loser
            rp_loss = get_rp_change(loser, False, multiplier)
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
                value=f"<@{winner}> +{rp_gain} RP\n<@{loser}> -{rp_loss} RP",
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

        except Exception as e:
            embed.add_field(
                name="⚠️ Error",
                value="There was an error processing rewards. Please contact an admin.",
                inline=False
            )
            await self.session_manager.end_session(interaction.user.id, reason="error")
            self.disable_all()

        await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(label="🏳️ Forfeit", style=ButtonStyle.danger)
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
        except:
            pass
        
        await interaction.response.edit_message(content="✅ You have forfeited the match.", view=None)
    
    @ui.button(label="❌ Cancel", style=ButtonStyle.secondary)
    async def cancel_forfeit(self, interaction: Interaction, button: ui.Button):
        await interaction.response.edit_message(content="Forfeit cancelled. Continue fighting!", view=None)