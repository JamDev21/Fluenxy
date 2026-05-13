import logging
from openai import AsyncOpenAI
from app.core.config import settings
from typing import List

logger = logging.getLogger(__name__)

# DeepSeek uses the OpenAI SDK format but requires their specific base_url
client = AsyncOpenAI(
    api_key=settings.DEEPSEEK_API_KEY, 
    base_url="https://api.deepseek.com/v1" # Standard DeepSeek endpoint
)

class DeepSeekService:
    async def generate_room_topic(self, user_interests: List[str]) -> str:
        """
        Takes a pooled list of interests from up to 6 users and generates
        a single, highly engaging B1-level debate question.
        """
        # Remove duplicates and empty strings
        unique_interests = list(set([i.lower().strip() for i in user_interests if i]))
        interests_str = ", ".join(unique_interests) if unique_interests else "general life, hobbies, travel"

        prompt = f"""
        You are an expert ESL (English as a Second Language) teacher.
        Create ONE engaging, open-ended debate question for a B1 English conversation club.
        
        The participants share these interests: {interests_str}.
        
        Rules:
        1. It must be a single question.
        2. Keep the vocabulary at a B1 level (understandable but challenging enough to spark debate).
        3. Do not include any introductory text, just the question itself.
        """

        try:
            response = await client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.8,
                max_tokens=50
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"DeepSeek Topic Generation Failed: {e}")
            # Fallback to guarantee the room still opens even if the AI API is down
            return "If you could travel anywhere in the world tomorrow, where would you go and why?"


    async def generate_grammar_feedback(self, transcript_buffer: List[dict], active_usernames: dict) -> str:
        """
        Analyzes the full meeting transcript and generates personalized grammatical 
        feedback for each participant in a strict JSON format.
        """
        
        formatted_history = "\n".join(
            [f"{msg.get('sender_name')}: {msg.get('text')}" 
             for msg in transcript_buffer 
             if msg.get('text') and msg.get('sender_name') != 'AI_MODERATOR']
        )
        
        
        if not formatted_history.strip():
            return "{}"
        
        users_list = ", ".join(active_usernames.values())
        
        prompt = f"""
        You are an expert ESL (English as a Second Language) evaluator.
        Analyze the following conversation from a B1 English club.
        Participants: {users_list}
        
        Transcript:
        {formatted_history}
        
        TASK: Return a STRICT JSON object containing feedback for each user who spoke.
        Do NOT wrap the JSON in markdown formatting. Just return the raw JSON.
        
        Expected JSON Schema:
        {{
            "User Name": {{
                "strengths": "What they did well in 1 short sentence",
                "improvement_area": "One specific grammar or vocabulary correction",
                "example_correction": "Incorrect phrase -> Correct phrase"
            }}
        }}
        """

        try:
            response = await client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1000,
                
                response_format={"type": "json_object"} 
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"DeepSeek Feedback Generation Failed: {e}")
            return "{}"


deepseek_service = DeepSeekService()