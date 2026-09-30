from __future__ import annotations

import re


class UnitConversionError(ValueError):
    """Raised when a unit cannot be converted safely."""


_LENGTH_TO_MM = {
    "mm": 1.0,
    "millimeter": 1.0,
    "millimeters": 1.0,
    "cm": 10.0,
    "centimeter": 10.0,
    "centimeters": 10.0,
    "m": 1000.0,
    "meter": 1000.0,
    "meters": 1000.0,
    "in": 25.4,
    "inch": 25.4,
    "inches": 25.4,
    "\"": 25.4,
    "ft": 304.8,
    "foot": 304.8,
    "feet": 304.8,
    "'": 304.8,
}

_LENGTH_PATTERN = re.compile(
    r"(?P<value>\b\d+(?:\.\d+)?)\s*(?P<unit>millimeters?|mm|centimeters?|cm|meters?|m|inches|inch|in|feet|foot|ft|\"|')\b",
    re.IGNORECASE,
)


def convert_length(value: float, from_unit: str, to_unit: str = "mm") -> float:
    from_factor = _factor(from_unit)
    to_factor = _factor(to_unit)
    return value * from_factor / to_factor


def normalize_length_to_mm(value: float, unit: str) -> float:
    return convert_length(value, unit, "mm")


def normalize_prompt_lengths_to_mm(prompt: str) -> str:
    """Replace explicit length values in a prompt with deterministic millimeter values."""

    def repl(match: re.Match[str]) -> str:
        value = float(match.group("value"))
        unit = match.group("unit")
        normalized = normalize_length_to_mm(value, unit)
        return f"{_format_number(normalized)} mm"

    return _LENGTH_PATTERN.sub(repl, prompt)


def display_length(value_mm: float, unit: str) -> float:
    if unit == "mm":
        return value_mm
    if unit in {"in", "inch"}:
        return convert_length(value_mm, "mm", "in")
    raise UnitConversionError(f"Unsupported display unit: {unit}")


def _factor(unit: str) -> float:
    key = unit.strip().lower()
    if key not in _LENGTH_TO_MM:
        raise UnitConversionError(f"Unsupported length unit: {unit}")
    return _LENGTH_TO_MM[key]


def _format_number(value: float) -> str:
    rounded = round(value, 6)
    if rounded.is_integer():
        return str(int(rounded))
    return f"{rounded:g}"
