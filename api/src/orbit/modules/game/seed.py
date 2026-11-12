"""Dev seed: 15 questions across the three kinds. A starting point for the real bank (task 4.1)."""

from typing import Any
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from orbit.modules.game.models import Question


def _single(prompt: str, choices: list[str], *tags: str) -> dict[str, Any]:
    return {"kind": "single", "prompt": prompt, "options": {"choices": choices}, "tags": list(tags)}


def _multi(prompt: str, choices: list[str], *tags: str) -> dict[str, Any]:
    return {"kind": "multi", "prompt": prompt, "options": {"choices": choices}, "tags": list(tags)}


def _slider(prompt: str, low: str, high: str, *tags: str) -> dict[str, Any]:
    options = {"min_label": low, "max_label": high}
    return {"kind": "slider", "prompt": prompt, "options": options, "tags": list(tags)}


DEV_QUESTIONS = [
    _single(
        "It's Friday night. You're most likely...",
        [
            "Out with a big group",
            "Dinner with one or two close friends",
            "Home with a show or game",
            "Still working",
        ],
        "social",
    ),
    _single("Pick a holiday", ["Mountains", "Beach", "A new city", "Staycation"], "travel"),
    _single(
        "Your phone is at 5%. You...",
        ["Panic and find a charger", "Let it die", "Low power mode and carry on"],
        "habits",
    ),
    _single(
        "Morning person or night owl?", ["Early bird", "Night owl", "Depends on the day"], "habits"
    ),
    _single(
        "Group trip planning: your role?",
        [
            "Planner with the spreadsheet",
            "Budget keeper",
            "Tell me when to show up",
            "Books last minute",
        ],
        "travel",
        "social",
    ),
    _single("Chai or coffee?", ["Chai", "Coffee", "Both", "Neither"], "food"),
    _multi(
        "What would you watch tonight?",
        ["Cricket match", "Bollywood film", "Stand-up special", "Documentary", "Anime"],
        "entertainment",
    ),
    _multi(
        "Hobbies you actually do",
        ["Sports", "Gaming", "Music", "Reading", "Cooking", "Travel", "Art"],
        "hobbies",
    ),
    _multi(
        "What starts a group chat argument for you?",
        ["Food", "Cricket", "Movies", "Tech", "Nothing, I just send memes"],
        "social",
    ),
    _multi("Your comfort foods", ["Maggi", "Biryani", "Pizza", "Dal chawal", "Momos"], "food"),
    _slider("How much do you plan your day?", "Go with the flow", "Every hour planned", "habits"),
    _slider("In a group, how much do you talk?", "Mostly listen", "Mostly talk", "social"),
    _slider("How competitive are you in games?", "Here for fun", "Must win", "hobbies"),
    _slider(
        "How spontaneous are your trips?", "Booked months ahead", "Leaving in an hour", "travel"
    ),
    _slider("How much do you share online?", "Lurker", "Post everything", "social"),
]


async def seed(session: AsyncSession) -> int:
    rows = [{"id": uuid5(NAMESPACE_URL, f"orbit-dev-q:{q['prompt']}"), **q} for q in DEV_QUESTIONS]
    res = await session.execute(insert(Question).values(rows).on_conflict_do_nothing())
    return res.rowcount
