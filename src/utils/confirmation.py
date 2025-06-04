from discord import Interaction, ButtonStyle, ui
from typing import Callable, Awaitable

class ConfirmActionView(ui.View):
    def __init__(
        self,
        user_id: int,
        action_fn: Callable[[Interaction], Awaitable[bool]],
        success_message: str,
        failure_message: str,
        timeout: int = 30,
    ):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.action_fn = action_fn
        self.success_message = success_message
        self.failure_message = failure_message

    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("⛔ You cannot perform this action.", ephemeral=True)
            return False
        return True

    @ui.button(label="✅ Confirm", style=ButtonStyle.danger)
    async def confirm(self, interaction: Interaction, button: ui.Button):
        success = await self.action_fn(interaction)
        if success:
            await interaction.response.edit_message(content=self.success_message, embed=None, view=None)
        else:
            await interaction.response.edit_message(content=self.failure_message, embed=None, view=None)
        self.stop()

    @ui.button(label="❌ Cancel", style=ButtonStyle.secondary)
    async def cancel(self, interaction: Interaction, button: ui.Button):
        await interaction.response.edit_message(content="❌ Action cancelled.", embed=None, view=None)
        self.stop()
