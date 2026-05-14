import logging
from groq import AsyncGroq
from app.core.config import settings
from typing import List

logger = logging.getLogger(__name__)
client = AsyncGroq(api_key=settings.GROQ_API_KEY)

BASE_SYSTEM_PROMPT = """
You are the AI Moderator for a B1 level English conversation club named Fluenxy.
Your ONLY goal is to encourage human participants to speak to EACH OTHER.
You are NOT a participant. You are a strict but friendly facilitator.

Core Directives:
1. Use B1 level English (simple, clear, avoiding complex idioms).
2. BE EXTREMELY BRIEF. Your responses must never exceed 20 words.
3. Never participate in the debate. Always redirect the conversation back to the users.
4. Do not say "Hello" or introduce yourself, just deliver the moderation prompt.
"""

class GroqService:
    def _format_transcript_for_ai(self, recent_messages: List[dict]) -> str:
        """
        Converts the raw JSON buffer into a readable text format.
        Now uses 'sender_name' instead of UUID for human-readable context.
        """
        formatted_history = "\n".join(
            [f"{msg.get('sender_name')}: {msg.get('text')}" for msg in recent_messages if msg.get('text')]
        )
        return formatted_history or "(No previous conversation)"

    async def generate_silence_intervention(self, transcript_buffer: List[dict], active_users: List[str]) -> str:
        # Expanding the memory window to the last 40 messages
        recent_messages = transcript_buffer[-40:] 
        history = self._format_transcript_for_ai(recent_messages)
        
        user_prompt = f"""
        
        
        Current participants in the room: {', '.join(active_users)}
        
        The room has been completely silent for 15 seconds.
        Here is the recent conversation history:
        {history}
        
        TASK: Look at the participants list. Ask a very short, open-ended question to ONE specific participant by name. 
        Try to call on someone who hasn't spoken recently in the history. Relate the question to the last topic discussed.
        """

        try:
            response = await client.chat.completions.create(
                messages=[
                    {"role": "system", "content": BASE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                model="llama-3.1-8b-instant",
                temperature=0.7,
                max_tokens=40
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Groq API error during silence intervention: {e}")
            fallback_user = active_users[0] if active_users else "everyone"
            return f"{fallback_user}, what do you think about this?"

    async def generate_sos_intervention(self, transcript_buffer: List[dict], active_users: List[str]) -> str:
        # Expanding the memory window here as well for better context
        recent_messages = transcript_buffer[-40:]
        history = self._format_transcript_for_ai(recent_messages)
        
        user_prompt = f"""
        
        
        Current participants in the room: {', '.join(active_users)}
        
        A user has requested help (SOS) because they don't know how to finish their sentence.
        Here is the recent conversation history:
        {history}
        
        TASK: Look at the very last message in the history. Suggest 2 simple words or a short phrase 
        that they might be looking for to finish their idea. Keep it highly encouraging.
        """

        try:
            response = await client.chat.completions.create(
                messages=[
                    {"role": "system", "content": BASE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt} 
                ],
                model="llama-3.1-8b-instant",
                temperature=0.5,
                max_tokens=40
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Groq API error during SOS intervention: {e}")
            return "Take your time! What word are you looking for?"

groq_service = GroqService()