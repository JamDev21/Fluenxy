from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from enum import Enum
from datetime import datetime, time, timezone
from uuid import UUID, uuid4

# Strict Validation Enums 

class EnglishLevel(str, Enum):
    A1 = "A1"
    A2 = "A2"
    B1 = "B1" 
    B2 = "B2"
    C1 = "C1"

class GroupStatus(str, Enum):
    PENDING = "PENDING"     # Waiting for scheduled time
    ACTIVE = "ACTIVE"       # Call in progress
    COMPLETED = "COMPLETED" # Call finished, ready for feedback

#  Domain Models 

class UserProfile(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    username: str = Field(..., min_length=3, max_length=50)
    interests: List[str] = Field(default_factory=list)
    level: EnglishLevel = EnglishLevel.B1

    @field_validator("interests")
    @classmethod
    def normalize_interests(cls, v: List[str]) -> List[str]:
        # Convert to lowercase and strip whitespace.
        # Ensures uniform data for the matchmaking algorithm.
        return [interest.strip().lower() for interest in v]

class UserAvailability(BaseModel):
    user_id: UUID
    day_of_week: int = Field(ge=0, le=6, description="0=Monday, 6=Sunday")
    slot_time: time 
    # Note: Frontend must send this 'time' converted to UTC.

class MatchGroup(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    topic: Optional[str] = None # Populated when AI suggests a topic
    scheduled_at: datetime
    status: GroupStatus = GroupStatus.PENDING
    members: List[UUID] = Field(default_factory=list, max_length=6) # Max 6 users per room

    @field_validator("scheduled_at")
    @classmethod
    def ensure_timezone_aware(cls, v: datetime) -> datetime:
        # Force UTC if datetime is naive to prevent timezone bugs
        # when deploying to cloud environments like Koyeb.
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v