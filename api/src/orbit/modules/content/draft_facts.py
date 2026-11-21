"""Draft new facts for human review (task 9.6). Never writes to the live bank.

  uv run python -m orbit.modules.content.draft_facts --per-tag 25
  -> writes data/facts.drafts.json; review it by hand, then move the good ones into
     data/facts.json and run `uv run python -m orbit.seed --banks`.

Needs ANTHROPIC_API_KEY.
"""

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

import anthropic

from orbit.core.config import get_settings
from orbit.modules.content.seed import BANK
from orbit.modules.content.tags import TAGS

DRAFTS = BANK.with_name("facts.drafts.json")

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "facts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"text": {"type": "string"}, "source_url": {"type": "string"}},
                "required": ["text", "source_url"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["facts"],
    "additionalProperties": False,
}


async def draft(
    client: anthropic.AsyncAnthropic, model: str, tag: str, n: int, avoid: list[str]
) -> list[dict]:
    prompt = (
        f"Write {n} surprising, well-established facts for the topic '{tag}' for a party game "
        "played by young adults in India. One sentence each, under 160 characters. Only facts "
        "you are highly confident are true and that a reliable source states; give that source's "
        "URL. Nothing about real tragedies, religion or divisive politics. Do not repeat these:\n"
        + "\n".join(f"- {a}" for a in avoid)
    )
    response = await client.beta.messages.create(
        model=model,
        max_tokens=16000,
        messages=[{"role": "user", "content": prompt}],
        output_config={"effort": "high", "format": {"type": "json_schema", "schema": SCHEMA}},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if response.stop_reason == "refusal":
        return []
    text = next((b.text for b in response.content if b.type == "text"), '{"facts": []}')
    return [{**f, "tags": [tag], "reviewed": False} for f in json.loads(text)["facts"]]


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--per-tag", type=int, default=25)
    args = parser.parse_args()
    settings = get_settings()
    if settings.anthropic_api_key is None:
        raise SystemExit("Set ANTHROPIC_API_KEY first.")
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key.get_secret_value())
    existing = [f["text"] for f in json.loads(await asyncio.to_thread(Path(BANK).read_text))]
    results = await asyncio.gather(
        *(draft(client, settings.content_llm_model, tag, args.per_tag, existing) for tag in TAGS)
    )
    drafts = [f for batch in results for f in batch]
    DRAFTS.write_text(json.dumps(drafts, indent=1, ensure_ascii=False) + "\n")
    print(
        f"Wrote {len(drafts)} drafts to {DRAFTS}. Review each one before adding it to {BANK.name}."
    )


if __name__ == "__main__":
    asyncio.run(main())
