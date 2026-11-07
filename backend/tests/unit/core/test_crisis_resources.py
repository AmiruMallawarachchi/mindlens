"""The crisis contact list is safety-critical data, not decoration.

The property that matters most here is the last one: with no country on file,
the app must not present one country's numbers to the whole user base. That
was the original behaviour — a fixed Sri Lankan list served to everyone — and
it is asserted against so it cannot come back.
"""

from __future__ import annotations

from app.core.crisis_resources import (
    INTERNATIONAL_RESOURCES,
    known_countries,
    resources_for,
)


def test_every_row_is_rendered_row_shaped() -> None:
    for code in [*known_countries(), "ZZ", None, ""]:
        rows = resources_for(code)
        assert rows, f"no rows for {code!r}"
        assert all(set(row) == {"name", "number"} for row in rows)
        assert all(row["name"] and row["number"] for row in rows)


def test_country_rows_come_first_and_international_always_follow() -> None:
    rows = resources_for("GB")
    assert rows[0]["name"] == "Samaritans (UK)"
    assert rows[-len(INTERNATIONAL_RESOURCES):] == INTERNATIONAL_RESOURCES


def test_unknown_country_still_reaches_a_real_service() -> None:
    assert resources_for("ZZ") == INTERNATIONAL_RESOURCES


def test_country_code_is_case_and_space_insensitive() -> None:
    assert resources_for("us") == resources_for(" US ") == resources_for("US")


def test_no_country_never_yields_a_single_country_s_numbers() -> None:
    """The regression this file exists to prevent."""
    numbers = {row["number"] for row in resources_for(None)}
    assert numbers == {row["number"] for row in INTERNATIONAL_RESOURCES}
    assert not any(name in numbers for name in ("1926", "119 / 110", "988", "116 123"))


def test_every_country_row_names_its_country() -> None:
    """A number is only safe to dial if the reader can tell whose number it is."""
    for code in known_countries():
        for row in resources_for(code):
            if row in INTERNATIONAL_RESOURCES:
                continue
            assert "(" in row["name"] and row["name"].endswith(")"), row["name"]
