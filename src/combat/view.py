import random
from discord import ui, Interaction, Embed, ButtonStyle, Color
from src.combat.session import CombatSession
from src.combat.session_manager import session_manager

class CombatView(ui.View):
    def __init__(self, session: CombatSession, session_manager):
        super().__init__(timeout=3600)
        self.session = session
        self.session_manager = session_manager

    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user.id not in [self.session.p1_id, self.session.p2_id]:
            await interaction.response.send_message("❌ You’re not part of this battle.", ephemeral=True)
            return False
        return True

    def disable_all(self):
        for item in self.children:
            item.disabled = True

    def build_embed(self):
        embed = Embed(title="⚔️ Turn-Based Combat", color=Color.blurple())

        embed.add_field(name="Your Turn", value=f"<@{self.session.turn}>", inline=False)

        p1 = self.session.p1_id
        p2 = self.session.p2_id

        card1 = self.session.p1_card
        card2 = self.session.p2_card

        embed.add_field(
            name="🃏 Player 1",
            value=(
                f"<@{p1}>\n"
                f"**{card1['name']}**\n"
                f"❤️ HP: {self.session.hp[p1]}\n"
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
                f"❤️ HP: {self.session.hp[p2]}\n"
                f"🗡️ ATK: {card2['attack']}\n"
                f"🛡️ DEF: {card2['defense']}"
            ),
            inline=True
        )

        return embed

    @ui.button(label="🎲 Roll", style=ButtonStyle.primary)
    async def roll_button(self, interaction: Interaction, button: ui.Button):
        user_id = interaction.user.id

        if not self.session.is_player_turn(user_id):
            await interaction.response.send_message("❌ It's not your turn!", ephemeral=True)
            return

        roll = random.randint(1, 6)
        damage, mod = self.session.apply_roll(user_id, roll)

        description = f"🎲 You rolled a {roll}!\n"
        if mod == 0:
            description += "You missed!"
        else:
            description += f"Hit modifier: ×{mod:.2f}\nDamage dealt: **{damage}**"

        embed = self.build_embed()
        embed.add_field(name="🎯 Result", value=description, inline=False)

        if self.session.hp[self.session.p1_id] == 0 or self.session.hp[self.session.p2_id] == 0:
            winner = self.session.p1_id if self.session.hp[self.session.p2_id] == 0 else self.session.p2_id
            embed.title = "🏆 Combat Ended"
            embed.color = Color.green()
            user = await interaction.client.fetch_user(winner)
            embed.add_field(
                name="👊 Battle Complete",
                value=f"<@{user.name}> has won the fight!"
            )

            await self.session_manager.end_session(user_id, reason="victory")
            self.disable_all()

        await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(label="🏳️ Forfeit", style=ButtonStyle.danger)
    async def forfeit_button(self, interaction: Interaction, button: ui.Button):
        loser = interaction.user.id
        winner = self.session.get_opponent(loser)
        self.session.completed = True

        embed = Embed(
            title="🏳️ Combat Forfeited",
            description=f"<@{loser}> has forfeited. <@{winner}> wins!",
            color=Color.red()
        )
        await self.session_manager.end_session(loser, reason="forfeit")
        self.disable_all()
        await interaction.response.edit_message(embed=embed, view=self)
