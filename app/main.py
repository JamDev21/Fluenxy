from fastapi import FastAPI
from app.core.config import settings
from app.api.websockets import router as websocket_router

# Initialize the FastAPI application with project metadata
app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description="Event-driven real-time backend for Fluenxy AI Moderator."
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