import logging
import asyncio
from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from uuid import uuid4

from app.core.database import get_supabase_client
from app.services.deepseek_service import deepseek_service

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()

async def run_matchmaking_cycle():
    """
    Core algorithm to group users. Runs exactly at the top of the hour.
    """
    logger.info("Starting Matchmaking Cycle...")
    
    try:
        supabase = await get_supabase_client()
        
        # 1. Determine the target time 
        now = datetime.now(timezone.utc)
        target_time = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        
        target_day = target_time.weekday() # 0 = Monday, 6 = Sunday
        target_hour_str = target_time.strftime("%H:%M:%S")

        # 2. Fetch available users from Supabase
        # NOTE: Using a hypothetical RPC or joined query. Adjust based on your exact Supabase schema.
        response = await supabase.table("Availability") \
            .select("user_id, Profiles(username, interests)") \
            .eq("day_of_week", target_day) \
            .eq("slot_time", target_hour_str) \
            .execute()
            
        available_users = response.data
        if not available_users:
            logger.info(f"No users available for {target_hour_str} UTC.")
            return

        # 3. Grouping Algorithm (Max 6 per room)
        # For production, we could sort by English level here. 
        # For now, we chunk them sequentially.
        chunk_size = 6
        groups = [available_users[i:i + chunk_size] for i in range(0, len(available_users), chunk_size)]
        
        logger.info(f"Formed {len(groups)} groups for the upcoming hour.")

        # 4. Process groups concurrently to save time
        tasks = []
        for group in groups:
            tasks.append(process_single_group(supabase, group, target_time))
            
        await asyncio.gather(*tasks)
        
        logger.info("Matchmaking Cycle Completed Successfully.")

    except Exception as e:
        logger.error(f"Critical error during matchmaking cycle: {e}")

async def process_single_group(supabase, group: list, scheduled_at: datetime):
    """
    Extracts interests, asks DeepSeek for a topic, and saves the room to the DB.
    """
    group_id = str(uuid4())
    member_ids = [str(user["user_id"]) for user in group]
    
    # Extract all interests into a flat list
    all_interests = []
    for user in group:
        # Assuming Profiles is a joined dictionary from Supabase
        profile = user.get("Profiles", {})
        if profile and isinstance(profile.get("interests"), list):
            all_interests.extend(profile["interests"])

    # Ask DeepSeek for a custom topic
    topic = await deepseek_service.generate_room_topic(all_interests)
    
    # Save the pending room to Supabase
    room_data = {
        "id": group_id,
        "topic": topic,
        "scheduled_at": scheduled_at.isoformat(),
        "status": "PENDING",
        "members": member_ids
    }
    
    try:
        await supabase.table("Groups").insert(room_data).execute()
        logger.info(f"Room {group_id} created with topic: '{topic}'")
    except Exception as e:
        logger.error(f"Failed to save room {group_id} to database: {e}")

# --- Scheduler Controls ---

def start_matchmaking_cron():
    """
    Schedules the job to run at minute 45 of every hour.
    Example: At 14:45, it groups people for the 15:00 slot.
    """
    scheduler.add_job(
        run_matchmaking_cycle, 
        'cron', 
        minute=45, 
        id='hourly_matchmaker',
        replace_existing=True
    )
    scheduler.start()
    logger.info("Matchmaking Cron Job started (Runs every hour at minute 45).")