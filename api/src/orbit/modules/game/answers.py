"""Answer validation per question kind. Pure."""

from typing import Any


class InvalidAnswerError(ValueError):
    pass


def validate(kind: str, options: dict[str, Any], value: dict[str, Any]) -> dict[str, Any]:
    """Return the canonical stored form, or raise InvalidAnswerError.

    single: {"choice": i}; multi: {"choices": [i, ...]} (sorted, unique, may be empty);
    slider: {"value": 0..1}.
    """
    if kind in ("single", "multi"):
        n = len(options.get("choices", []))
        if kind == "single":
            choice = value.get("choice")
            if not isinstance(choice, int) or isinstance(choice, bool) or not 0 <= choice < n:
                raise InvalidAnswerError("choice out of range")
            return {"choice": choice}
        choices = value.get("choices")
        if not isinstance(choices, list) or not all(
            isinstance(c, int) and not isinstance(c, bool) and 0 <= c < n for c in choices
        ):
            raise InvalidAnswerError("choices out of range")
        return {"choices": sorted(set(choices))}
    if kind == "slider":
        v = value.get("value")
        if not isinstance(v, int | float) or isinstance(v, bool) or not 0 <= v <= 1:
            raise InvalidAnswerError("slider value must be between 0 and 1")
        return {"value": round(float(v), 4)}
    raise InvalidAnswerError(f"unknown kind {kind}")
