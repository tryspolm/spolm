from datetime import datetime, timezone
from typing import Any


def retrieve(
    *,
    driver,
    task: str,
    user_id: str,
    agent_id: str,
    embedding_model: str,
    embedding_api_key: str,
    top_k: int = 8,
) -> dict[str, Any]:
    """Return memories and recent similar runs for a given task."""
    from spolm.graph import queries
    from spolm.llm import provider

    task_embedding = provider.embed(task, model=embedding_model, api_key=embedding_api_key)

    with driver.session() as session:
        raw_memories = queries.search_similar_memories(
            session,
            embedding=task_embedding,
            user_id=user_id,
            agent_id=agent_id,
            top_k=top_k,
        )
        recent_runs = queries.get_recent_runs(session, user_id=user_id, agent_id=agent_id, limit=3)

    memories = _rerank(raw_memories)
    return {"memories": memories, "recent_runs": recent_runs}


def _rerank(memories: list[dict]) -> list[dict]:
    """Re-rank by similarity × confidence × recency decay."""
    now = datetime.now(timezone.utc)
    scored = []
    for m in memories:
        similarity = m.get("score", 0.0)
        confidence = m.get("confidence", 0.5)
        recency = _recency_score(m.get("created_at"), now)
        combined = similarity * 0.5 + confidence * 0.35 + recency * 0.15
        scored.append({**m, "relevance": round(combined, 3)})
    scored.sort(key=lambda x: x["relevance"], reverse=True)
    return scored


def _recency_score(created_at, now: datetime) -> float:
    if not created_at:
        return 0.5
    try:
        if hasattr(created_at, "to_native"):
            created_at = created_at.to_native()
        elif isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        days_old = (now - created_at).days
        return max(0.0, 1.0 - days_old / 90)  # Decays to 0 over 90 days
    except Exception:
        return 0.5
