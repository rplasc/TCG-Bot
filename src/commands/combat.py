import logging
from discord import app_commands, Interaction, Embed, Color, ui, Member, SelectOption, ButtonStyle
from src.aclient import client
from src.combat.view import CombatView
from src.combat.pve_view import PVESetupView, AI_DIFFICULTIES
from src.combat.session_manager import session_manager
from src.database.db import get_card, get_user_collection

CARD_SELECT_TIMEOUT = 120
CHALLENGE_TIMEOUT = 30

async def send_card_selection(channel, user_id: int):
    cards = await get_user_collection(user_id)
    if not cards:
        await channel.send(f"<@{user_id}> has no cards to battle with.")
        return

    view = CardSelectView(user_id, cards)
    embed = Embed(
        title="🃏 Choose Your Card",
        description=f"<@{user_id}>, select a card and press Ready",
        color=Color.blurple()
    )
    await channel.send(embed=embed, view=view)

class CardSelectView(ui.View):
    
    def __init__(self, target_user_id: int, cards):
        super().__init__(timeout=CARD_SELECT_TIMEOUT)
        self.target_user_id = target_user_id
        self.cards = cards
        self.selected_card_id = None
        self.ready = False

        options = [
            SelectOption(
                label=f"{card[1]} [{card[2]}]",
                value=str(card[0]),
                description=f"ATK:{card[3]} DEF:{card[4]} HP:{card[5]}"
            )
            for card in cards[:25]  # Discord dropdown limit
        ]
        self.dropdown = CardDropdown(options, self)
        self.add_item(self.dropdown)
        self.add_item(ReadyButton(self))

    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user.id != self.target_user_id:
            await interaction.response.send_message("❌ This isn't your selection to make.", ephemeral=True)
            return False
        return True
    
    async def on_timeout(self):
        session_manager.clear_card_selection(self.target_user_id)
        
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
        
        session_manager.set_card_selection(self.parent_view.target_user_id, card_data)
        self.parent_view.selected_card_id = card_id
        await interaction.response.send_message("✅ Card selected. Click 'Ready' to confirm.", ephemeral=True)

class ReadyButton(ui.Button):
    
    def __init__(self, parent_view):
        super().__init__(label="✅ Ready", style=ButtonStyle.success)
        self.parent_view = parent_view

    async def callback(self, interaction: Interaction):
        if not self.parent_view.selected_card_id:
            await interaction.response.send_message("❌ Please select a card first.", ephemeral=True)
            return

        self.parent_view.ready = True
        self.parent_view.clear_items()

        user_id = self.parent_view.target_user_id
        card = session_manager.get_card_selection(user_id)

        embed = Embed(
            title=f"✅ {interaction.user.display_name} is Ready!",
            description=f"**Selected Card:** {card['name']}\n"
                        f"🗡️ Attack: {card['attack']}\n"
                        f"🛡️ Defense: {card['defense']}\n"
                        f"❤️ HP: {card['hp']}",
            color=Color.green()
        )

        if card.get("image"):
            embed.set_thumbnail(url=card["image"])

        await interaction.message.edit(embed=embed, view=None)

        # Mark this player ready and only start once BOTH players have confirmed
        session_manager.set_player_ready(user_id)
        partner = session_manager.get_combat_partner(user_id)

        if partner is not None and session_manager.are_both_ready(user_id, partner):
            await start_combat(interaction.channel, user_id, partner)
        else:
            await interaction.channel.send(f"🕒 Waiting for the other player to be ready...")

async def start_combat(channel, user1: int, user2: int):
    card1 = session_manager.get_card_selection(user1)
    card2 = session_manager.get_card_selection(user2)
    
    if not card1 or not card2:
        await channel.send("❌ Error: One or both players don't have a card selected.")
        return
    
    session = session_manager.create_session(user1, user2, card1, card2)
    view = CombatView(session, session_manager)
    embed = view.build_embed()
    
    embed.add_field(
        name="⚔️ Battle Begin!",
        value=f"<@{session.turn}> goes first!",
        inline=False
    )

    await channel.send(content="⚔️ Combat has begun!", embed=embed, view=view)

    # Clear card selections
    session_manager.clear_card_selection(user1)
    session_manager.clear_card_selection(user2)

