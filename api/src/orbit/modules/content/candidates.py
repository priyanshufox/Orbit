"""What a source produces before review."""

from dataclasses import dataclass, field
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5


@dataclass
class Candidate:
    type: str  # fact | meme | news
    source: str  # imgflip | newsdata | ...
    external_key: str  # stable per item at the source, for de-duplication
    payload: dict[str, Any]
    source_url: str | None = None
    tags: list[str] = field(default_factory=list)

    @property
    def id(self) -> UUID:
        return uuid5(NAMESPACE_URL, f"orbit-{self.source}:{self.external_key}")

    def text_for_review(self) -> str:
        return " | ".join(str(v) for k, v in sorted(self.payload.items()) if k != "image_url")
