from discord import Interaction, Embed, Color,Object
from src.database.db import add_card, get_card_by_name, delete_card_by_name, update_card_by_name, create_collection, delete_collection_by_name
from src.aclient import client
from src.utils.permissions import has_role
from src.utils.confirmation import ConfirmActionView

RARITIES = ["common", "uncommon", "rare", "epic", "legendary"]

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