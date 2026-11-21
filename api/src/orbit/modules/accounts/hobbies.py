"""The hobbies a player can pick at sign-up (up to MAX_HOBBIES). Shown on edges as reasons
("Both into Cricket and Music"), so unlike roots they are not private."""

from typing import Literal, get_args

Hobby = Literal[
    "Cricket",
    "Football",
    "Fitness",
    "Gaming",
    "Music",
    "Dancing",
    "Movies",
    "Anime",
    "Reading",
    "Writing",
    "Cooking",
    "Food",
    "Travel",
    "Photography",
    "Art",
    "Tech",
    "Fashion",
    "Trekking",
]

HOBBIES: tuple[str, ...] = get_args(Hobby)
MAX_HOBBIES = 6
