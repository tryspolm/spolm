<div align="center">

<img src="assets/image.png" alt="Spolm" width="80" />

# Spolm

**Self-learning intelligence layer for AI agents.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![PyPI](https://img.shields.io/pypi/v/spolm.svg)](https://pypi.org/project/spolm/)

[Website](https://tryspolm.com) · [Docs](https://tanrocode.github.io/spolm-docs/)

</div>

---

Spolm sits alongside any AI agent system. After each run, it extracts reusable memories — lessons, patterns, warnings, facts — and surfaces the most relevant ones as context before the next run. Your agent gets smarter over time without any changes to your architecture.

```
run 1 → record() → memories extracted + stored
run 2 → get_context() → relevant memories injected → better output
run N → compounding improvement
```

---

## Packages

| Package | Install | Description |
|---|---|---|
| [`packages/python`](packages/python/) | `pip install spolm` | Learning SDK — `get_context()` + `record()` |
| [`packages/python-trace`](packages/python-trace/) | `pip install spolm-trace` | Python tracing — structured run + step logging |
| [`packages/js-trace`](packages/js-trace/) | `npm install @spolm/tracer` | JS tracing — structured run + step logging |

---

## Quick Start

### Learning SDK

```python
from spolm import Spolm

# Hosted — managed Neo4j + dashboard at tryspolm.com
spolm = Spolm(api_key="spk_...")

# Before your agent runs: retrieve relevant memories as prompt context
context = spolm.get_context("summarize the user's inbox")
# Returns a <spolm_context>...</spolm_context> XML block — inject directly into your prompt

# After your agent runs: record the outcome so Spolm can learn
spolm.record(
    task="summarize the user's inbox",
    result="Sent digest with 3 action items",
    trajectory=[...],  # optional — any list of steps/tool calls
)
```

**Self-hosted** (bring your own Neo4j):

```python
spolm = Spolm(
    neo4j_uri="bolt://localhost:7687",
    neo4j_password="your-password",
    llm_api_key="sk-...",  # any LiteLLM-compatible provider
)
```

Both modes share the same API. `get_context()` always returns a string and never raises — safe on cold start. `record()` runs in a background thread and never blocks your agent.

---

### Tracing SDK

Use the Tracer alongside the learning SDK to log every step automatically and trigger learning at the end of each run.

```python
from trace import Tracer

tracer = Tracer(api_key="spk_...", agent_id="my-agent", spolm=spolm)
tracer.start_run("summarize inbox")

@tracer.log_step(step_name="fetch_emails", step_type="tool_call")
async def fetch_emails(query): ...

await fetch_emails("inbox")
tracer.end_run(result)  # logs the run + fires spolm.record() automatically
```

**JavaScript:**

```javascript
const Tracer = require("@spolm/tracer");

const tracer = new Tracer("spk_...", "my-agent", { userId: "user-123" });
tracer.startRun("summarize inbox");
// ... log steps ...
tracer.endRun(result);
```

---

## How it works

### Memory extraction

After `record()` is called, an LLM processes the task, result, and trajectory to extract structured **Memory nodes** — typed as `lesson`, `pattern`, `warning`, or `fact`. Each memory gets a confidence score that updates over time.

### Deduplication

Before writing a new memory, Spolm computes embedding similarity against existing nodes:
- **> 0.92 similarity** — skip, already known
- **0.75 – 0.92** — ask the LLM to merge or update
- **< 0.75** — write as a new memory

This keeps the memory graph clean and non-redundant as your agent accumulates more runs.

### Context retrieval

`get_context()` runs a vector similarity search and re-ranks results by a combined score of **similarity × confidence × recency**. The top memories are formatted into a `<spolm_context>` XML block ready to inject into any prompt.

---

## Environment variables

| Variable | Description |
|---|---|
| `SPOLM_API_KEY` | Hosted API key (`spk_...`) |
| `SPOLM_NEO4J_URI` | Self-hosted Neo4j URI |
| `SPOLM_NEO4J_PASSWORD` | Self-hosted Neo4j password |
| `SPOLM_LLM_API_KEY` | LLM provider API key (self-hosted only) |
| `SPOLM_BASE_URL` | Override the tracing API base URL (self-hosted only) |

---

## Hosted platform

[tryspolm.com](https://tryspolm.com) provides:

- **Managed Neo4j** — no infrastructure to set up or maintain
- **Dashboard** — visualize memories, run history, and confidence scores over time
- **API key management** — per-agent isolation, multi-tenant by design
- **`agent_id` scoping** — memories are separated per agent, so different agents don't bleed context into each other

---

## Self-hosting

Run Spolm entirely on your own infrastructure:

1. Spin up Neo4j (local or cloud)
2. `pip install spolm`
3. Initialize with your Neo4j URI, password, and LLM API key

No account or internet connection required. Self-hosting is intentionally frictionless — the dashboard is the paid layer, not the SDK.

---

## Contributing

PRs welcome. Please open an issue first for anything beyond small fixes.

## License

MIT — see [LICENSE](LICENSE)
