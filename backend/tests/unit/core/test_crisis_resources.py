"""The crisis contact list is safety-critical data, not decoration."""

from __future__ import annotations

from app.core.crisis_resources import CRISIS_RESOURCES


def test_crisis_resources_are_rendered_row_shaped() -> None:
    assert len(CRISIS_RESOURCES) >= 3
    assert all(set(row) == {"name", "number"} for row in CRISIS_RESOURCES)
    assert all(row["name"] and row["number"] for row in CRISIS_RESOURCES)


def test_crisis_resources_include_the_mandatory_numbers() -> None:
    numbers = {row["number"] for row in CRISIS_RESOURCES}
    assert "1926" in numbers
    assert "119 / 110" in numbers
