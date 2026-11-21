"""Claude for the content pipeline (tasks 9.2, 9.4, 9.5): meme captions, and one review call per
batch that both tags (from the fixed list only) and moderates each item."""

import json
from dataclasses import dataclass
from typing import Any, Protocol

import anthropic
import structlog

from orbit.modules.content.tags import TAGS

log = structlog.get_logger("orbit.content")

REVIEW_SYSTEM = f"""You review short items for a party game played by adults (18+) in India.
For each item, decide:
- safe: false if it is sexual, hateful or demeaning toward a group, graphic or gory, about
  self-harm, a real tragedy or disaster, divisive political or religious content, or makes
  claims about a named private person. Light, good-natured humour and gentle dark humour
  about history or absurd facts are fine.
- tags: 1 to 3 tags chosen ONLY from this list: {", ".join(TAGS)}.
Return a verdict for every index you were given."""

CAPTION_SYSTEM = """You write captions for meme templates for a friendly party game played by
adults in India. Keep each caption under 60 characters, relatable (college, office, chai,
cricket, family WhatsApp groups, traffic, exams), never mean about a group, never sexual,
never political. Fill exactly the number of text boxes each template has."""

REVIEW_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "verdicts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "safe": {"type": "boolean"},
                    "tags": {"type": "array", "items": {"type": "string", "enum": list(TAGS)}},
                },
                "required": ["index", "safe", "tags"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["verdicts"],
    "additionalProperties": False,
}

CAPTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "captions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "template_id": {"type": "string"},
                    "texts": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["template_id", "texts"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["captions"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class Verdict:
    safe: bool
    tags: list[str]


class ContentLLM(Protocol):
    async def review(self, texts: list[str]) -> list[Verdict | None]: ...
    async def captions(self, templates: list[dict[str, Any]]) -> dict[str, list[str]]: ...


class ClaudeContentLLM:
    def __init__(self, api_key: str, model: str) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model

    async def _json(
        self, system: str, prompt: str, schema: dict[str, Any]
    ) -> dict[str, Any] | None:
        response = await self._client.beta.messages.create(
            model=self._model,
            max_tokens=16000,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}},
            # Opt-in server-side fallback: if the model declines, another model retries in the
            # same call, routed by refusal category.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        if response.stop_reason == "refusal":
            log.warning(
                "content.llm_refused", category=getattr(response.stop_details, "category", None)
            )
            return None
        text = next((b.text for b in response.content if b.type == "text"), None)
        return json.loads(text) if text else None

    async def review(self, texts: list[str]) -> list[Verdict | None]:
        listing = "\n".join(f"{i}. {t}" for i, t in enumerate(texts))
        data = await self._json(REVIEW_SYSTEM, f"Items:\n{listing}", REVIEW_SCHEMA)
        out: list[Verdict | None] = [None] * len(texts)
        for v in (data or {}).get("verdicts", []):
            if 0 <= v["index"] < len(texts):
                out[v["index"]] = Verdict(safe=bool(v["safe"]), tags=list(v["tags"]))
        return out  # None = no verdict: the item is not activated

    async def captions(self, templates: list[dict[str, Any]]) -> dict[str, list[str]]:
        listing = "\n".join(
            f'- template_id {t["id"]}: "{t["name"]}", {t["box_count"]} text boxes'
            for t in templates
        )
        data = await self._json(CAPTION_SYSTEM, f"Templates:\n{listing}", CAPTION_SCHEMA)
        return {c["template_id"]: c["texts"] for c in (data or {}).get("captions", [])}
