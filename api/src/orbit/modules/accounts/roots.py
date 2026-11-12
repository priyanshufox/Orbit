"""Place and school name normalisation for matching shared roots (design: Data model).

Roots are stored as the player typed them (tidied); scoring compares the normalised forms, so
"Bombay", " mumbai " and "Mumbai." all match. Pure functions, no I/O.
"""

import re
import unicodedata

# Old or alternative names -> the name we match on. Extend as real rooms show misses.
CITY_ALIASES: dict[str, str] = {
    "bombay": "mumbai",
    "bangalore": "bengaluru",
    "calcutta": "kolkata",
    "madras": "chennai",
    "poona": "pune",
    "gurgaon": "gurugram",
    "new delhi": "delhi",
    "trivandrum": "thiruvananthapuram",
    "baroda": "vadodara",
    "mysore": "mysuru",
    "mangalore": "mangaluru",
    "cochin": "kochi",
    "vizag": "visakhapatnam",
    "banaras": "varanasi",
    "benares": "varanasi",
    "allahabad": "prayagraj",
    "pondicherry": "puducherry",
    "simla": "shimla",
    "cawnpore": "kanpur",
    "belgaum": "belagavi",
    "hubli": "hubballi",
}

_NON_WORD = re.compile(r"[^\w\s]")
_SPACES = re.compile(r"\s+")


def tidy(text: str) -> str:
    """Display form: trimmed, single spaces. Keeps the player's casing."""
    return _SPACES.sub(" ", text).strip()


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = _NON_WORD.sub(" ", text.lower())
    return _SPACES.sub(" ", text).strip()


def normalise_city(city: str) -> str:
    folded = _fold(city)
    return CITY_ALIASES.get(folded, folded)


def normalise_school(school: str) -> str:
    return _fold(school)
