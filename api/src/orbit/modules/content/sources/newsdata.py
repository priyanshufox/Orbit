"""NewsData.io headlines (task 9.3): India + world, English. Needs NEWSDATA_API_KEY.
Free plan: 200 credits/day, 10 articles per request; commercial use allowed."""

import httpx2

from orbit.modules.content.candidates import Candidate

API = "https://newsdata.io/api/1/latest"
CATEGORIES = "science,technology,sports,entertainment,food,lifestyle,tourism"


async def fetch(http: httpx2.AsyncClient, api_key: str, count: int) -> list[Candidate]:
    out: list[Candidate] = []
    seen: set[str] = set()
    page: str | None = None
    for country in ("in", None):  # India first, then world
        page = None
        while len(out) < count:
            params = {
                "apikey": api_key,
                "language": "en",
                "category": CATEGORIES,
                "removeduplicate": 1,
            }
            if country:
                params["country"] = country
            if page:
                params["page"] = page
            res = await http.get(API, params=params)
            res.raise_for_status()
            body = res.json()
            for article in body.get("results", []):
                title, link = article.get("title"), article.get("link")
                if not title or not link or link in seen:
                    continue
                seen.add(link)
                out.append(
                    Candidate(
                        type="news",
                        source="newsdata",
                        external_key=link,
                        payload={
                            "headline": title.strip(),
                            "outlet": article.get("source_name") or article.get("source_id"),
                        },
                        source_url=link,
                    )
                )
            page = body.get("nextPage")
            if not page:
                break
        if len(out) >= count:
            break
    return out[:count]
