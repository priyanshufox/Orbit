"""Daily content curator (task 9.1): fetch -> review (tag + moderate) -> store.

Rooms only read the `content` table, so no round depends on an outside API being up. Every
source is optional: it runs only when its key is set. Without ANTHROPIC_API_KEY nothing new is
stored, because nothing can be moderated (9.5).
"""

from dataclasses import dataclass
from datetime import UTC, datetime

import httpx2
import structlog
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from orbit.core.config import Settings
from orbit.modules.content.candidates import Candidate
from orbit.modules.content.llm import ClaudeContentLLM, ContentLLM
from orbit.modules.content.models import Content
from orbit.modules.content.sources import imgflip, newsdata
from orbit.modules.content.tags import TAGS

log = structlog.get_logger("orbit.content")

REVIEW_BATCH = 25


@dataclass
class Report:
    fetched: int = 0
    approved: int = 0
    rejected: int = 0
    stored: int = 0

    def asdict(self) -> dict[str, int]:
        return dict(self.__dict__)


def valid_tags(tags: list[str]) -> list[str]:
    """Only tags from the fixed list survive; at most 3, order kept, no repeats."""
    out: list[str] = []
    for t in tags:
        if t in TAGS and t not in out:
            out.append(t)
    return out[:3]


async def review(llm: ContentLLM, candidates: list[Candidate], report: Report) -> list[Candidate]:
    approved = []
    for start in range(0, len(candidates), REVIEW_BATCH):
        batch = candidates[start : start + REVIEW_BATCH]
        verdicts = await llm.review([c.text_for_review() for c in batch])
        for c, v in zip(batch, verdicts, strict=True):
            tags = valid_tags(v.tags) if v else []
            if v and v.safe and tags:
                c.tags = tags
                approved.append(c)
            else:
                report.rejected += 1
    report.approved += len(approved)
    return approved


async def store(session: AsyncSession, items: list[Candidate]) -> int:
    if not items:
        return 0
    rows = [
        {
            "id": c.id,
            "type": c.type,
            "source": c.source,
            "source_url": c.source_url,
            "payload": c.payload,
            "tags": c.tags,
            "active": True,  # passed moderation
        }
        for c in items
    ]
    result = await session.execute(
        insert(Content).values(rows).on_conflict_do_nothing().returning(Content.id)
    )
    stored = len(result.all())
    await session.commit()
    return stored


async def run(
    session: AsyncSession,
    settings: Settings,
    *,
    llm: ContentLLM | None = None,
    http: httpx2.AsyncClient | None = None,
) -> dict[str, int]:
    report = Report()
    if llm is None:
        if settings.anthropic_api_key is None:
            log.warning(
                "content.skipped", reason="ANTHROPIC_API_KEY not set; nothing can be moderated"
            )
            return report.asdict()
        llm = ClaudeContentLLM(
            settings.anthropic_api_key.get_secret_value(), settings.content_llm_model
        )

    own_http = http is None
    http = http or httpx2.AsyncClient(timeout=30)
    candidates: list[Candidate] = []
    try:
        if settings.imgflip_username and settings.imgflip_password:
            try:
                candidates += await imgflip.fetch(
                    http,
                    llm,
                    settings.imgflip_username,
                    settings.imgflip_password.get_secret_value(),
                    settings.memes_per_day,
                    seed=int(datetime.now(UTC).strftime("%Y%m%d")),
                )
            except Exception:
                log.exception("content.source_failed", source="imgflip")
        if settings.newsdata_api_key:
            try:
                candidates += await newsdata.fetch(
                    http, settings.newsdata_api_key.get_secret_value(), settings.news_per_day
                )
            except Exception:
                log.exception("content.source_failed", source="newsdata")
    finally:
        if own_http:
            await http.aclose()

    report.fetched = len(candidates)
    report.stored = await store(session, await review(llm, candidates, report))
    log.info("content.curated", **report.asdict())
    return report.asdict()
