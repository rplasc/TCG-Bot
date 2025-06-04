from discord import Interaction, app_commands

def has_role(role_name: str):
    async def predicate(interaction: Interaction) -> bool:
        if not interaction.user.guild_permissions.administrator:
            member = interaction.guild.get_member(interaction.user.id)
            if member is None:
                member = await interaction.guild.fetch_member(interaction.user.id)
            return any(role.name == role_name for role in member.roles)
        return True  # allow admins by default
    return app_commands.check(predicate)
