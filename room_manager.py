# app/services/room_manager.py - V2 Bidirectional
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional, List
from fastapi import WebSocket
import random
import string

@dataclass
class Participant:
    """Represents a participant in a conversation"""
    user_id: str
    user_name: str
    language: str  # User's native language (e.g., "en", "zh", "es")
    websocket: WebSocket
    joined_at: datetime

@dataclass
class ConversationRoom:
    """Represents a conversation room with bidirectional translation"""
    room_code: str
    created_at: datetime
    participants: Dict[str, Participant] = field(default_factory=dict)  # user_id -> Participant
    is_active: bool = True
    message_count: int = 0
    
    def get_participant(self, user_id: str) -> Optional[Participant]:
        """Get participant by user ID"""
        return self.participants.get(user_id)
    
    def get_other_participants(self, user_id: str) -> List[Participant]:
        """Get all participants except the specified user"""
        return [p for uid, p in self.participants.items() if uid != user_id]
    
    def get_translation_targets(self, sender_id: str) -> List[tuple[Participant, str, str]]:
        """
        Get translation targets for a message
        
        Returns list of tuples: (participant, source_lang, target_lang)
        This tells us who to send to and what language pair to use
        """
        sender = self.get_participant(sender_id)
        if not sender:
            return []
        
        targets = []
        for participant in self.get_other_participants(sender_id):
            # Translate from sender's language to participant's language
            targets.append((
                participant,
                sender.language,      # source language
                participant.language  # target language
            ))
        
        return targets

class RoomManager:
    """Manages conversation rooms and participants - V2 with bidirectional support"""
    
    def __init__(self):
        self.rooms: Dict[str, ConversationRoom] = {}
    
    def generate_room_code(self) -> str:
        """Generate a unique 6-character room code"""
        while True:
            # Generate code like: ABC123
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            if code not in self.rooms:
                return code
    
    def create_room(self) -> ConversationRoom:
        """
        Create a new conversation room (no language specified - each user picks their own)
        """
        room_code = self.generate_room_code()
        
        room = ConversationRoom(
            room_code=room_code,
            created_at=datetime.now()
        )
        
        self.rooms[room_code] = room
        
        print(f"✅ Created room {room_code} (bidirectional translation enabled)")
        
        return room
    
    def get_room(self, room_code: str) -> Optional[ConversationRoom]:
        """Get room by code"""
        return self.rooms.get(room_code)
    
    def add_participant(
        self, 
        room_code: str, 
        user_id: str, 
        user_name: str,
        language: str,
        websocket: WebSocket
    ) -> bool:
        """
        Add participant to room with their native language
        
        Args:
            room_code: Room code
            user_id: Unique user identifier
            user_name: Display name
            language: User's native language code (e.g., "en", "zh")
            websocket: WebSocket connection
            
        Returns:
            True if added successfully, False otherwise
        """
        room = self.rooms.get(room_code)
        
        if not room:
            return False
        
        participant = Participant(
            user_id=user_id,
            user_name=user_name,
            language=language,
            websocket=websocket,
            joined_at=datetime.now()
        )
        
        room.participants[user_id] = participant
        
        print(f"✅ User {user_name} ({user_id}) joined room {room_code}")
        print(f"   Language: {language} | Total participants: {len(room.participants)}")
        
        # Print language pairs for debugging
        if len(room.participants) > 1:
            print(f"   Active language pairs:")
            for uid, p in room.participants.items():
                others = [f"{other.language}" for other_uid, other in room.participants.items() if other_uid != uid]
                if others:
                    print(f"      {p.language} → {', '.join(others)}")
        
        return True
    
    def remove_participant(self, room_code: str, user_id: str):
        """Remove participant from room"""
        room = self.rooms.get(room_code)
        
        if room and user_id in room.participants:
            participant = room.participants[user_id]
            del room.participants[user_id]
            
            print(f"❌ User {participant.user_name} ({user_id}) left room {room_code}")
            print(f"   Remaining participants: {len(room.participants)}")
            
            # Close room if no participants
            if len(room.participants) == 0:
                self.close_room(room_code)
    
    async def broadcast_to_room(
        self, 
        room_code: str, 
        message: dict, 
        exclude_user: Optional[str] = None
    ):
        """
        Broadcast message to all participants in room
        
        Args:
            room_code: Room code
            message: Message to broadcast
            exclude_user: Optional user ID to exclude from broadcast
        """
        room = self.rooms.get(room_code)
        
        if not room:
            return
        
        # Send to all participants except excluded user
        for user_id, participant in room.participants.items():
            if user_id != exclude_user:
                try:
                    await participant.websocket.send_json(message)
                except Exception as e:
                    print(f"❌ Failed to send to {participant.user_name} ({user_id}): {e}")
        
        room.message_count += 1
    
    async def send_to_user(self, room_code: str, user_id: str, message: dict):
        """
        Send message to specific user
        
        Args:
            room_code: Room code
            user_id: Target user ID
            message: Message to send
        """
        room = self.rooms.get(room_code)
        
        if not room:
            return
        
        participant = room.participants.get(user_id)
        
        if participant:
            try:
                await participant.websocket.send_json(message)
            except Exception as e:
                print(f"❌ Failed to send to {participant.user_name} ({user_id}): {e}")
    
    def close_room(self, room_code: str):
        """Close and remove a room"""
        room = self.rooms.get(room_code)
        
        if room:
            room.is_active = False
            
            # Remove room
            del self.rooms[room_code]
            print(f"🗑️ Closed room {room_code}")
    
    def cleanup_inactive_rooms(self, max_age_hours: int = 24):
        """Clean up rooms older than max_age_hours"""
        now = datetime.now()
        rooms_to_close = []
        
        for room_code, room in self.rooms.items():
            age = (now - room.created_at).total_seconds() / 3600
            
            if age > max_age_hours or (len(room.participants) == 0 and age > 1):
                rooms_to_close.append(room_code)
        
        for room_code in rooms_to_close:
            self.close_room(room_code)
        
        if rooms_to_close:
            print(f"🗑️ Cleaned up {len(rooms_to_close)} inactive rooms")
    
    def get_stats(self) -> dict:
        """Get statistics about active rooms"""
        total_participants = sum(len(room.participants) for room in self.rooms.values())
        total_messages = sum(room.message_count for room in self.rooms.values())
        
        # Get language pair statistics
        language_pairs = {}
        for room in self.rooms.values():
            languages = sorted(set(p.language for p in room.participants.values()))
            if len(languages) >= 2:
                pair = " ↔ ".join(languages)
                language_pairs[pair] = language_pairs.get(pair, 0) + 1
        
        return {
            "total_rooms": len(self.rooms),
            "active_rooms": sum(1 for room in self.rooms.values() if room.is_active),
            "total_participants": total_participants,
            "total_messages": total_messages,
            "language_pairs": language_pairs,
            "rooms": [
                {
                    "code": room.room_code,
                    "participants": [
                        {
                            "name": p.user_name,
                            "language": p.language,
                            "joined_at": p.joined_at.isoformat()
                        }
                        for p in room.participants.values()
                    ],
                    "created_at": room.created_at.isoformat()
                }
                for room in self.rooms.values()
            ]
        }