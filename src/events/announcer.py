"""Background task that announces event rotations.

The active event(s) are computed deterministically from the date, so this task
only needs to detect when the period key changes and post once. The last
announced key is persisted in the ``event_state`` table so restarts don't
re-announce. On first ever run (no stored key) we seed silently.
"""

import asyncio
import os
from typing import Optional

from discord import Embed, Color

from src.events.schedule import period_key
from src.events.service import active_events, format_effects
from src.database.db import get_last_announced_event_key, set_last_announced_event_key

EVENT_ANNOUNCE_CHANNEL_ID = int(os.getenv("EVENT_ANNOUNCE_CHANNEL_ID", "0"))
CHECK_INTERVAL = 300  # seconds


def _announce_embed(events) -> Embed:
    embed = Embed(
        title="🎉 New Events Are Live!",
        description="The event rotation just changed. Here's what's active now:",
        color=Color.purple(),
    )
    if not events:
        embed.description = "No events are active right now."
        return embed
    for e in events:
        embed.add_field(
            name=f"{e.emoji} {e.name} ({e.cadence})",
            value=f"{e.description}\n*{format_effects(e)}*",
            inline=False,
        )
    return embed


class EventAnnouncer:
    def __init__(self):
        self.task: Optional[asyncio.Task] = None

    def start(self, client):
        if self.task is None or self.task.done():
            self.task = asyncio.create_task(self._loop(client))

    async def _loop(self, client):
        while True:
            try:
                await self._check_and_announce(client)
                await asyncio.sleep(CHECK_INTERVAL)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[event announcer] {e}")
                await asyncio.sleep(CHECK_INTERVAL)

    async def _check_and_announce(self, client):
        key = period_key()
        last = await get_last_announced_event_key()
        if key == last:
            return

        # First-ever run: seed silently so restarts don't spam the channel.
        if last is None:
            await set_last_announced_event_key(key)
            return

        if EVENT_ANNOUNCE_CHANNEL_ID:
            channel = client.get_channel(EVENT_ANNOUNCE_CHANNEL_ID)
            if channel:
                await channel.send(embed=_announce_embed(active_events()))
        await set_last_announced_event_key(key)

    async def shutdown(self):
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass


event_announcer = EventAnnouncer()
