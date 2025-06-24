from discord import app_commands, Interaction, Embed, Object, Color, ui, Member, SelectOption, ButtonStyle
from src.aclient import client
from src.combat.view import CombatView
from src.combat.pve_view import PVESetupView, AI_DIFFICULTIES
from src.combat.session_manager import session_manager
from src.database.db import get_card, get_user_collection

GUILD = Object(id=955464847028531280)

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
    def __init__(self, target_user_id, cards):
        super().__init__(timeout=120)
        self.target_user_id = target_user_id
        self.cards = cards
        self.selected_card_id = None
        self.ready = False

        options = [
            SelectOption(label=f"{card[1]} [{card[2]}]", value=str(card[0]))
            for card in cards
        ]
        self.dropdown = CardDropdown(options, self)
        self.add_item(self.dropdown)
        self.add_item(ReadyButton(self))

    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user.id != self.target_user_id:
            await interaction.response.send_message("❌ This isn’t your selection to make.", ephemeral=True)
            return False
        return True
        
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

        # Check if both players are ready
        ready_players = list(session_manager.get_ready_players())
        if len(ready_players) >= 2:
            challenger_id, opponent_id = ready_players[0], ready_players[1]
            if challenger_id != opponent_id:
                await start_combat(interaction.channel, challenger_id, opponent_id)
        else:
            await interaction.channel.send(f"🕒 Waiting for the other player to be ready...")

async def start_combat(channel, user1, user2):
    card1 = session_manager.get_card_selection(user1)
    card2 = session_manager.get_card_selection(user2)
    
    session = session_manager.create_session(user1, user2, card1, card2)
    view = CombatView(session, session_manager)
    embed = view.build_embed()

    await channel.send(content="⚔️ Combat has begun!", embed=embed, view=view)

    # Clear card selections
    session_manager.clear_card_selection(user1)
    session_manager.clear_card_selection(user2)

# 🔁 Challenge Accept/Decline View
class ChallengeResponseView(ui.View):
    def __init__(self, challenger_id, opponent_id):
        super().__init__(timeout=30)
        self.challenger_id = challenger_id
        self.opponent_id = opponent_id
        self.challenger_card = None
        self.opponent_card = None

    @ui.button(label="✅ Accept", style=ButtonStyle.success)
    async def accept(self, interaction: Interaction, button: ui.Button):
        if interaction.user.id != self.opponent_id:
            await interaction.response.send_message("❌ You're not the challenged player.", ephemeral=True)
            return

        await interaction.response.edit_message(
            content="✅ Challenge accepted! Awaiting card selections...",
            view=None
        )

        challenger = interaction.guild.get_member(self.challenger_id)
        opponent = interaction.user

        await send_card_selection(interaction.channel, self.challenger_id)
        await send_card_selection(interaction.channel, self.opponent_id)

    @ui.button(label="❌ Decline", style=ButtonStyle.danger)
    async def decline(self, interaction: Interaction, button: ui.Button):
        if interaction.user.id != self.opponent_id:
            await interaction.response.send_message("❌ You're not the challenged player.", ephemeral=True)
            return
        await interaction.response.edit_message(content="❌ Challenge declined.", view=None)

@client.tree.command(name="challenge", description="Challenge another player to a card battle!", guild=GUILD)
@app_commands.describe(opponent="The user you want to challenge")
async def challenge(interaction: Interaction, opponent: Member):
    user_id = interaction.user.id
    opponent_id = opponent.id

    if user_id == opponent_id:
        await interaction.response.send_message("❌ You can't challenge yourself.", ephemeral=True)
        return

    # Prevent multiple active sessions
    if session_manager.is_user_in_session(user_id) or session_manager.is_user_in_session(opponent_id):
        await interaction.response.send_message("❌ One of you is already in a battle.", ephemeral=True)
        return

    # Ask for confirmation from the opponent
    embed = Embed(
        title="⚔️ Challenge Issued!",
        description=f"<@{user_id}> has challenged <@{opponent_id}> to battle!",
        color=Color.orange()
    )
    view = ChallengeResponseView(user_id, opponent_id)
    await interaction.response.send_message(content=f"<@{opponent_id}>", embed=embed, view=view)

@client.tree.command(name="pve", description="Fight against an AI opponent!", guild=GUILD)
async def pve_command(interaction: Interaction):
    user_id = interaction.user.id
    
    # Check if user is already in a session
    if session_manager.is_user_in_session(user_id):
        await interaction.response.send_message("❌ You're already in a battle!", ephemeral=True)
        return
    
    view = PVESetupView(user_id)
    embed = Embed(
        title="🤖 PVE Combat Setup",
        description="Choose your difficulty and card to fight the AI!",
        color=Color.blue()
    )
    
    embed.add_field(
        name="🎯 Difficulties",
        value="\n".join([f"**{diff['name']}**: {diff['description']}" for diff in AI_DIFFICULTIES.values()]),
        inline=False
    )
    
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)