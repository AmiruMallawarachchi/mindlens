"""Crisis contact rows returned to the UI.

These are data, not model output. The crisis path never calls Groq, and the
client renders this list as contact rows beside the template response.

The country comes from Settings > General ("Where you are"), which is the only
place this app learns a location — there is no IP or timezone sniffing here.
Without it the rows are the international directories, never a single country's
numbers: an app used from many places must not guess that a stranger in crisis
is Sri Lankan.

The international rows are appended for every country, so a wrong or missing
country code still leaves someone with a way to reach a real person.
"""

from __future__ import annotations

# ISO 3166-1 alpha-2 -> contact rows. Numbers are the ones published by the
# service itself; each row names the service so a reader can verify it.
_COUNTRY_RESOURCES: dict[str, list[dict[str, str]]] = {
    "LK": [
        {"name": "Sumithrayo (Sri Lanka)", "number": "011 269 6666"},
        {"name": "NIMH National Mental Health Helpline (Sri Lanka)", "number": "1926"},
        {"name": "Emergency services (Sri Lanka)", "number": "119 / 110"},
    ],
    "US": [
        {"name": "988 Suicide & Crisis Lifeline (US)", "number": "988"},
        {"name": "Crisis Text Line (US)", "number": "text HOME to 741741"},
        {"name": "Emergency services (US)", "number": "911"},
    ],
    "GB": [
        {"name": "Samaritans (UK)", "number": "116 123"},
        {"name": "NHS 111, option 2 (UK)", "number": "111"},
        {"name": "Emergency services (UK)", "number": "999"},
    ],
    "IE": [
        {"name": "Samaritans (Ireland)", "number": "116 123"},
        {"name": "Emergency services (Ireland)", "number": "112 / 999"},
    ],
    "AU": [
        {"name": "Lifeline (Australia)", "number": "13 11 14"},
        {"name": "Emergency services (Australia)", "number": "000"},
    ],
    "NZ": [
        {"name": "Youthline (New Zealand)", "number": "0800 376 633"},
        {"name": "Emergency services (New Zealand)", "number": "111"},
    ],
    "CA": [
        {"name": "Talk Suicide Canada (Canada)", "number": "1-833-456-4566"},
        {"name": "Emergency services (Canada)", "number": "911"},
    ],
    "IN": [
        {"name": "Tele-MANAS (India)", "number": "14416"},
        {"name": "KIRAN Mental Health Helpline (India)", "number": "1800-599-0019"},
        {"name": "Emergency services (India)", "number": "112"},
    ],
    "ZA": [
        {"name": "SADAG Suicide Crisis Line (South Africa)", "number": "0800 567 567"},
        {"name": "Emergency services (South Africa)", "number": "10111"},
    ],
    "DE": [
        {"name": "Telefonseelsorge (Germany)", "number": "0800 111 0 111"},
        {"name": "Emergency services (Germany)", "number": "112"},
    ],
    "FR": [
        {"name": "3114 suicide écoute (France)", "number": "3114"},
        {"name": "Emergency services (France)", "number": "112"},
    ],
}

# Always shown, and shown alone when no country is on file.
INTERNATIONAL_RESOURCES: list[dict[str, str]] = [
    {
        "name": "Emergency services",
        "number": "your local emergency number",
    },
    {
        "name": "Find A Helpline - directory of 170+ countries",
        "number": "findahelpline.com",
    },
    {
        "name": "Befrienders Worldwide - emotional support",
        "number": "befrienders.org",
    },
]


def resources_for(country: str | None) -> list[dict[str, str]]:
    """Rows for one country, then the international fallbacks.

    Unknown or missing country codes are not an error — they simply get the
    international rows, which work from anywhere.
    """
    key = (country or "").strip().upper()
    rows = list(_COUNTRY_RESOURCES.get(key, []))
    rows.extend(INTERNATIONAL_RESOURCES)
    return rows


def known_countries() -> list[str]:
    """Country codes this module has direct numbers for, for the Settings list."""
    return sorted(_COUNTRY_RESOURCES)
