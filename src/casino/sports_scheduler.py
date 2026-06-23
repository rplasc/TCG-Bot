"""Background task that settles the daily sports match and opens the next one.

Every tick it settles any open match whose day has passed (paying winners and
announcing the result), then ensures a match exists for the current day. Settled
matches are skipped on subsequent ticks, so restarts never double-pay.
"""

import asyncio
import os
from typing import Optional

from discord import Embed, Color

from src.casino.sportsbook import settle_due_matches, get_or_create_today_match

# Falls back to the shared event-announce channel if a dedicated one isn't set.
SPORTS_ANNOUNCE_CHANNEL_ID = int(
    os.getenv("SPORTS_ANNOUNCE_CHANNEL_ID") or os.getenv("EVENT_ANNOUNCE_CHANNEL_ID", "0")
)
CHECK_INTERVAL = 300  # seconds


def _result_embed(summary: dict) -> Embed:
    match = summary["match"]
    if summary["refunded"]:
        embed = Embed(
            title="🏟️ Match Voided — Bets Refunded",
            description=(
                f"**{match['team_a']}** vs **{match['team_b']}**\n"
                f"Nobody backed the winning side, so all stakes were refunded."
            ),
            color=Color.greyple(),
        )
        return embed

    embed = Embed(
        title="🏟️ Sports Result!",
        description=f"**{match['team_a']}** vs **{match['team_b']}**",
        color=Color.gold(),
    )
    embed.add_field(name="🏆 Winner", value=f"**{summary['winning_team']}**", inline=False)
    if summary["total_pool"] == 0:
        embed.add_field(name="Pool", value="No bets were placed today.", inline=False)
    else:
        embed.add_field(name="💰 Total Pool", value=f"{summary['total_pool']} coins", inline=True)
        embed.add_field(name="🏠 House Rake", value=f"{summary['rake']} coins", inline=True)
        embed.add_field(
            name="📤 Paid Out",
            value=f"{summary['distributable']} coins to {summary['winners']} winner(s)",
            inline=False,
        )
    return embed


class SportsScheduler:
    def __init__(self):
        self.task: Optional[asyncio.Task] = None

    def start(self, client):
        if self.task is None or self.task.done():
            self.task = asyncio.create_task(self._loop(client))

    async def _loop(self, client):
        while True:
            try:
                await self._tick(client)
                await asyncio.sleep(CHECK_INTERVAL)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[sports scheduler] {e}")
                await asyncio.sleep(CHECK_INTERVAL)

    async def _tick(self, client):
        summaries = await settle_due_matches()
        if summaries and SPORTS_ANNOUNCE_CHANNEL_ID:
            channel = client.get_channel(SPORTS_ANNOUNCE_CHANNEL_ID)
            if channel:
                for summary in summaries:
                    await channel.send(embed=_result_embed(summary))
        # Always make sure today's match is available to bet on.
        await get_or_create_today_match()

    async def shutdown(self):
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass


sports_scheduler = SportsScheduler()
