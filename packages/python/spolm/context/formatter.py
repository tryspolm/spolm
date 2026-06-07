from typing import Any


def format_context(memories: list[dict], recent_runs: list[dict]) -> str:
    """Format retrieved memories and runs into a prompt-ready <spolm_context> block."""
    if not memories and not recent_runs:
        return ""

    parts = ["<spolm_context>"]

    lessons = [m for m in memories if m["type"] == "lesson"]
    facts = [m for m in memories if m["type"] == "fact"]
    patterns = [m for m in memories if m["type"] == "pattern"]
    warnings = [m for m in memories if m["type"] == "warning"]

    if lessons:
        parts.append("  <lessons>")
        for m in lessons:
            parts.append(f"    - [confidence: {m['confidence']:.2f}] {m['content']}")
        parts.append("  </lessons>")

    if facts:
        parts.append("  <facts>")
        for m in facts:
            parts.append(f"    - [confidence: {m['confidence']:.2f}] {m['content']}")
        parts.append("  </facts>")

    if patterns:
        parts.append("  <patterns>")
        for m in patterns:
            parts.append(f"    - [confidence: {m['confidence']:.2f}] {m['content']}")
        parts.append("  </patterns>")

    if warnings:
        parts.append("  <warnings>")
        for m in warnings:
            parts.append(f"    - [confidence: {m['confidence']:.2f}] {m['content']}")
        parts.append("  </warnings>")

    if recent_runs:
        parts.append("  <similar_runs>")
        for run in recent_runs:
            outcome = run.get("outcome") or "unknown"
            summary = (run.get("summary") or run.get("task") or "")[:120]
            run_id = (run.get("run_id") or "")[:8]
            parts.append(f"    - Run #{run_id} ({outcome}): {summary}")
        parts.append("  </similar_runs>")

    parts.append("</spolm_context>")
    return "\n".join(parts)
