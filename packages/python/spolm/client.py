"""
Spolm — self-learning intelligence layer for AI agents.

Two modes:
  Hosted:      Spolm(api_key="spk_...")
  Self-hosted: Spolm(neo4j_uri=..., neo4j_password=..., llm_api_key=...)
"""
import logging
import os
import threading
import uuid
from typing import Any

logger = logging.getLogger("spolm")


class Spolm:
    def __init__(
        self,
        *,
        # Hosted mode
        api_key: str = None,
        hosted_url: str = "https://api.spolm.ai",
        # Self-hosted mode
        neo4j_uri: str = None,
        neo4j_user: str = "neo4j",
        neo4j_password: str = None,
        # LLM config (self-hosted)
        llm_provider: str = None,
        llm_model: str = "gpt-4o-mini",
        llm_api_key: str = None,
        embedding_model: str = "text-embedding-3-small",
        # Identity
        user_id: str = "default",
        agent_id: str = "default",
    ):
        # Resolve from env vars as fallback
        api_key = api_key or os.getenv("SPOLM_API_KEY")
        neo4j_uri = neo4j_uri or os.getenv("SPOLM_NEO4J_URI")
        neo4j_password = neo4j_password or os.getenv("SPOLM_NEO4J_PASSWORD")
        llm_api_key = llm_api_key or os.getenv("SPOLM_LLM_API_KEY")
        llm_model = llm_model or os.getenv("SPOLM_LLM_MODEL", "gpt-4o-mini")

        self.user_id = user_id
        self.agent_id = agent_id

        if api_key:
            self._mode = "hosted"
            self._api_key = api_key
            self._hosted_url = hosted_url.rstrip("/")
        elif neo4j_uri and neo4j_password:
            self._mode = "self_hosted"
            self._driver = self._connect_neo4j(neo4j_uri, neo4j_user, neo4j_password)
            self._llm_model = llm_model
            self._llm_api_key = llm_api_key
            self._embedding_model = embedding_model
            self._embedding_api_key = llm_api_key  # Same key used for both by default
            self._apply_schema()
        else:
            raise ValueError(
                "Provide either api_key (hosted mode) or neo4j_uri + neo4j_password (self-hosted mode). "
                "See: https://docs.spolm.ai/quickstart"
            )

    def get_context(self, task: str) -> str:
        """
        Retrieve relevant memory for a task and return a prompt-ready context block.

        Returns an empty string on cold start (no memories yet) — never raises.
        """
        if self._mode == "hosted":
            return self._hosted_get_context(task)

        try:
            from spolm.memory import retriever
            from spolm.context import formatter

            result = retriever.retrieve(
                driver=self._driver,
                task=task,
                user_id=self.user_id,
                agent_id=self.agent_id,
                embedding_model=self._embedding_model,
                embedding_api_key=self._embedding_api_key,
            )
            return formatter.format_context(result["memories"], result["recent_runs"])
        except Exception as e:
            logger.warning("spolm.get_context failed silently: %s", e)
            return ""

    def record(self, task: str, result: Any = None, trajectory: list = None, outcome: str = None) -> None:
        """
        Record a completed agent run. Triggers the memory pipeline asynchronously.

        Never blocks. Never raises.
        """
        run_id = str(uuid.uuid4())
        thread = threading.Thread(
            target=self._run_pipeline,
            args=(run_id, task, result, trajectory or [], outcome),
            daemon=True,
        )
        thread.start()

    # ── Internal pipeline ──────────────────────────────────────────────────────

    def _run_pipeline(self, run_id: str, task: str, result: Any, trajectory: list, outcome: str) -> None:
        try:
            from spolm.graph import queries, schema
            from spolm.memory import extractor, updater
            from spolm.llm import provider

            outcome = outcome or _infer_outcome(result)
            summary = f"{task} — {outcome}"

            run_embedding = provider.embed(task, model=self._embedding_model, api_key=self._embedding_api_key)

            with self._driver.session() as session:
                queries.upsert_user(session, self.user_id)
                queries.upsert_agent(session, self.agent_id, self.user_id)
                queries.create_run(
                    session,
                    run_id=run_id,
                    agent_id=self.agent_id,
                    task=task,
                    outcome=outcome,
                    summary=summary,
                    embedding=run_embedding,
                    trajectory=trajectory,
                    result=result,
                )

            candidates = extractor.extract(
                task=task,
                result=result,
                trajectory=trajectory,
                outcome=outcome,
                llm_model=self._llm_model,
                llm_api_key=self._llm_api_key,
            )

            if candidates:
                updater.process(
                    driver=self._driver,
                    candidates=candidates,
                    run_id=run_id,
                    user_id=self.user_id,
                    agent_id=self.agent_id,
                    llm_model=self._llm_model,
                    llm_api_key=self._llm_api_key,
                    embedding_model=self._embedding_model,
                    embedding_api_key=self._embedding_api_key,
                )
        except Exception as e:
            logger.warning("spolm memory pipeline failed silently: %s", e)

    # ── Hosted mode HTTP calls ─────────────────────────────────────────────────

    def _hosted_get_context(self, task: str) -> str:
        try:
            import httpx
            resp = httpx.post(
                f"{self._hosted_url}/retrieve",
                json={"task_text": task, "user_id": self.user_id, "agent_id": self.agent_id, "top_k": 8},
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json().get("context", "")
        except Exception as e:
            logger.warning("spolm hosted get_context failed: %s", e)
            return ""

    def _hosted_record(self, run_id: str, task: str, result: Any, trajectory: list, outcome: str) -> None:
        try:
            import httpx
            httpx.post(
                f"{self._hosted_url}/runs",
                json={
                    "run_id": run_id,
                    "user_id": self.user_id,
                    "agent_id": self.agent_id,
                    "user_task": task,
                    "outcome": outcome or _infer_outcome(result),
                    "run_tree": {"steps": trajectory},
                },
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=30,
            )
        except Exception as e:
            logger.warning("spolm hosted record failed: %s", e)

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _connect_neo4j(self, uri: str, user: str, password: str):
        from neo4j import GraphDatabase
        return GraphDatabase.driver(uri, auth=(user, password))

    def _apply_schema(self) -> None:
        from spolm.graph import schema
        try:
            schema.apply(self._driver)
        except Exception as e:
            logger.warning("spolm schema apply failed: %s", e)

    def close(self) -> None:
        if self._mode == "self_hosted":
            self._driver.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def _infer_outcome(result: Any) -> str:
    if result is None:
        return "unknown"
    if isinstance(result, dict):
        status = result.get("status") or result.get("outcome") or result.get("success")
        if status in (True, "success", "ok", "done"):
            return "success"
        if status in (False, "failure", "error", "failed"):
            return "failure"
    return "success"
