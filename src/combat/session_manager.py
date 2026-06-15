import asyncio
from typing import Dict, Optional, Set
from src.combat.session import CombatSession

class CombatSessionManager:
    def __init__(self):
        self.active_sessions: Dict[int, 'CombatSession'] = {}
        self.selected_cards: Dict[int, dict] = {}
        self.pending_challenges: Dict[int, int] = {}
        self.ready_players: Set[int] = set()
        self.combat_pairs: Dict[int, int] = {}
        self.cleanup_task: Optional[asyncio.Task] = None

    def start_cleanup_task(self):
        if self.cleanup_task is None or self.cleanup_task.done():
            self.cleanup_task = asyncio.create_task(self._cleanup_expired_sessions())
            self._cleanup_running = True
    
    async def _cleanup_expired_sessions(self):
        while True:
            try:
                await asyncio.sleep(300)
                await self.cleanup_expired_sessions()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in cleanup task: {e}")
        self._cleanup_running = False
    
    async def cleanup_expired_sessions(self):
        expired_users = []
        
        for user_id, session in self.active_sessions.items():
            if session.has_timed_out():
                expired_users.append(user_id)
        
        for user_id in expired_users:
            await self.end_session(user_id, reason="timeout")

        stale_selections = [
            uid for uid in self.selected_cards
            if uid not in self.active_sessions
        ]
        for uid in stale_selections:
            self.selected_cards.pop(uid, None)
            self.ready_players.discard(uid)
            self.clear_combat_pair(uid)

    def create_session(self, user1_id: int, user2_id: int, card1: dict, card2: dict) -> 'CombatSession':
        session = CombatSession(user1_id, user2_id, card1, card2)
        self.active_sessions[user1_id] = session
        self.active_sessions[user2_id] = session
        self.pending_challenges.pop(user2_id, None)

        # Battle has begun: clear pre-battle matchmaking state for both players
        for uid in (user1_id, user2_id):
            self.ready_players.discard(uid)
            self.clear_combat_pair(uid)

        return session
    
    def get_session(self, user_id: int) -> Optional['CombatSession']:
        return self.active_sessions.get(user_id)
    
    def is_user_in_session(self, user_id: int) -> bool:
        return user_id in self.active_sessions
    
    def has_pending_challenge(self, user_id: int) -> bool:
        return user_id in self.pending_challenges
    
    def set_pending_challenge(self, challenger_id: int, opponent_id: int):
        self.pending_challenges[opponent_id] = challenger_id

    def clear_pending_challenge(self, opponent_id: int):
        self.pending_challenges.pop(opponent_id, None)
    
    async def end_session(self, user_id: int, reason: str = "completed"):
        session = self.active_sessions.get(user_id)
        if not session:
            return
        
        # Get both players
        players = [session.p1_id, session.p2_id]
        
        # Mark session as completed
        session.completed = True
        
        # Remove from active sessions
        for player_id in players:
            self.active_sessions.pop(player_id, None)
            # Also clean up any lingering card selections / matchmaking state
            self.selected_cards.pop(player_id, None)
            self.ready_players.discard(player_id)
            self.clear_combat_pair(player_id)

    def set_card_selection(self, user_id: int, card: dict):
        self.selected_cards[user_id] = card

    def get_card_selection(self, user_id: int) -> Optional[dict]:
        return self.selected_cards.get(user_id)

    def clear_card_selection(self, user_id: int):
        self.selected_cards.pop(user_id, None)

    def set_combat_pair(self, user1_id: int, user2_id: int):
        self.combat_pairs[user1_id] = user2_id
        self.combat_pairs[user2_id] = user1_id

    def get_combat_partner(self, user_id: int) -> Optional[int]:
        return self.combat_pairs.get(user_id)

    def clear_combat_pair(self, user_id: int):
        partner = self.combat_pairs.pop(user_id, None)
        if partner is not None:
            self.combat_pairs.pop(partner, None)

    def set_player_ready(self, user_id: int):
        self.ready_players.add(user_id)

    def clear_ready(self, user_id: int):
        self.ready_players.discard(user_id)

    def are_both_ready(self, user1_id: int, user2_id: int) -> bool:
        return (
            user1_id in self.ready_players
            and user2_id in self.ready_players
            and user1_id in self.selected_cards
            and user2_id in self.selected_cards
        )
    
    async def shutdown(self):
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        
        # End all active sessions
        active_users = list(self.active_sessions.keys())
        for user_id in active_users:
            await self.end_session(user_id, reason="shutdown")
        
# Global session manager instance
session_manager = CombatSessionManager()