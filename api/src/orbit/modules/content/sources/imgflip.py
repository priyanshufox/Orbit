"""Imgflip memes (task 9.2): top templates -> Claude captions -> rendered by /caption_image.
Free tier adds a small watermark. Needs IMGFLIP_USERNAME / IMGFLIP_PASSWORD."""

import random

import httpx2
import structlog

from orbit.modules.content.candidates import Candidate
from orbit.modules.content.llm import ContentLLM

log = structlog.get_logger("orbit.content")

API = "https://api.imgflip.com"


async def fetch(
    http: httpx2.AsyncClient, llm: ContentLLM, username: str, password: str, count: int, seed: int
) -> list[Candidate]:
    res = await http.get(f"{API}/get_memes")
    res.raise_for_status()
    templates = [m for m in res.json()["data"]["memes"] if 1 <= m["box_count"] <= 3]
    picked = random.Random(seed).sample(templates[:100], min(count, len(templates)))  # noqa: S311
    captions = await llm.captions(picked)

    out = []
    for template in picked:
        texts = captions.get(str(template["id"]))
        if not texts:
            continue
        form = {"template_id": template["id"], "username": username, "password": password}
        form.update({f"boxes[{i}][text]": t for i, t in enumerate(texts[: template["box_count"]])})
        made = await http.post(f"{API}/caption_image", data=form)
        body = made.json()
        if not body.get("success"):
            log.warning(
                "content.imgflip_failed", template=template["id"], error=body.get("error_message")
            )
            continue
        out.append(
            Candidate(
                type="meme",
                source="imgflip",
                external_key=body["data"]["url"],
                payload={
                    "image_url": body["data"]["url"],
                    "template": template["name"],
                    "caption": " / ".join(texts),
                },
                source_url=body["data"]["page_url"],
            )
        )
    return out
