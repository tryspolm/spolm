"""
For each extracted memory candidate:
1. Vector search for similar existing memories
2. High similarity (>0.92): skip — already know this
3. Medium similarity (0.75–0.92): ask LLM whether to UPDATE existing or ADD new
4. Low similarity (<0.75): ADD as new memory
"""
import json
import re
import uuid
from typing import Any

MERGE_PROMPT = """Two memories about similar topics. Should I keep both, update the existing one, or skip the new one?

Existing: "{existing}"
New: "{new}"
Similarity: {similarity:.2f}

- UPDATE_EXISTING: new one is clearer, more accurate, or more useful
- KEEP_BOTH: genuinely different angles, both worth keeping
- SKIP: new one is redundant or weaker

Return JSON only: {{"action": "UPDATE_EXISTING|KEEP_BOTH|SKIP", "reason": "..."}}"""

HIGH_SIMILARITY = 0.92
LOW_SIMILARITY = 0.75


def process(
    *,
    driver,
    candidates: list[dict],
    run_id: str,
    user_id: str,
    agent_id: str,
    llm_model: str,
    llm_api_key: str,
    embedding_model: str,
    embedding_api_key: str,
) -> list[str]:
    """Store memory candidates into Neo4j, deduplicating against existing memories. Returns list of memory IDs written."""
    from spolm.graph import queries
    from spolm.llm import provider

    written_ids = []

    with driver.session() as session:
        for candidate in candidates:
            content = candidate["content"]
            memory_type = candidate["type"]

            embedding = provider.embed(content, model=embedding_model, api_key=embedding_api_key)
            similar = queries.get_all_memories_for_update(session, embedding=embedding, user_id=user_id, agent_id=agent_id)

            if not similar:
                mid = _write_new(session, content=content, memory_type=memory_type, confidence=0.7, embedding=embedding, user_id=user_id, agent_id=agent_id, run_id=run_id)
                written_ids.append(mid)
                continue

            best = similar[0]
            score = best.get("score", 0.0)

            if score >= HIGH_SIMILARITY:
                # Already have this — skip
                continue
            elif score >= LOW_SIMILARITY:
                action = _ask_llm_merge(
                    existing=best["content"],
                    new=content,
                    similarity=score,
                    llm_model=llm_model,
                    llm_api_key=llm_api_key,
                )
                if action == "UPDATE_EXISTING":
                    new_confidence = min(best.get("confidence", 0.7) + 0.05, 1.0)
                    queries.update_memory_content(session, memory_id=best["id"], content=content, confidence=new_confidence, embedding=embedding)
                    queries.link_memory_to_run(session, memory_id=best["id"], run_id=run_id)
                    written_ids.append(best["id"])
                elif action == "KEEP_BOTH":
                    mid = _write_new(session, content=content, memory_type=memory_type, confidence=0.7, embedding=embedding, user_id=user_id, agent_id=agent_id, run_id=run_id)
                    written_ids.append(mid)
                # SKIP: do nothing
            else:
                mid = _write_new(session, content=content, memory_type=memory_type, confidence=0.7, embedding=embedding, user_id=user_id, agent_id=agent_id, run_id=run_id)
                written_ids.append(mid)

    return written_ids


def _write_new(session, *, content, memory_type, confidence, embedding, user_id, agent_id, run_id) -> str:
    from spolm.graph import queries

    mid = str(uuid.uuid4())
    queries.create_memory(session, memory_id=mid, content=content, memory_type=memory_type, confidence=confidence, embedding=embedding, user_id=user_id, agent_id=agent_id)
    queries.link_memory_to_run(session, memory_id=mid, run_id=run_id)
    return mid


def _ask_llm_merge(*, existing: str, new: str, similarity: float, llm_model: str, llm_api_key: str) -> str:
    from spolm.llm import provider

    prompt = MERGE_PROMPT.format(existing=existing, new=new, similarity=similarity)
    try:
        raw = provider.complete(
            model=llm_model,
            messages=[
                {"role": "system", "content": "Respond with JSON only."},
                {"role": "user", "content": prompt},
            ],
            api_key=llm_api_key,
            temperature=0.1,
            max_tokens=100,
        )
        text = raw.strip()
        if text.startswith("```"):
            text = re.sub(r"^```\w*\n?", "", text)
            text = re.sub(r"\n?```\s*$", "", text).strip()
        data = json.loads(text)
        action = data.get("action", "KEEP_BOTH").upper()
        if action not in ("UPDATE_EXISTING", "KEEP_BOTH", "SKIP"):
            return "KEEP_BOTH"
        return action
    except Exception:
        return "KEEP_BOTH"
