"""Room codes: 6 characters a person can read off a TV and type on a phone."""

import secrets

# No 0/O, 1/I/L: they are easy to confuse on a big screen.
ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
LENGTH = 6


def new_code() -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(LENGTH))


def normalise(code: str) -> str:
    """What a player typed -> the stored form (case-insensitive, look-alikes mapped)."""
    return code.strip().upper().replace("0", "O").replace("1", "I")


def is_valid(code: str) -> bool:
    return len(code) == LENGTH and all(c in ALPHABET for c in code)
