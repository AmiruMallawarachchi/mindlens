"""User memory preference and extraction persistence helpers."""

from __future__ import annotations

import datetime
from typing import Any

from pymongo.errors import DuplicateKeyError


async def _ensure_user_memory_doc(db: Any, user_id: str, now: datetime.datetime) -> None:
    """Best-effort bootstrap of an empty `user_memory` document, used before
    any write that itself needs to be a plain (non-upsert) update.

    Not gated on any check — nothing gates chat behind onboarding completion,
    so a session can run without a `user_memory` document ever having been
    created. A concurrent writer for the same `user_id` (a second backend
    process, in a horizontally-scaled deployment) creating the document first
    raises `DuplicateKeyError` on the unique index in `db.py` — that's the
    other writer doing this job for us, not a failure, so it's swallowed
    rather than crashing this turn.
    """
    try:
        await db.user_memory.update_one(
            {"user_id": user_id},
            {"$setOnInsert": {"user_id": user_id, "created_at": now}},
            upsert=True,
        )
    except DuplicateKeyError:
        pass


async def _save_introvert_score(
    db: Any,
    user_id: str,
    result: dict[str, Any],
) -> None:
    """Persist PersonalityAgent's updated social-disposition score.

    This is the write that closes the personality loop. Before it existed the
    agent computed a score into its output metadata every turn and nothing
    read it back, so RoutineAgent's introvert/extrovert branches could never
    fire — the classic dead control.

    Uses a dotted `$set` so only this one field moves: `preferences` also
    carries the user's typed settings (tone, modality, custom instructions),
    and writing the whole subdocument would silently wipe them.

    Bootstraps the document via `_ensure_user_memory_doc` rather than
    combining `$set` and `$setOnInsert` in one `upsert=True` call — that
    combined form loses the score update entirely if it races a concurrent
    upsert for the same user and hits the unique index (see that helper's
    docstring). Splitting the bootstrap out means this write can be a plain,
    race-free update once the document is guaranteed to exist.
    """
    for output in result.get("agent_outputs", []):
        if output.get("agent") != "personality":
            continue
        metadata = output.get("metadata") or {}
        if metadata.get("skipped"):
            return
        score = (metadata.get("score_update") or {}).get("introvert_score")
        if not isinstance(score, (int, float)):
            return

        now = datetime.datetime.now(datetime.UTC)
        await _ensure_user_memory_doc(db, user_id, now)
        await db.user_memory.update_one(
            {"user_id": user_id},
            {"$set": {"preferences.introvert_score": float(score), "updated_at": now}},
        )
        return


async def _save_extracted_memory(
    db: Any,
    user_id: str,
    result: dict[str, Any],
) -> None:
    """Persist SessionMemorySave's heuristic extraction — a person, a hard
    topic, or a coping strategy this turn actually mentioned.

    This is the write that makes the Memory page's promise true. Before it
    existed, `user_memory` was fully readable and editable but nothing
    populated it automatically: "What's been hard" / "What's helped" could
    only be filled through an admin-only endpoint, and a new person only
    through the onboarding wizard — never from an ordinary conversation.

    A newly-mentioned person is written in two steps rather than one
    conditional upsert: `update_one` with `upsert=True` on a filter that
    includes `"people.<name>": {"$exists": False}` would, the moment that
    name already exists, match zero documents and then *insert a second*
    `user_memory` document for the same user — colliding with the unique
    index on `user_id` and crashing this turn's save. Bootstrapping the
    document first (`_ensure_user_memory_doc`) and then applying the
    conditional set with no upsert flag makes a name that's already on file
    a safe no-op instead, and never overwrites a person the user edited by
    hand on the Memory page. Topics and coping strategies use `$addToSet`,
    which is idempotent and append-only for the same reason, and go through
    the same bootstrap-then-plain-update shape to stay race-free.
    """
    for output in result.get("agent_outputs", []):
        if output.get("agent") != "session_memory_save":
            continue
        extracted = (output.get("metadata") or {}).get("extracted") or {}
        if not extracted:
            return

        now = datetime.datetime.now(datetime.UTC)

        # Every person the turn introduced, not just the first: one sentence
        # can name two ("my boyfriend called Hasanka and my mum's name is
        # Rehana") and dropping the rest broke the Memory page's promise for
        # exactly the turns where the user was deliberately listing people.
        # Falls back to the single-person keys so an older payload shape
        # still writes.
        people = extracted.get("people")
        if not people and extracted.get("person_name"):
            people = [
                {
                    "name": extracted["person_name"],
                    "relation": extracted.get("person_relation", ""),
                }
            ]
        if people:
            await _ensure_user_memory_doc(db, user_id, now)
            for person in people:
                person_name = person.get("name")
                # A dot or a leading $ in a key is not a legal Mongo field
                # path; a name carrying one would make the whole update
                # fail, taking the other people in the same turn with it.
                if not person_name or "." in person_name or person_name.startswith("$"):
                    continue
                await db.user_memory.update_one(
                    {"user_id": user_id, f"people.{person_name}": {"$exists": False}},
                    {
                        "$set": {
                            f"people.{person_name}": {
                                "role": person.get("relation", ""),
                                "context": "",
                                "sentiment": "neutral",
                            },
                            "updated_at": now,
                        }
                    },
                )

        add_to_set: dict[str, Any] = {}
        topic = extracted.get("trigger_topic")
        coping = extracted.get("effective_coping")
        if topic:
            add_to_set["emotional_patterns.trigger_topics"] = topic
        if coping:
            add_to_set["emotional_patterns.effective_coping"] = coping
        if add_to_set:
            await _ensure_user_memory_doc(db, user_id, now)
            await db.user_memory.update_one(
                {"user_id": user_id},
                {"$addToSet": add_to_set, "$set": {"updated_at": now}},
            )
        return

