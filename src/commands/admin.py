from discord import Interaction, Embed, Color, Member
from src.database.db import (
    add_card, get_card_by_name, delete_card_by_name, update_card_by_name,
    create_collection, delete_collection_by_name,
    get_balance, get_recent_ledger, get_ledger_source_totals, get_economy_totals, get_user_budgets,
    reset_database,
)
from src.aclient import client
from src.utils.permissions import has_role
from src.utils.confirmation import ConfirmActionView
from src.utils.time import get_current_date_str

RARITIES = ["common", "uncommon", "rare", "epic", "legendary"]


def _fmt_amount(n: int) -> str:
    return f"+{n:,}" if n >= 0 else f"{n:,}"


@client.tree.command(name="economy_report", description="View currency ledger and reward-budget data")
@has_role("ChopperDevTeam")
async def economy_report_command(interaction: Interaction, user: Member = None):
    if user is None:
        # Global economy overview.
        created, destroyed = await get_economy_totals()
        net = created - destroyed
        embed = Embed(title="📊 Economy Report — Global", color=Color.gold())
        embed.add_field(
            name="Coin Flow (all-time, ledgered)",
            value=(f"🟢 Created: **{created:,}**\n"
                   f"🔴 Destroyed: **{destroyed:,}**\n"
                   f"⚖️ Net: **{_fmt_amount(net)}**"),
            inline=False,
        )
        totals = await get_ledger_source_totals()
        if totals:
            lines = [f"`{_fmt_amount(total):>10}` · {src} ({count})" for src, total, count in totals]
            embed.add_field(name="By Source (net · count)", value="\n".join(lines)[:1024], inline=False)
        else:
            embed.add_field(name="By Source", value="No ledger entries yet.", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    # Per-user report.
    balance = await get_balance(user.id)
    created, destroyed = await get_economy_totals(user.id)
    embed = Embed(title=f"📊 Economy Report — {user.display_name}", color=Color.blue())
    embed.add_field(name="💰 Balance", value=f"{balance:,}", inline=True)
    embed.add_field(name="🟢 Earned", value=f"{created:,}", inline=True)
    embed.add_field(name="🔴 Spent", value=f"{destroyed:,}", inline=True)

    budgets = await get_user_budgets(user.id, get_current_date_str())
    if budgets:
        embed.add_field(
            name="Today's Reward Budget",
            value="\n".join(f"{cat}: **{amt:,}**" for cat, amt in budgets),
            inline=False,
        )

    recent = await get_recent_ledger(user.id, limit=12)
    if recent:
        lines = []
        for amount, balance_after, source, created_at in recent:
            ts = created_at[5:16].replace("T", " ") if created_at else ""
            lines.append(f"`{_fmt_amount(amount):>8}` {source} → {balance_after:,}  _{ts}_")
        embed.add_field(name="Recent Ledger", value="\n".join(lines)[:1024], inline=False)
    else:
        embed.add_field(name="Recent Ledger", value="No ledger entries yet.", inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)

@client.tree.command(name="add_card", description="Add card to database")
@has_role("ChopperDevTeam")
async def add_card_command(
    interaction: Interaction,
    name: str,
    rarity: str,
    attack: int,
    defense: int,
    hp: int,
    image: str,
    collection: str = None
):
    try:
        if rarity.lower() not in RARITIES:
            await interaction.response.send_message(
                f"❌ Invalid rarity. Must be one of: {', '.join(RARITIES)}"
            )
            return
        
        if not image.startswith("http"):
            await interaction.response.send_message("❌ Image must be a valid URL starting with http/https.", ephemeral=True)
            return

        await add_card(name, rarity.lower(), attack, defense, hp, image, collection_name=collection)

        await interaction.response.send_message(f"Card '{name}' added to collection '{collection or 'Default Collection'}'.")
    except ValueError as e:
        await interaction.response.send_message(str(e))

@client.tree.command(name="delete_card", description="Delete a card by name with confirmation")
@has_role("ChopperDevTeam")
async def delete_card_command(interaction: Interaction, name: str):
    embed = Embed(
        title="🗑️ Confirm Card Deletion",
        description=f"Are you sure you want to delete the card named `{name}`?",
        color=Color.red()
    )

    async def perform_deletion(_: Interaction) -> bool:
        return await delete_card_by_name(name)

    view = ConfirmActionView(
        user_id=interaction.user.id,
        action_fn=perform_deletion,
        success_message=f"✅ Card '{name}' has been deleted.",
        failure_message=f"❌ Card '{name}' was not found or could not be deleted."
    )

    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

@client.tree.command(name="edit_card", description="Edit an existing card")
@has_role("ChopperDevTeam")
async def edit_card_command(
    interaction: Interaction,
    name: str,
    attack: int = None,
    defense: int = None,
    hp: str = None,
    image: str = None,
    rarity: str = None,
    collection: str = None
):
    try:
        await update_card_by_name(
            name,
            attack=attack,
            defense=defense,
            hp=hp,
            image=image,
            rarity=rarity.lower() if rarity else None,
            collection_name=collection
        )

        card = await get_card_by_name(name)
        if not card:
            await interaction.response.send_message(f"✅ Card updated but not found afterward. Please check the name.", ephemeral=True)
            return

        embed = Embed(title=f"{card[1]} (#{card[0]})", color=Color.orange())
        embed.add_field(name="Rarity", value=card[2])
        embed.add_field(name="Attack", value=card[3])
        embed.add_field(name="Defense", value=card[4])
        embed.add_field(name="HP", value=card[5])

        image_url = card[6]
        if isinstance(image_url, str) and image_url.startswith("http"):
            embed.set_image(url=image_url)

        await interaction.response.send_message(content=f"✅ Card '{name}' updated.", embed=embed)

    except ValueError as e:
        await interaction.response.send_message(f"❌ {str(e)}", ephemeral=True)

@client.tree.command(name="create_collection", description="Create a new card collection")
@has_role("ChopperDevTeam")
async def createcollection(interaction: Interaction, name: str):
    await create_collection(name)
    await interaction.response.send_message(f"✅ Collection '{name}' created.")

@client.tree.command(name="delete_collection", description="Delete a collection by name")
@has_role("ChopperDevTeam")
async def delete_collection_command(interaction: Interaction, name: str):
    embed = Embed(
        title="⚠️ Confirm Collection Deletion",
        description=f"Are you sure you want to delete the collection `{name}`?",
        color=Color.red()
    )

    async def perform_deletion(_: Interaction):
        return await delete_collection_by_name(name)

    view = ConfirmActionView(
        user_id=interaction.user.id,
        action_fn=perform_deletion,
        success_message=f"✅ Collection '{name}' has been deleted.",
        failure_message=f"❌ Collection '{name}' was not found or couldn't be deleted.",
    )

    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

@client.tree.command(name="reset", description="Reset the database (wipes all player data)")
@has_role("ChopperDevTeam")
async def reset_command(interaction: Interaction, keep_cards: bool = True):
    if keep_cards:
        scope = "All player data (balances, collections, streaks, casino stats, ledger) will be wiped. **Card and collection definitions will be kept.**"
    else:
        scope = "**Everything** will be wiped — all player data **and** every card and collection definition."

    embed = Embed(
        title="⚠️ Confirm Database Reset",
        description=f"{scope}\n\nThis cannot be undone. Are you sure?",
        color=Color.red(),
    )

    async def perform_reset(_: Interaction) -> bool:
        try:
            await reset_database(keep_cards=keep_cards)
            return True
        except Exception as e:
            print(f"Error resetting database: {e}")
            return False

    success_message = (
        "✅ Database reset. Player data wiped; cards kept."
        if keep_cards
        else "✅ Database reset. Player data, cards, and collections wiped."
    )

    view = ConfirmActionView(
        user_id=interaction.user.id,
        action_fn=perform_reset,
        success_message=success_message,
        failure_message="❌ Database reset failed. Check the logs.",
    )

    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)