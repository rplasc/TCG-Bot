import os
import discord
from src.aclient import client
from src.commands import cards, general, packs, collection, codex, currency, xp
from src.db.db import give_coins, register_user, init_db

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

# Gives users coins based on messages
def calculate_message_reward(message: str) -> int:
    length = len(message)
    if length < 50:
        return 1
    elif length < 100:
        return 5
    elif length < 300:
        return 10
    else:
        return 15

@client.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    user_id = message.author.id
    username = message.author.name

    await register_user(user_id, username)

    reward = calculate_message_reward(message.content)
    await give_coins(user_id, reward)

# Rewards bonus for reactions
@client.event
async def on_reaction_add(reaction: discord.Reaction, user: discord.User):
    # Ignore bot reactions
    if user.bot or reaction.message.author.bot:
        return

    message_author = reaction.message.author
    message_author_id = message_author.id

    await register_user(message_author_id, message_author.name)

    reward = 2
    await give_coins(message_author_id, reward)

@client.tree.error
async def on_app_command_error(interaction: discord.Interaction, error):
    if isinstance(error, discord.app_commands.CheckFailure):
        await interaction.response.send_message("🚫 You don't have permission to use this command.", ephemeral=True)
    else:
        raise error

client.run(os.getenv('DISCORD_BOT_TOKEN'))