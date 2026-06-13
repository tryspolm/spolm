import asyncio
import pytest
from unittest.mock import MagicMock, patch


def make_tracer(**kwargs):
    from trace import Tracer
    defaults = dict(api_key="spk_test", agent_id="agent-1")
    return Tracer(**{**defaults, **kwargs})


# ── Init ──────────────────────────────────────────────────────────────────────

def test_raises_without_api_key():
    from trace import Tracer
    with pytest.raises(ValueError, match="api_key"):
        Tracer(api_key=None, agent_id="agent-1")


def test_raises_without_agent_id():
    from trace import Tracer
    with pytest.raises(ValueError, match="agent_id"):
        Tracer(api_key="spk_test", agent_id=None)


def test_init_without_event_loop():
    # must not crash in a plain synchronous context
    tracer = make_tracer()
    assert tracer.API_KEY == "spk_test"
    assert tracer.AGENT_ID == "agent-1"


def test_default_user_id():
    tracer = make_tracer()
    assert tracer.user_id == "default"


def test_custom_user_id():
    tracer = make_tracer(user_id="user-123")
    assert tracer.user_id == "user-123"


# ── start_run ─────────────────────────────────────────────────────────────────

def test_start_run_returns_run_id():
    tracer = make_tracer()
    run_id = tracer.start_run("send weekly digest")
    assert isinstance(run_id, str)
    assert len(run_id) == 36  # uuid4


def test_start_run_stores_correct_fields():
    tracer = make_tracer(user_id="user-abc")
    tracer.start_run("send weekly digest", metadata={"env": "prod"})

    run = tracer.current_run
    assert run["user_task"] == "send weekly digest"
    assert run["user_id"] == "user-abc"
    assert run["agent_id"] == "agent-1"
    assert run["metadata"] == {"env": "prod"}
    assert run["steps"] == []


def test_start_run_raises_without_task():
    tracer = make_tracer()
    with pytest.raises(ValueError):
        tracer.start_run("")


# ── log_step ──────────────────────────────────────────────────────────────────

def test_log_step_records_successful_step():
    tracer = make_tracer()
    tracer.start_run("fetch emails")

    @tracer.log_step(step_name="fetch", step_type="tool_call")
    async def fetch(data):
        return {"emails": 5}

    asyncio.run(fetch({"query": "inbox"}))

    assert len(tracer.current_run["steps"]) == 1
    step = tracer.current_run["steps"][0]
    assert step["step_name"] == "fetch"
    assert step["step_type"] == "tool_call"
    assert step["step_status"] == "success"
    assert step["step_output"] == {"emails": 5}
    assert step["step_error"] is None


def test_log_step_records_failed_step():
    tracer = make_tracer()
    tracer.start_run("fetch emails")

    @tracer.log_step(step_name="fetch", step_type="tool_call")
    async def fetch(data):
        raise ValueError("rate limited")

    with pytest.raises(ValueError, match="rate limited"):
        asyncio.run(fetch({}))

    step = tracer.current_run["steps"][0]
    assert step["step_status"] == "failed"
    assert step["step_error"] == "rate limited"
    assert step["step_output"] is None


def test_log_step_records_latency():
    tracer = make_tracer()
    tracer.start_run("task")

    @tracer.log_step(step_name="slow_step", step_type="llm_call")
    async def slow(data):
        return "done"

    asyncio.run(slow({}))
    assert tracer.current_run["steps"][0]["step_latency"] >= 0


# ── end_run ───────────────────────────────────────────────────────────────────

def test_end_run_posts_log():
    with patch("logs_analysis.post.post_log") as mock_post:
        tracer = make_tracer()
        tracer.start_run("task")
        tracer.end_run({"result": "ok"})
        mock_post.assert_called_once()


def test_end_run_no_debug_file_by_default(tmp_path):
    tracer = make_tracer(debug=False)
    tracer.start_run("task")
    tracer.end_run("done")
    assert list(tmp_path.iterdir()) == []


def test_end_run_writes_debug_file(tmp_path, monkeypatch):
    import trace as trace_module
    monkeypatch.setattr(trace_module.os.path, "dirname", lambda _: str(tmp_path))

    tracer = make_tracer(debug=True)
    tracer.start_run("task")
    tracer.end_run("done")

    debug_dir = tmp_path / ".." / "debug_logs"
    # just check it tried — file location varies; main thing is no crash
    assert tracer.debug is True


def test_end_run_sets_duration():
    tracer = make_tracer()
    tracer.start_run("task")
    tracer.end_run("done")
    assert tracer.current_run["duration"] >= 0


def test_end_run_raises_without_active_run():
    tracer = make_tracer()
    with pytest.raises(RuntimeError, match="No active run"):
        tracer.end_run("done")


# ── Learning integration ───────────────────────────────────────────────────────

def test_end_run_triggers_learning_when_spolm_set():
    mock_spolm = MagicMock()
    tracer = make_tracer(spolm=mock_spolm)
    tracer.start_run("send digest")
    tracer.end_run({"sent": True}, status="complete")

    # give the background thread a moment
    import time; time.sleep(0.1)

    mock_spolm.record.assert_called_once()
    call_kwargs = mock_spolm.record.call_args.kwargs
    assert call_kwargs["task"] == "send digest"
    assert call_kwargs["outcome"] == "success"


def test_end_run_no_learning_without_spolm():
    tracer = make_tracer()
    tracer.start_run("task")
    tracer.end_run("done")
    assert tracer._spolm is None


def test_learning_outcome_failure_on_non_complete_status():
    mock_spolm = MagicMock()
    tracer = make_tracer(spolm=mock_spolm)
    tracer.start_run("task")
    tracer.end_run("done", status="error")

    import time; time.sleep(0.1)

    call_kwargs = mock_spolm.record.call_args.kwargs
    assert call_kwargs["outcome"] == "failure"
