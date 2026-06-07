import json
import re
from typing import Any


EXTRACTION_PROMPT = """Extract reusable lessons from this agent run. These will be stored in a knowledge graph and retrieved to help future agents doing similar tasks.

Rules:
- Generalize. Never mention specific dates, run IDs, or one-off values.
- BAD: "On May 3rd the API returned a 429"
- GOOD: "This API rate limits aggressively under load — use exponential backoff"
- Each memory must be a single, standalone insight that makes sense out of context.
- Only extract insights worth remembering. Skip trivial or obvious observations.
- Choose the right type:
  - lesson: procedural knowledge (how to do something)
  - fact: static truth about a tool, API, or system
  - pattern: recurring behavior or sequence that works well
  - warning: a risk, failure mode, or gotcha to avoid

Task: {task}
Outcome: {outcome}
Result: {result}
Trajectory: {trajectory}

Return JSON only:
{{
  "memories": [
    {{"content": "...", "type": "lesson|fact|pattern|warning"}},
    ...
  ]
}}

If nothing is worth extracting, return: {{"memories": []}}"""


def extract(*, task: str, result: Any, trajectory: list, outcome: str, llm_model: str, llm_api_key: str) -> list[dict]:
    from spolm.llm import provider

    trajectory_str = _format_trajectory(trajectory)
    result_str = str(result)[:500] if result else "none"

    prompt = EXTRACTION_PROMPT.format(
        task=task,
        outcome=outcome,
        result=result_str,
        trajectory=trajectory_str,
    )

    raw = provider.complete(
        model=llm_model,
        messages=[
            {"role": "system", "content": "You are a memory curator for AI agents. Respond with valid JSON only."},
            {"role": "user", "content": prompt},
        ],
        api_key=llm_api_key,
        temperature=0.3,
        max_tokens=1024,
    )

    return _parse(raw)


def _parse(raw: str) -> list[dict]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```\w*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text).strip()

    start = text.find("{")
    if start >= 0:
        end = text.rfind("}") + 1
        text = text[start:end]

    try:
        data = json.loads(text)
        memories = data.get("memories", [])
        return [
            m for m in memories
            if isinstance(m, dict) and m.get("content") and m.get("type") in ("lesson", "fact", "pattern", "warning")
        ]
    except (json.JSONDecodeError, TypeError):
        return []


def _format_trajectory(trajectory: list) -> str:
    if not trajectory:
        return "none"
    lines = []
    for i, step in enumerate(trajectory[:10], 1):  # Cap at 10 steps
        if isinstance(step, dict):
            name = step.get("name") or step.get("step_name") or f"step_{i}"
            status = step.get("status") or step.get("step_status") or ""
            lines.append(f"{i}. {name} [{status}]")
        else:
            lines.append(f"{i}. {str(step)[:100]}")
    return "\n".join(lines)
