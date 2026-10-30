"""Unit tests for heuristic memory extraction."""

from __future__ import annotations

import pytest
from app.services.memory_extraction import extract_memory


class TestMemoryExtraction:
    """These pin the rules that decide what is allowed to become durable
    memory. A bad write here is replayed into every future prompt, so the
    false-positive cases matter as much as the extraction cases."""

    async def test_extracts_a_person_forward_order(self) -> None:
        """'My sister Amaya' — capitalised at the start of a sentence, which
        a case-sensitive match on 'my' would have missed entirely."""
        extracted = extract_memory("My sister Amaya called me today and it was nice.")
        assert extracted["person_relation"] == "sister"
        assert extracted["person_name"] == "Amaya"

    async def test_person_name_casing_is_normalized(self) -> None:
        """"AMAYA" and "amaya" must collapse to the same `people` key as
        "Amaya" — otherwise the same person shows up multiple times on the
        Memory page depending on how a message happened to capitalize them."""
        extracted = extract_memory("My sister AMAYA called today.")
        assert extracted["person_name"] == "Amaya"

    async def test_extracts_every_person_in_one_message(self) -> None:
        """One sentence naming two people must save both.

        A user who wrote "i have a boyfriend called Hasanka and my mum's
        name is Rehana" and then "remember those people" got neither
        stored: the relation had to sit directly against the name, so
        "called"/"name is" both missed, and even once matched only the
        first person was returned.
        """
        extracted = extract_memory(
            "i have a boyfriend called Hasanka and my mum's name is Rehana, "
            "remember those people"
        )
        people = extracted["people"]
        assert {p["name"] for p in people} == {"Hasanka", "Rehana"}
        assert {p["relation"] for p in people} == {"boyfriend", "mum"}

    @pytest.mark.parametrize(
        ("text", "relation", "name"),
        [
            ("my boyfriend called Hasanka", "boyfriend", "Hasanka"),
            ("my boyfriend named Hasanka", "boyfriend", "Hasanka"),
            ("my mum's name is Rehana", "mum", "Rehana"),
            ("my moms name is Rehana", "mom", "Rehana"),
            ("I have a friend called Alex", "friend", "Alex"),
            # "mother" must win over "mom" in the alternation, or this
            # stores the relation as "mom" and leaves a stray "her".
            ("my mother Rehana", "mother", "Rehana"),
        ],
    )
    async def test_natural_introduction_phrasings(
        self, text: str, relation: str, name: str
    ) -> None:
        """Only bare adjacency ("my sister Amaya") used to match, so the
        ordinary ways people introduce someone all recorded nobody."""
        extracted = extract_memory(text)
        assert extracted["person_name"] == name
        assert extracted["person_relation"] == relation

    @pytest.mark.parametrize(
        ("text", "name"),
        [
            ("my mums name is rehana", "Rehana"),
            ("i have a boyfriend called hasanka", "Hasanka"),
            ("my best friend named alex", "Alex"),
        ],
    )
    async def test_lowercase_names_are_stored_when_explicitly_declared(
        self, text: str, name: str
    ) -> None:
        """People type their own lives in lowercase. Requiring a capital
        taught the user they had to punctuate correctly to be heard. After
        "called"/"name is" the sentence has already declared a name is
        coming, so case carries no information there — it is only load-
        bearing for bare adjacency ("my sister Amaya")."""
        extracted = extract_memory(text)
        assert extracted["person_name"] == name

    @pytest.mark.parametrize(
        "text",
        [
            "my sister called me",
            "my mum called me today",
            "my friend called and said hi",
            "my brother called us back",
        ],
    )
    async def test_called_me_does_not_store_a_person_named_me(self, text: str) -> None:
        """Accepting lowercase after "called" makes "my sister called me"
        look exactly like "my sister called alex" — so the pronouns and
        common adverbs that actually follow "called" are excluded."""
        assert "person_name" not in extract_memory(text)

    @pytest.mark.parametrize(
        "text",
        [
            "my mum is Sri Lankan",
            "my dad is Buddhist",
            "my sister is Australian",
        ],
    )
    async def test_bare_is_does_not_invent_a_person(self, text: str) -> None:
        """A bare "is" is not accepted as a naming connector. It would catch
        "my mum is Rehana", but these have the identical shape — and a bad
        write here persists and is replayed into every future prompt, while
        a missed name only costs one fact the user can add in Memory."""
        extracted = extract_memory(text)
        assert "people" not in extracted
        assert "person_name" not in extracted

    async def test_extracts_a_person_reverse_order(self) -> None:
        extracted = extract_memory("Amaya, my sister, called me today")
        assert extracted["person_relation"] == "sister"
        assert extracted["person_name"] == "Amaya"

    async def test_extracts_a_two_word_name(self) -> None:
        """"My supervisor Dr Perera" used to capture only the first token,
        storing the person as "Dr" — a title, not a name — so every later
        mention of Perera failed to recall anything."""
        extracted = extract_memory("My supervisor Dr Perera keeps pushing my deadline back.")
        assert extracted["person_relation"] == "supervisor"
        assert extracted["person_name"] == "Dr Perera"

    async def test_extracts_from_raw_text(self) -> None:
        """The caller passes the un-anonymised message: anonymize() would
        have turned "Dr Perera" into "[NAME]" before this could see it."""
        extracted = extract_memory(
            "My supervisor Dr Perera keeps pushing my deadline back."
        )
        assert extracted["person_name"] == "Dr Perera"

    async def test_two_word_name_casing_is_normalized_per_word(self) -> None:
        """A single .capitalize() over the whole string turned "MARY JANE"
        into "Mary jane" — wrong on the second word."""
        extracted = extract_memory("My mom MARY JANE called today.")
        assert extracted["person_name"] == "Mary Jane"

    async def test_extracts_a_two_word_name_reverse_order(self) -> None:
        extracted = extract_memory("Dr Perera, my supervisor, emailed again.")
        assert extracted["person_relation"] == "supervisor"
        assert extracted["person_name"] == "Dr Perera"

    async def test_extracts_a_hard_topic_on_a_negative_turn(self) -> None:
        extracted = extract_memory(
            "I feel anxious about my exam tomorrow.", valence="negative"
        )
        assert extracted["trigger_topic"] == "exams"

    async def test_does_not_flag_a_topic_mentioned_calmly(self) -> None:
        """A topic keyword alone isn't enough — "exams are done, I'm
        relieved" shouldn't get filed under "what's been hard"."""
        extracted = extract_memory(
            "My exams are finally done and I feel relieved.",
            distress_level=0.2,
            valence="positive",
        )
        assert "trigger_topic" not in extracted

    async def test_extracts_coping_only_with_a_helped_phrase(self) -> None:
        extracted = extract_memory("Going for a walk really helped me calm down.")
        assert extracted["effective_coping"] == "going for a walk"

    async def test_mentioning_an_activity_without_helped_extracts_nothing(self) -> None:
        """The keyword alone isn't a coping strategy — only pairing it with
        a "helped" phrase counts, otherwise "I went for a walk and then had
        a huge fight" would get filed as something that helped."""
        extracted = extract_memory("I went for a walk earlier.")
        assert "effective_coping" not in extracted

    async def test_ordinary_turn_extracts_nothing(self) -> None:
        assert extract_memory("nothing interesting happened today") == {}

    async def test_memory_depth_nothing_disables_extraction(self) -> None:
        """Settings > Memory depth = Nothing also stops new memory from
        accumulating, not just recall."""
        extracted = extract_memory(
            "My sister Amaya called, my exam went badly, a walk helped.",
            memory_depth="nothing",
            valence="negative",
        )
        assert extracted == {}
