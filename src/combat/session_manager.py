import asyncio
from typing import Dict, Optional, Set
from src.combat.session import CombatSession

class CombatSessionManager:
    def __init__(self):
        self.active_sessions: Dict[int, 'CombatSession'] = {}
        self.selected_cards: Dict[int, dict] = {}
        self.cleanup_task = None
        self._cleanup_running = False
    
    def start_cleanup_task(self):
        if not self._cleanup_running and (self.cleanup_task is None or self.cleanup_task.done()):
            self.cleanup_task = asyncio.create_task(self._cleanup_expired_sessions())
            self._cleanup_running = True
    
    async def _cleanup_expired_sessions(self):
        while self._cleanup_running:
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
    
    def create_session(self, user1_id: int, user2_id: int, card1: dict, card2: dict) -> 'CombatSession':        
        session = CombatSession(user1_id, user2_id, card1, card2)
        self.active_sessions[user1_id] = session
        self.active_sessions[user2_id] = session
        
        return session
    
    def get_session(self, user_id: int) -> Optional['CombatSession']:
        return self.active_sessions.get(user_id)
    
    def is_user_in_session(self, user_id: int) -> bool:
        return user_id in self.active_sessions
    
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
            # Also clean up any lingering card selections
            self.selected_cards.pop(player_id, None)
            
    def set_card_selection(self, user_id: int, card: dict):
        self.selected_cards[user_id] = card
    
    def get_card_selection(self, user_id: int) -> Optional[dict]:
        return self.selected_cards.get(user_id)
    
    def clear_card_selection(self, user_id: int):
        self.selected_cards.pop(user_id, None)
    
    def get_ready_players(self) -> Set[int]:
        return set(self.selected_cards.keys())
    
    async def shutdown(self):
        if self.cleanup_task:
            self.cleanup_task.cancel()
        
        # End all active sessions
        active_users = list(self.active_sessions.keys())
        for user_id in active_users:
            await self.end_session(user_id, reason="shutdown")

# Global session manager instance
session_manager = CombatSessionManager()