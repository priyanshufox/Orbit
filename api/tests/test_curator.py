"""Content pipeline (Phase 9) with a fake reviewer and mocked source APIs."""

import json
from typing import Any

import httpx2
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from orbit.core.config import Settings
from orbit.modules.content import curator
from orbit.modules.content.llm import Verdict
from orbit.modules.content.models import Content


class FakeLLM:
    """Approves everything except text mentioning 'gore'; proposes one bad tag on purpose."""

    def __init__(self) -> None:
        self.reviewed: list[str] = []

    async def review(self, texts: list[str]) -> list[Verdict | None]:
        self.reviewed += texts
        out: list[Verdict | None] = []
        for t in texts:
            if "no verdict" in t:
                out.append(None)
            else:
                out.append(
                    Verdict(safe="gore" not in t, tags=["not-a-tag", "tech", "tech", "food"])
                )
        return out

    async def captions(self, templates: list[dict[str, Any]]) -> dict[str, list[str]]:
        return {
            str(t["id"]): ["When the chai is cold", "but the deadline is hot"] for t in templates
        }


def mock_apis(request: httpx2.Request) -> httpx2.Response:
    url = str(request.url)
    if url.endswith("/get_memes"):
        memes = [{"id": str(i), "name": f"Template {i}", "box_count": 2} for i in range(5)]
        return httpx2.Response(200, json={"success": True, "data": {"memes": memes}})
    if url.endswith("/caption_image"):
        tid = dict(httpx2.QueryParams(request.content.decode()))["template_id"]
        return httpx2.Response(
            200,
            json={
                "success": True,
                "data": {
                    "url": f"https://i.imgflip.com/{tid}.jpg",
                    "page_url": f"https://imgflip.com/i/{tid}",
                },
            },
        )
    if "newsdata.io" in url:
        results = [
            {
                "title": "ISRO plans new mission",
                "link": "https://n.test/1",
                "source_name": "Test News",
            },
            {"title": "Graphic gore story", "link": "https://n.test/2", "source_name": "Test News"},
            {
                "title": "Cricket: no verdict",
                "link": "https://n.test/3",
                "source_name": "Test News",
            },
        ]
        return httpx2.Response(200, json={"results": results, "nextPage": None})
    return httpx2.Response(404)


async def test_curator_fetches_reviews_and_stores(
    db: AsyncSession, test_settings: Settings
) -> None:
    settings = test_settings.model_copy(
        update={
            "imgflip_username": "u",
            "imgflip_password": SecretStr("p"),
            "newsdata_api_key": SecretStr("k"),
            "memes_per_day": 3,
            "news_per_day": 3,
        }
    )
    llm = FakeLLM()
    async with httpx2.AsyncClient(transport=httpx2.MockTransport(mock_apis)) as http:
        report = await curator.run(db, settings, llm=llm, http=http)

    assert report == {"fetched": 6, "approved": 4, "rejected": 2, "stored": 4}
    rows = (
        await db.scalars(select(Content).where(Content.source.in_(["imgflip", "newsdata"])))
    ).all()
    assert {r.type for r in rows} == {"meme", "news"}
    assert all(r.active and r.tags == ["tech", "food"] for r in rows)  # bad tag dropped, deduped
    assert not any("gore" in json.dumps(r.payload).lower() for r in rows)

    # Running again stores nothing new.
    async with httpx2.AsyncClient(transport=httpx2.MockTransport(mock_apis)) as http:
        again = await curator.run(db, settings, llm=FakeLLM(), http=http)
    assert again["stored"] == 0


async def test_without_llm_key_nothing_is_stored(db: AsyncSession, test_settings: Settings) -> None:
    settings = test_settings.model_copy(
        update={"anthropic_api_key": None, "newsdata_api_key": SecretStr("k")}
    )
    assert await curator.run(db, settings) == {
        "fetched": 0,
        "approved": 0,
        "rejected": 0,
        "stored": 0,
    }


def test_valid_tags() -> None:
    assert curator.valid_tags(["x", "food", "food", "tech", "science", "travel"]) == [
        "food",
        "tech",
        "science",
    ]
