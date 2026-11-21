from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

ReactionKind = Literal["like", "laugh", "skip", "send"]
SocialKind = Literal["follow", "like_profile"]


class QuestionCard(BaseModel):
    kind: Literal["question"] = "question"
    id: UUID
    question_kind: Literal["single", "multi", "slider"]
    prompt: str
    options: dict[str, Any]


class ContentCard(BaseModel):
    kind: Literal["content"] = "content"
    id: UUID
    content_type: Literal["fact", "meme", "news"]
    payload: dict[str, Any]
    source_url: str | None


Card = Annotated[QuestionCard | ContentCard, Field(discriminator="kind")]


class DeckView(BaseModel):
    ends_at: datetime | None
    cards: list[Card]
    # What this player already sent, so a reload resumes where they were.
    answers: dict[UUID, dict[str, Any]]
    reactions: dict[UUID, ReactionKind]


class AnswerIn(BaseModel):
    value: dict[str, Any]


class ReactionIn(BaseModel):
    reaction: ReactionKind


class SocialIn(BaseModel):
    to_user: UUID
    kind: SocialKind
