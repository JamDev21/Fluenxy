import logging
from uuid import UUID
from app.core.database import get_supabase_client
from app.services.deepseek_service import deepseek_service

logger = logging.getLogger(__name__)

async def process_post_meeting_feedback(group_id: UUID, transcript_buffer: list, active_usernames: dict, manager_instance):
    """
    The core Data Diet workflow. Runs asynchronously after the last user disconnects.
    Generates grammar feedback via DeepSeek, saves to Supabase Storage, and clears RAM.
    """
    try:
        if not transcript_buffer:
            logger.info(f"Room {group_id} ended with no conversation. Skipping Data Diet.")
            return

        logger.info(f"Starting Data Diet for room {group_id}. Processing {len(transcript_buffer)} messages.")
        
        # 1. Request structural JSON feedback from DeepSeek
        feedback_json_str = await deepseek_service.generate_grammar_feedback(transcript_buffer, active_usernames)
        
        if feedback_json_str == "{}":
            logger.warning(f"DeepSeek returned empty feedback for room {group_id}.")
            return
            
        # 2. Connect to Supabase
        supabase = await get_supabase_client()
        file_name = f"{group_id}_feedback.json"
        
        # 3. Upload raw JSON to Supabase Storage
        # NOTE: Ensure you have created a public bucket named 'feedback_reports' in your Supabase dashboard
        await supabase.storage.from_("feedback_reports").upload(
            path=file_name,
            file=feedback_json_str.encode("utf-8"),
            file_options={"content-type": "application/json"}
        )
        
        logger.info(f"Feedback successfully saved to Supabase bucket 'feedback_reports': {file_name}")

    except Exception as e:
        logger.error(f"Critical failure during Data Diet for room {group_id}: {e}")
        
    finally:
        # 4. PRIVACY & MEMORY CLEANUP
        # Guarantee the raw transcript is permanently deleted from RAM.
        manager_instance.destroy_room(group_id)