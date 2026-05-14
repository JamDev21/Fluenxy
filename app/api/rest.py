import logging
from fastapi import APIRouter, HTTPException
from uuid import UUID
from typing import Optional
from pydantic import BaseModel
from datetime import datetime, timezone

from app.core.database import get_supabase_client
from app.models.schemas import UserAvailability

logger = logging.getLogger(__name__)
router = APIRouter()

# --- Schemas specifically for REST Requests/Responses ---

class RoomResponse(BaseModel):
    group_id: UUID
    topic: str
    scheduled_at: datetime
    status: str
    time_remaining_seconds: Optional[int] = None

# --- REST Endpoints ---

@router.post("/availability", status_code=201)
async def create_availability(availability: UserAvailability):
    """
    Saves a user's available time slot to the database.
    This data is consumed by the Hourly Matchmaking Cron Job.
    """
    try:
        supabase = await get_supabase_client()
        
        # Convert Pydantic model to dictionary, formatting the time safely
        data = {
            "user_id": str(availability.user_id),
            "day_of_week": availability.day_of_week,
            "slot_time": availability.slot_time.strftime("%H:%M:%S")
        }
        
        # Upsert: If the user already has this slot, it updates it. Otherwise, it inserts.
        # This prevents duplicate database entries if a user double-clicks the save button.
        response = await supabase.table("Availability").upsert(data).execute()
        
        logger.info(f"Availability upserted for user {availability.user_id}")
            
        return {"status": "success", "message": "Availability saved."}
        
    except Exception as e:
        logger.error(f"Error saving availability for {availability.user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.get("/my-room/{user_id}", response_model=RoomResponse)
async def get_current_room(user_id: UUID):
    """
    Called by React to check if the user has an active/pending room.
    Implements the 'Grace Period' logic to prevent late joins.
    """
    try:
        supabase = await get_supabase_client()
        now_utc = datetime.now(timezone.utc)
        
        # Find a PENDING or ACTIVE room where this user is a member
        # The 'cs' filter means "contains" for JSON/Array columns in PostgREST
        response = await supabase.table("Groups") \
            .select("*") \
            .in_("status", ["PENDING", "ACTIVE"]) \
            .filter("members", "cs", f'["{str(user_id)}"]') \
            .execute()
            
        if not response.data:
            raise HTTPException(status_code=404, detail="No active rooms found for this user.")
            
        room_data = response.data[0]
        
        # Ensure timezone awareness
        scheduled_time = datetime.fromisoformat(room_data["scheduled_at"])
        if scheduled_time.tzinfo is None:
            scheduled_time = scheduled_time.replace(tzinfo=timezone.utc)

        # --- Grace Period Logic ---
        # Block users who try to join 10+ minutes after the session started
        GRACE_PERIOD_MINUTES = 10
        minutes_since_start = (now_utc - scheduled_time).total_seconds() / 60.0
        
        if minutes_since_start > GRACE_PERIOD_MINUTES:
            raise HTTPException(status_code=403, detail="The session is too advanced to join.")
        
        # Calculate time remaining until the session officially starts
        time_diff = (scheduled_time - now_utc).total_seconds()
        time_remaining = max(0, int(time_diff))

        return RoomResponse(
            group_id=UUID(room_data["id"]),
            topic=room_data["topic"] or "General Conversation",
            scheduled_at=scheduled_time,
            status=room_data["status"],
            time_remaining_seconds=time_remaining
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching room for {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")