class ChallengeResponseView(ui.View):
    
    def __init__(self, challenger_id: int, opponent_id: int):
        super().__init__(timeout=CHALLENGE_TIMEOUT)
        self.challenger_id = challenger_id
        self.opponent_id = opponent_id

    @ui.button(label="✅ Accept", style=ButtonStyle.success)
    async def accept(self, interaction: Interaction, button: ui.Button):
        if interaction.user.id != self.opponent_id:
            await interaction.response.send_message("❌ You're not the challenged player.", ephemeral=True)
            return
        
        # Double-check both users are still available
        if session_manager.is_user_in_session(self.challenger_id) or \
           session_manager.is_user_in_session(self.opponent_id):
            await interaction.response.edit_message(
                content="❌ One of the players is now in another battle.",
                view=None
            )
            session_manager.clear_pending_challenge(self.opponent_id)
            return

        await interaction.response.edit_message(
            content="✅ Challenge accepted! Awaiting card selections...",
            view=None
        )
        
        session_manager.clear_pending_challenge(self.opponent_id)

        # Pair the two players so readiness can be matched within this challenge
        session_manager.set_combat_pair(self.challenger_id, self.opponent_id)

        await send_card_selection(interaction.channel, self.challenger_id)
        await send_card_selection(interaction.channel, self.opponent_id)

    @ui.button(label="❌ Decline", style=ButtonStyle.danger)
    async def decline(self, interaction: Interaction, button: ui.Button):
        if interaction.user.id != self.opponent_id:
            await interaction.response.send_message("❌ You're not the challenged player.", ephemeral=True)
            return
        
        session_manager.clear_pending_challenge(self.opponent_id)
        await interaction.response.edit_message(
            content=f"❌ <@{self.opponent_id}> declined the challenge.",
            view=None
        )
    
    async def on_timeout(self):
        session_manager.clear_pending_challenge(self.opponent_id)

@client.tree.command(name="challenge", description="Challenge another player to a card battle!")
@app_commands.describe(opponent="The user you want to challenge")
async def challenge(interaction: Interaction, opponent: Member):
    user_id = interaction.user.id
    opponent_id = opponent.id

    if user_id == opponent_id:
        await interaction.response.send_message("❌ You can't challenge yourself.", ephemeral=True)
        return
    
    if opponent.bot:
        await interaction.response.send_message("❌ You can't challenge a bot. Use `/pve` instead!", ephemeral=True)
        return

    # Prevent multiple active sessions
    if session_manager.is_user_in_session(user_id):
        await interaction.response.send_message("❌ You're already in a battle!", ephemeral=True)
        return
    
    if session_manager.is_user_in_session(opponent_id):
        await interaction.response.send_message("❌ That player is already in a battle!", ephemeral=True)
        return
    
    # Check if opponent has a pending challenge
    if session_manager.has_pending_challenge(opponent_id):
        await interaction.response.send_message(
            "❌ That player already has a pending challenge. Please wait!",
            ephemeral=True
        )
        return
    
    # Set pending challenge
    session_manager.set_pending_challenge(user_id, opponent_id)

    # Ask for confirmation from the opponent
    embed = Embed(
        title="⚔️ Challenge Issued!",
        description=f"<@{user_id}> has challenged <@{opponent_id}> to battle!",
        color=Color.orange()
    )
    view = ChallengeResponseView(user_id, opponent_id)
    await interaction.response.send_message(content=f"<@{opponent_id}>", embed=embed, view=view)
    
@client.tree.command(name="pve", description="Fight against an AI opponent!")
async def pve_command(interaction: Interaction):
    user_id = interaction.user.id
    
    # Check if user is already in a session
    if session_manager.is_user_in_session(user_id):
        await interaction.response.send_message("❌ You're already in a battle!", ephemeral=True)
        return
    
    view = PVESetupView(user_id)
    embed = Embed(
        title="🎮 PVE Combat Setup",
        description="Choose your difficulty and card to fight the AI!",
        color=Color.blue()
    )
    
    embed.add_field(
        name="🎯 Difficulties",
        value="\n".join([
            f"**{diff['name']}**: {diff['description']}"
            for diff in AI_DIFFICULTIES.values()
        ]),
        inline=False
    )
    
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
