from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    user_id: int = Field(gt=0)
    message: str = Field(min_length=1)


class UsageRequest(BaseModel):
    user_id: int = Field(gt=0)
    screen_time: int = Field(ge=0)
    goal: int = Field(gt=0)