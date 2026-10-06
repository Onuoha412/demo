from uuid import UUID

from pydantic import BaseModel, Field

class WaitTimeResponse(BaseModel):
    estimated_minutes: int = Field(ge=0)
    lower_bound_minutes: int = Field(ge=0)
    upper_bound_minutes: int = Field(ge=0)
    confidence: float = Field(ge=0, le=1)
    model_version: str
    factors: dict
