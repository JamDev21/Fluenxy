import asyncio
import time
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from uuid import UUID

from app.services.connection_manager import manager

logger = logging.getLogger(__name__)
router = APIRouter()

# Business Logic Constants
SILENCE_THRESHOLD_SECONDS = 15.0
MAX_SPEAKER_HOLD_SECONDS = 30.0 # Prevents a disconnected user from locking the AI forever

@router.websocket("/room/{group_id}/{user_id}")
async def room_websocket(websocket: WebSocket, group_id: UUID, user_id: UUID):
    """
    Event-driven WebSocket endpoint with Active Speaker Lock and SOS functionality.
    """
    await manager.connect(websocket, group_id, user_id)
    
    try:
        while True:
            try:
                # Wait for JSON events. Timeout triggers the silence check.
                data = await asyncio.wait_for(websocket.receive_json(), timeout=SILENCE_THRESHOLD_SECONDS)
                
                event_type = data.get("type")
                
                if event_type == "speaking_start":
                    # ENGAGE LOCK: User is making sound, block AI interventions
                    manager.set_active_speaker(group_id, user_id)
                    
                elif event_type == "transcript":
                    # RELEASE LOCK: User finished the phrase
                    manager.clear_active_speaker(group_id)
                    
                    incoming_text = data.get("text", "")
                    transcript_line = {
                        "sender_id": str(user_id),
                        "text": incoming_text,
                        "timestamp": time.time(),
                        "event": "transcript"
                    }
                    manager.update_activity(group_id, transcript_line)
                    await manager.broadcast_to_group(group_id, transcript_line)
                    
                elif event_type == "sos":
                    # OVERRIDE: User explicitly pressed "Help me AI"
                    room = manager.active_rooms.get(group_id)
                    if room and not room.is_ai_computing:
                        room.is_ai_computing = True
                        manager.clear_active_speaker(group_id) # Release lock just in case
                        
                        logger.info(f"User {user_id} triggered SOS in room {group_id}.")
                        
                        try:
                            
                            ai_response_text = "I'm here to help! What word are you looking for?"
                            
                            ai_message = {
                                "sender_id": "AI_MODERATOR",
                                "text": ai_response_text,
                                "timestamp": time.time(),
                                "event": "ai_intervention"
                            }
                            manager.update_activity(group_id, ai_message)
                            await manager.broadcast_to_group(group_id, ai_message)
                        finally:
                            room.is_ai_computing = False

            except asyncio.TimeoutError:
                # SILENCE TIMEOUT TRIGGERED
                room = manager.active_rooms.get(group_id)
                if not room:
                    continue
                    
                # 1. Fail-Safe: Check if someone has held the speaker lock for too long 
                if room.active_speaker:
                    hold_duration = time.time() - room.active_speaker_timestamp
                    if hold_duration > MAX_SPEAKER_HOLD_SECONDS:
                        logger.warning(f"Ghost lock detected: releasing active speaker in room {group_id}.")
                        room.active_speaker = None
                    else:
                        # Someone is actively thinking/speaking. DO NOT interrupt.
                        continue 
                        
                # 2. Normal Silence Check (Only runs if NO ONE is currently speaking)
                current_silence = time.time() - room.last_activity
                
                if current_silence >= SILENCE_THRESHOLD_SECONDS and not room.is_ai_computing and not room.active_speaker:
                    room.is_ai_computing = True
                    logger.info(f"Room {group_id} silent for {current_silence:.1f}s. Triggering AI...")
                    
                    try:
                        
                        ai_response_text = "It's a bit quiet! Who wants to share their opinion next?"
                        
                        ai_message = {
                            "sender_id": "AI_MODERATOR",
                            "text": ai_response_text,
                            "timestamp": time.time(),
                            "event": "ai_intervention"
                        }
                        manager.update_activity(group_id, ai_message)
                        await manager.broadcast_to_group(group_id, ai_message)
                    finally:
                        room.is_ai_computing = False

    except WebSocketDisconnect:
        # If the user who disconnected was holding the mic, release the lock immediately
        room = manager.active_rooms.get(group_id)
        if room and room.active_speaker == user_id:
            manager.clear_active_speaker(group_id)
            
        manager.disconnect(websocket, group_id, user_id)