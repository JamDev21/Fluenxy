from fastapi import WebSocket
from typing import Dict, List, Optional
from uuid import UUID
import asyncio
from dataclasses import dataclass, field
import time
import logging

from app.services.data_diet import process_post_meeting_feedback

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Room State Encapsulation 

@dataclass
class RoomState:
    """
    Encapsulates all temporary data for an active call.
    """
    # Mapping: { user_id: WebSocket } - Prevents duplicate sockets per user
    connections: Dict[UUID, WebSocket] = field(default_factory=dict)
    active_usernames: Dict[UUID, str] = field(default_factory=dict)
    
    # Stores the raw conversation for the DeepSeek Data Diet
    transcript_buffer: List[dict] = field(default_factory=list)
    
    # Tracks the exact timestamp of the last spoken message (for AI silence detection)
    last_activity: float = field(default_factory=time.time)
    is_ai_computing: bool = False

    # Activate Speaker Lock
    active_speaker: Optional[UUID] = None
    active_speaker_timestamp: float = field(default_factory=time.time)

    # Icebreaker State
    topic: str = "General Conversation"
    icebreaker_sent: bool = False

# Connection Manager 

class ConnectionManager:
    def __init__(self):
        # Master mapping: { group_id: RoomState }
        self.active_rooms: Dict[UUID, RoomState] = {}

    async def connect(self, websocket: WebSocket, group_id: UUID, user_id: UUID):
        await websocket.accept()
        
        # 1. Initialize room if it doesn't exist
        if group_id not in self.active_rooms:
            self.active_rooms[group_id] = RoomState()
            
        room = self.active_rooms[group_id]

        # 2. Reconnection Logic: Close old socket gracefully
        if user_id in room.connections:
            logger.info(f"User {user_id} reconnecting. Closing old socket.")
            try:
                await room.connections[user_id].close()
            except Exception:
                pass

        # 3. Map the new connection
        room.connections[user_id] = websocket
        logger.info(f"User {user_id} joined room {group_id}. Active users: {len(room.connections)}")

    def disconnect(self, websocket: WebSocket, group_id: UUID, user_id: UUID):
        if group_id in self.active_rooms:
            room = self.active_rooms[group_id]
            
            # Ensure we only remove the matching socket (handles fast reconnections)
            if user_id in room.connections and room.connections[user_id] == websocket:
                del room.connections[user_id]
                # Cleanup the username
                if user_id in room.active_usernames:
                    del room.active_usernames[user_id]
                logger.info(f"User {user_id} left room {group_id}.")
            
            # TRIGGER THE DATA DIET WORKFLOW
            if not room.connections:
                logger.info(f"Room {group_id} connections empty. Initiating Data Diet background task.")
                
                # Start the background task to process and delete the transcript
                asyncio.create_task(
                    process_post_meeting_feedback(
                        group_id=group_id,
                        transcript_buffer=room.transcript_buffer,
                        active_usernames=room.active_usernames,
                        manager_instance=self
                    )
                )
            
    def set_username(self, group_id: UUID, user_id: UUID, username: str):
        if group_id in self.active_rooms:
            self.active_rooms[group_id].active_usernames[user_id] = username
            logger.info(f"Registered username '{username}' for UUID {user_id} in room {group_id}")

    async def broadcast_to_group(self, group_id: UUID, message: dict):
        if group_id in self.active_rooms:
            room = self.active_rooms[group_id]
            
            # Iterate over a list of items to prevent dict mutation errors during broadcast
            for uid, connection in list(room.connections.items()):
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.warning(f"Broadcast failed for user {uid}: {e}")
                    self.disconnect(connection, group_id, uid)

    def update_activity(self, group_id: UUID, transcript_line: dict):
        """
        Appends the STT transcript and resets the AI silence timer.
        """
        if group_id in self.active_rooms:
            room = self.active_rooms[group_id]
            room.transcript_buffer.append(transcript_line)
            room.last_activity = time.time()

    def destroy_room(self, group_id: UUID):
        """
        Called ONLY after DeepSeek has processed the transcript.
        Completely wipes the room from RAM.
        """
        if group_id in self.active_rooms:
            del self.active_rooms[group_id]
            logger.info(f"Room {group_id} fully wiped from memory (Data Diet complete).")

    def set_active_speaker(self, group_id: UUID, user_id: UUID):
        """Locks the room so the AI knows someone is currently formulating a thought."""
        if group_id in self.active_rooms:
            room = self.active_rooms[group_id]
            room.active_speaker = user_id
            room.active_speaker_timestamp = time.time()
            logger.info(f"User {user_id} started speaking in room {group_id}")

    def clear_active_speaker(self, group_id: UUID):
        """Releases the speaking lock once the phrase is complete."""
        if group_id in self.active_rooms:
            self.active_rooms[group_id].active_speaker = None

manager = ConnectionManager()