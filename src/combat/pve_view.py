import random
from discord import Interaction, Embed, Color, ui, SelectOption, ButtonStyle
from src.combat.view import CombatView
from src.combat.pve_session import PVESession, AI_DIFFICULTIES, PVE_XP_REWARD, PVE_COIN_REWARD
from src.combat.session_manager import session_manager
from src.database.db import get_card, get_user_collection, get_all_cards, give_coins, update_xp_and_check_level


def create_hp_bar(current: int, maximum: int, length: int = 10) -> str:
    filled = int((current / maximum) * length) if maximum > 0 else 0
    filled = max(0, min(length, filled))  # Clamp between 0 and length
    return f"[{'█' * filled}{'░' * (length - filled)}] {current}/{maximum}"

class PVECombatView(CombatView):
    
    def __init__(self, session: PVESession, session_manager):
        super().__init__(session, session_manager)
        self.pve_session = session
        # Shorter timeout for PVE (30 minutes)
        self.timeout = 1800
    
    def build_embed(self) -> Embed:
        embed = Embed(title="⚔️ PVE Combat", color=Color.blurple())
        
        if self.pve_session.is_ai_turn():
            embed.add_field(name="Turn", value="👹 Enemy is thinking...", inline=False)
        else:
            embed.add_field(name="Your Turn", value="🎲 Roll the dice!", inline=False)
        
        player_card = self.pve_session.p1_card
        ai_card = self.pve_session.p2_card
        
        player_hp = self.pve_session.hp[self.pve_session.player_id]
        ai_hp = self.pve_session.hp[self.pve_session.ai_id]
        
        embed.add_field(
            name="👤 You",
            value=(
                f"**{player_card['name']}**\n"
                f"❤️ {create_hp_bar(player_hp, player_card['hp'])}\n"
                f"🗡️ ATK: {player_card['attack']}\n"
                f"🛡️ DEF: {player_card['defense']}"
            ),
            inline=True
        )
        
        difficulty_info = AI_DIFFICULTIES[self.pve_session.difficulty]
        embed.add_field(
            name=f"👹 ({difficulty_info['name']}) Enemy",
            value=(
                f"**{ai_card['name']}**\n"
                f"❤️ {create_hp_bar(ai_hp, ai_card['hp'])}\n"
                f"🗡️ ATK: {ai_card['attack']}\n"
                f"🛡️ DEF: {ai_card['defense']}"
            ),
            inline=True
        )
        
        return embed
    
    @ui.button(label="🎲 Roll", style=ButtonStyle.primary)
    async def roll_button(self, interaction: Interaction, button: ui.Button):
        user_id = interaction.user.id
        
        # Only player can click roll
        if user_id != self.pve_session.player_id:
            await interaction.response.send_message("❌ This isn't your battle!", ephemeral=True)
            return
        
        # Check if session is finished
        if self.pve_session.is_finished():
            await interaction.response.send_message("❌ This battle has ended!", ephemeral=True)
            return
        
        if self.pve_session.is_ai_turn():
            await interaction.response.send_message("❌ Wait for the Enemy to finish its turn!", ephemeral=True)
            return
        
        # Player rolls
        roll = random.randint(1, 6)
        damage, mod = self.pve_session.apply_roll(user_id, roll)
        
        description = f"🎲 You rolled a **{roll}**!\n"
        if mod == 0:
            description += "💨 You missed!"
        else:
            description += f"⚡ Hit modifier: ×{mod:.2f}\n💥 Damage dealt: **{damage}**"
        
        embed = self.build_embed()
        embed.add_field(name="🎯 Your Attack", value=description, inline=False)
        
        # Check if AI is defeated
        if self.pve_session.hp[self.pve_session.ai_id] <= 0:
            await self._handle_victory(interaction, embed)
            return
        
        await interaction.response.edit_message(embed=embed, view=self)
        
        # AI takes its turn
        try:
            ai_roll, ai_result = await self.pve_session.ai_take_turn()
            if ai_roll is not None:
                await self._handle_ai_turn(interaction, ai_roll, ai_result)
        except Exception as e:
            await interaction.followup.send("⚠️ AI turn failed, but the battle continues!", ephemeral=True)
    
    async def _handle_victory(self, interaction: Interaction, embed: Embed):
        coin_reward = PVE_COIN_REWARD.get(self.pve_session.difficulty, 0)
        xp_reward = PVE_XP_REWARD.get(self.pve_session.difficulty, 0)

        await give_coins(self.pve_session.player_id, coin_reward)
        new_level, level_coins = await update_xp_and_check_level(self.pve_session.player_id, xp_reward)

        embed.title = "🏆 Victory!"
        embed.color = Color.green()
        embed.add_field(
            name="🎉 Battle Complete!", 
            value=f"You have successfully defeated **{self.pve_session.p2_card['name']}**!",
            inline=False
        )
        embed.add_field(
            name="💰 Rewards",
            value=f"💎 {coin_reward} coins\n⭐ {xp_reward} XP",
            inline=False
        )

        if new_level:
            embed.add_field(
                name="🆙 Level Up!", 
                value=f"You reached **Level {new_level}** and earned **+{level_coins} coins**!", 
                inline=False
            )

        await self.session_manager.end_session(self.pve_session.player_id, reason="pve_victory")
        self.disable_all()

        await interaction.response.edit_message(embed=embed, view=self)
    
    async def _handle_ai_turn(self, interaction: Interaction, ai_roll: int, ai_result: tuple):
        ai_damage, ai_mod = ai_result
        
        ai_description = f"🎲 Enemy rolled a **{ai_roll}**!\n"
        if ai_mod == 0:
            ai_description += "💨 Enemy missed!"
        else:
            ai_description += f"⚡ Hit modifier: ×{ai_mod:.2f}\n💥 Damage to you: **{ai_damage}**"
        
        embed = self.build_embed()
        embed.add_field(name="🎯 Enemy Attack", value=ai_description, inline=False)
        
        # Check if player is defeated
        if self.pve_session.hp[self.pve_session.player_id] <= 0:
            embed.title = "💀 Defeat"
            embed.color = Color.red()
            embed.add_field(
                name="⚰️ Battle Lost", 
                value=(
                    f"**{self.pve_session.p2_card['name']}** has proven too powerful!\n"
                    f"🔄 Train harder and try again!"
                ),
                inline=False
            )                
            await self.session_manager.end_session(self.pve_session.player_id, reason="pve_defeat")
            self.disable_all()
        
        await interaction.edit_original_response(embed=embed, view=self)

