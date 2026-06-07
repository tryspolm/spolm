import json
import uuid
from datetime import datetime, timezone
from typing import Any


def upsert_user(session, user_id: str) -> None:
    session.run(
        "MERGE (u:User {user_id: $user_id}) ON CREATE SET u.created_at = datetime()",
        user_id=user_id,
    )


def upsert_agent(session, agent_id: str, user_id: str) -> None:
    session.run(
        "MERGE (a:Agent {agent_id: $agent_id}) ON CREATE SET a.created_at = datetime()",
        agent_id=agent_id,
    )
    session.run(
        """
        MATCH (u:User {user_id: $user_id})
        MATCH (a:Agent {agent_id: $agent_id})
        MERGE (u)-[:HAS_AGENT]->(a)
        """,
        user_id=user_id,
        agent_id=agent_id,
    )


def create_run(session, *, run_id: str, agent_id: str, task: str, outcome: str, summary: str, embedding: list[float], trajectory: list = None, result: Any = None) -> None:
    session.run(
        """
        MERGE (r:Run {id: $run_id})
        SET r.agent_id = $agent_id,
            r.task = $task,
            r.outcome = $outcome,
            r.summary = $summary,
            r.embedding = $embedding,
            r.trajectory = $trajectory,
            r.result = $result,
            r.created_at = datetime()
        """,
        run_id=run_id,
        agent_id=agent_id,
        task=task,
        outcome=outcome,
        summary=summary,
        embedding=embedding,
        trajectory=json.dumps(trajectory or []),
        result=json.dumps(result) if result is not None else None,
    )
    session.run(
        """
        MATCH (a:Agent {agent_id: $agent_id})
        MATCH (r:Run {id: $run_id})
        MERGE (a)-[:EXECUTED]->(r)
        """,
        agent_id=agent_id,
        run_id=run_id,
    )


def create_memory(session, *, memory_id: str, content: str, memory_type: str, confidence: float, embedding: list[float], user_id: str, agent_id: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    session.run(
        """
        MERGE (m:Memory {id: $memory_id})
        SET m.content = $content,
            m.type = $type,
            m.confidence = $confidence,
            m.embedding = $embedding,
            m.user_id = $user_id,
            m.agent_id = $agent_id,
            m.use_count = 0,
            m.created_at = $now,
            m.updated_at = $now
        """,
        memory_id=memory_id,
        content=content,
        type=memory_type,
        confidence=confidence,
        embedding=embedding,
        user_id=user_id,
        agent_id=agent_id,
        now=now,
    )


def update_memory_content(session, *, memory_id: str, content: str, confidence: float, embedding: list[float]) -> None:
    session.run(
        """
        MATCH (m:Memory {id: $memory_id})
        SET m.content = $content,
            m.confidence = $confidence,
            m.embedding = $embedding,
            m.updated_at = $now
        """,
        memory_id=memory_id,
        content=content,
        confidence=confidence,
        embedding=embedding,
        now=datetime.now(timezone.utc).isoformat(),
    )


def link_memory_to_run(session, *, memory_id: str, run_id: str) -> None:
    session.run(
        """
        MATCH (r:Run {id: $run_id})
        MATCH (m:Memory {id: $memory_id})
        MERGE (r)-[:PRODUCED]->(m)
        MERGE (m)-[:DERIVED_FROM]->(r)
        """,
        run_id=run_id,
        memory_id=memory_id,
    )


def increment_memory_use_count(session, memory_id: str) -> None:
    session.run(
        "MATCH (m:Memory {id: $id}) SET m.use_count = coalesce(m.use_count, 0) + 1, m.updated_at = $now",
        id=memory_id,
        now=datetime.now(timezone.utc).isoformat(),
    )


def search_similar_memories(session, *, embedding: list[float], user_id: str, agent_id: str, top_k: int = 10) -> list[dict[str, Any]]:
    """Vector search over Memory nodes, filtered by user+agent."""
    try:
        result = session.run(
            """
            CALL db.index.vector.queryNodes('memory_embedding', $top_k, $embedding)
            YIELD node AS m, score
            WHERE m.user_id = $user_id AND m.agent_id = $agent_id
            RETURN m.id AS id, m.content AS content, m.type AS type,
                   m.confidence AS confidence, m.use_count AS use_count,
                   m.created_at AS created_at, score
            ORDER BY score DESC
            """,
            embedding=embedding,
            top_k=top_k * 3,  # Fetch more to compensate for user/agent filtering
            user_id=user_id,
            agent_id=agent_id,
        )
        return [dict(r) for r in result]
    except Exception:
        # Fallback: in-memory cosine similarity if vector index not available
        return _fallback_memory_search(session, embedding=embedding, user_id=user_id, agent_id=agent_id, top_k=top_k)


def _fallback_memory_search(session, *, embedding: list[float], user_id: str, agent_id: str, top_k: int) -> list[dict[str, Any]]:
    import numpy as np

    result = session.run(
        """
        MATCH (m:Memory {user_id: $user_id, agent_id: $agent_id})
        WHERE m.embedding IS NOT NULL
        RETURN m.id AS id, m.content AS content, m.type AS type,
               m.confidence AS confidence, m.use_count AS use_count,
               m.created_at AS created_at, m.embedding AS embedding
        """,
        user_id=user_id,
        agent_id=agent_id,
    )
    q = np.array(embedding)
    scored = []
    for r in result:
        emb = r["embedding"]
        if len(emb) != len(embedding):
            continue
        v = np.array(emb)
        score = float(np.dot(q, v) / (np.linalg.norm(q) * np.linalg.norm(v) + 1e-9))
        scored.append({**dict(r), "score": score})
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


def get_recent_runs(session, *, user_id: str, agent_id: str, limit: int = 5) -> list[dict[str, Any]]:
    result = session.run(
        """
        MATCH (u:User {user_id: $user_id})-[:HAS_AGENT]->(a:Agent {agent_id: $agent_id})-[:EXECUTED]->(r:Run)
        RETURN r.id AS run_id, r.task AS task, r.outcome AS outcome, r.summary AS summary,
               r.created_at AS created_at
        ORDER BY r.created_at DESC
        LIMIT $limit
        """,
        user_id=user_id,
        agent_id=agent_id,
        limit=limit,
    )
    return [dict(r) for r in result]


def get_all_memories_for_update(session, *, embedding: list[float], user_id: str, agent_id: str) -> list[dict[str, Any]]:
    """Used by updater to find existing memories similar to a new candidate."""
    return search_similar_memories(session, embedding=embedding, user_id=user_id, agent_id=agent_id, top_k=5)
