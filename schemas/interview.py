"""Pydantic schemas for Interview & Technology Cheat Sheet APIs."""

from pydantic import BaseModel, Field


class SelectResumeRequest(BaseModel):
    """Payload for switching active resume context in interview prep."""

    resume_id: str = Field(..., min_length=1, max_length=120)


class CheatsheetAddRequest(BaseModel):
    """Payload for adding a custom technology cheat sheet."""

    tech: str = Field(..., min_length=1, max_length=60)
    resume_id: str = Field(default="", max_length=120)


class CheatsheetReviseRequest(BaseModel):
    """Payload for toggling revision state on a cheat sheet card."""

    tech: str = Field(..., min_length=1, max_length=60)
    card_index: int = Field(..., ge=0, le=500)
    revised: bool = True