class PVESetupView(ui.View):
    
    def __init__(self, user_id: int):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.selected_card = None
        self.selected_difficulty = "normal"
        
        # Add difficulty dropdown
        difficulty_options = [
            SelectOption(
                label=f"{diff['name']} - {diff['description']}", 
                value=key,
                default=(key == "normal")
            )
            for key, diff in AI_DIFFICULTIES.items()
        ]
        self.add_item(DifficultyDropdown(difficulty_options, self))
    
    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This isn't your setup menu.", ephemeral=True)
            return False
        return True
    
    @ui.button(label="📋 Select Card", style=ButtonStyle.secondary)
    async def select_card_button(self, interaction: Interaction, button: ui.Button):
        cards = await get_user_collection(self.user_id)
        if not cards:
            await interaction.response.send_message("❌ You have no cards to battle with!", ephemeral=True)
            return
        
        # Create card selection view
        view = PVECardSelectView(self.user_id, cards, self)
        embed = Embed(
            title="🃏 Choose Your Card",
            description="Select a card for PVE combat",
            color=Color.blurple()
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @ui.button(label="⚔️ Start Battle", style=ButtonStyle.success)
    async def start_battle_button(self, interaction: Interaction, button: ui.Button):
        if not self.selected_card:
            await interaction.response.send_message("❌ Please select a card first!", ephemeral=True)
            return
        
        await start_pve_combat(interaction, self.user_id, self.selected_card, self.selected_difficulty)

class DifficultyDropdown(ui.Select):
    
    def __init__(self, options, parent_view):
        super().__init__(placeholder="Choose difficulty", options=options)
        self.parent_view = parent_view
    
    async def callback(self, interaction: Interaction):
        self.parent_view.selected_difficulty = self.values[0]
        difficulty = AI_DIFFICULTIES[self.values[0]]
        await interaction.response.send_message(
            f"✅ Difficulty set to **{difficulty['name']}** - {difficulty['description']}", 
            ephemeral=True
        )

class PVECardSelectView(ui.View):
    
    def __init__(self, user_id: int, cards, parent_setup_view):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.parent_setup_view = parent_setup_view
        
        options = [
            SelectOption(
                label=f"{card[1]} [{card[2]}]", 
                value=str(card[0]),
                description=f"ATK:{card[3]} DEF:{card[4]} HP:{card[5]}"
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
            "attack": card[3],
            "defense": card[4],
            "hp": card[5],
        }
        
        self.parent_view.parent_setup_view.selected_card = card_data
        await interaction.response.send_message(f"✅ Selected **{card_data['name']}**!", ephemeral=True)

async def get_random_ai_card() -> dict:
    all_cards = await get_all_cards()
    if not all_cards:
        # Fallback card if no cards in database
        return {
            "id": 0,
            "name": "Training Dummy",
            "attack": 10,
            "defense": 5,
            "hp": 30
        }
    
    card = random.choice(all_cards)
    return {
        "id": card[0],
        "name": card[1], 
        "attack": card[3],
        "defense": card[4],
        "hp": card[5]
    }

async def start_pve_combat(interaction: Interaction, player_id: int, player_card: dict, difficulty: str):
    ai_card = await get_random_ai_card()
    
    session = PVESession(player_id, player_card, ai_card, difficulty)
    
    # Register session with manager
    session_manager.active_sessions[player_id] = session
    
    view = PVECombatView(session, session_manager)
    embed = view.build_embed()
    
    difficulty_info = AI_DIFFICULTIES[difficulty]
    embed.add_field(
        name="⚔️ Battle Started!", 
        value=f"Difficulty: **{difficulty_info['name']}**\n🎯 You go first!", 
        inline=False
    )
    
    await interaction.response.edit_message(content="", embed=embed, view=view)