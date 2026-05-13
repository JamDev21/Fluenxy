from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.core.config import settings
from app.api.websockets import router as websocket_router
from app.services.matchmaking import start_matchmaking_cron, scheduler

# Initialize the FastAPI application with project metadata
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup Logic 
    # Start the matchmaking background clock
    start_matchmaking_cron()
    yield
    # Shutdown Logic 
    # Cleanly shut down the scheduler to prevent memory leaks
    scheduler.shutdown()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description="Event-driven real-time backend for Fluenxy AI Moderator.",
    lifespan=lifespan
)

# Mount the WebSocket router. 
# The endpoint will be accessible at: ws://<your-domain>/ws/room/{group_id}/{user_id}
app.include_router(websocket_router, prefix="/ws", tags=["Realtime"])

@app.get("/")
async def health_check():
    return {
        "status": "online",
        "project": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT
    }