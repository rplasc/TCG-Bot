import os
import time
from collections import defaultdict
import discord
from src.aclient import client
from src.commands import cards, general, leaderboard, packs, collection, codex, currency, level, casino, trades, combat
from src.database.db import give_coins, register_user, init_db
from src.combat.session_manager import session_manager

# Track last rewarded message timestamp
message_cooldowns = defaultdict(lambda: 0)
COOLDOWN_SECONDS = 10

reaction_cooldowns = defaultdict(lambda: 0)


@client.event
async def on_ready():
    await client.tree.sync()
    await init_db()

    GUILD = discord.Object(id=955464847028531280)
    await client.tree.sync(guild=GUILD)
    print(f'Logged in as {client.user.name}')

    commands = await client.tree.fetch_commands(guild=GUILD)
    print("Registered Commands:")
    for command in commands:
        print(f"- {command.name}")
    
    session_manager.start_cleanup_task()

@client.event
async def on_close():
    await session_manager.shutdown()

# Gives users coins based on messages
def calculate_message_reward(message: str) -> int:
    length = len(message)
    if length < 100:
        return 1
    elif length < 300:
        return 2
    elif length < 500:
        return 3
    else:
        return 5

@client.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    user_id = message.author.id
    username = message.author.name
    now = time.time()

    # Check cooldown
    if now - message_cooldowns[user_id] < COOLDOWN_SECONDS:
        return

    message_cooldowns[user_id] = now

    await register_user(user_id, username)

    reward = calculate_message_reward(message.content)
    await give_coins(user_id, reward)

# Rewards bonus for reactions
@client.event
async def on_reaction_add(reaction: discord.Reaction, user: discord.User):
    if user.bot or reaction.message.author.bot:
        return

    now = time.time()
    author = reaction.message.author
    if now - reaction_cooldowns[author.id] < COOLDOWN_SECONDS:
        return

    reaction_cooldowns[author.id] = now

    await register_user(author.id, author.name)
    await give_coins(author.id, 3)

@client.tree.error
async def on_app_command_error(interaction: discord.Interaction, error):
    if isinstance(error, discord.app_commands.CheckFailure):
        await interaction.response.send_message("🚫 You don't have permission to use this command.", ephemeral=True)
    else:
        raise error

client.run(os.getenv('DISCORD_BOT_TOKEN'))