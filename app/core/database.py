from supabase import create_async_client, AsyncClient
from app.core.config import settings

async def get_supabase_client() -> AsyncClient:
    """
    Creates and returns an asynchronous instance of the Supabase client.
    This ensures that our database calls do not block
    the FastAPI event loop, which is critical for keeping WebSockets fast.
    """
    client = await create_async_client(
        settings.SUPABASE_URL, 
        settings.SUPABASE_KEY
    )
    return client