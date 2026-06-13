import logging
import os
import threading
import time
import uuid
import json
from datetime import datetime, timezone

logger = logging.getLogger("spolm.trace")


class Tracer:

    def __init__(self, api_key, agent_id, user_id="default", options=None, debug=False, spolm=None):
        if not api_key:
            raise ValueError("api_key is required")
        if not agent_id:
            raise ValueError("agent_id is required")

        self.API_KEY = api_key
        self.AGENT_ID = agent_id
        self.user_id = user_id
        self.options = options or {}
        self.debug = debug
        self.current_run = None
        self._spolm = spolm

        threading.Thread(target=self._validate_api_key, daemon=True).start()

    def _validate_api_key(self):
        try:
            from api.keys import check_api_key
            result = check_api_key(self.API_KEY)
            if not result.get("valid", False):
                logger.warning("Invalid Spolm API key — calls will fail")
        except Exception as e:
            logger.warning("Could not validate API key: %s", e)

    def start_run(self, user_task, metadata=None):
        if not user_task:
            raise ValueError("user_task is required to start a run")

        self.current_run = {
            "run_id": str(uuid.uuid4()),
            "user_id": self.user_id,
            "agent_id": self.AGENT_ID,
            "start_timestamp": datetime.now(timezone.utc).isoformat(),
            "user_task": user_task,
            "metadata": metadata or {},
            "steps": [],
            "final_output": None,
            "duration": 0,
        }

        return self.current_run["run_id"]

    def log_step(self, *, step_name, step_type, provider=None, options=None):
        if not step_name or not step_type:
            raise ValueError("step_name and step_type are required")

        def decorator(fn):
            tracer = self

            async def wrapper(*args, **kwargs):
                if not tracer.current_run:
                    raise RuntimeError("No active run. Call start_run first.")

                step_start = time.time()
                step_id = str(uuid.uuid4())
                input_data = args[0] if len(args) == 1 else list(args)

                tracer._step_meta = {}

                def record_tokens(usage):
                    tracer._step_meta["tokenUsage"] = usage

                tracer.record_tokens = record_tokens

                result = None
                error = None

                try:
                    result = await fn(*args, **kwargs)
                except Exception as err:
                    error = err

                step = {
                    "step_id": step_id,
                    "step_name": step_name,
                    "step_type": step_type,
                    "step_input": input_data,
                    "step_output": None if error else result,
                    "step_error": str(error) if error else None,
                    "step_end_time": datetime.now(timezone.utc).isoformat(),
                    "step_latency": int((time.time() - step_start) * 1000),
                    "tool_provider": provider,
                    "options": options or {},
                    "step_status": "failed" if error else "success",
                }

                if "tokenUsage" in tracer._step_meta:
                    step["tokens"] = tracer._step_meta["tokenUsage"]

                tracer.current_run["steps"].append(step)

                del tracer._step_meta
                del tracer.record_tokens

                if error:
                    raise error

                return result

            return wrapper

        return decorator

    def end_run(self, final_result, status="complete"):
        if not self.current_run:
            raise RuntimeError("No active run. Call start_run first.")

        end_timestamp = datetime.now(timezone.utc).isoformat()
        self.current_run["final_output"] = final_result
        self.current_run["status"] = status
        self.current_run["end_timestamp"] = end_timestamp

        start = datetime.fromisoformat(self.current_run["start_timestamp"])
        end = datetime.fromisoformat(end_timestamp)
        self.current_run["duration"] = int((end - start).total_seconds() * 1000)

        if self.debug:
            self._write_debug_file()

        self._post_log()

        if self._spolm:
            self._trigger_learning(final_result, status)

    def _trigger_learning(self, final_result, status):
        outcome = "success" if status == "complete" else "failure"
        run = self.current_run
        threading.Thread(
            target=self._spolm.record,
            kwargs={
                "task": run["user_task"],
                "outcome": outcome,
                "trajectory": run["steps"],
                "result": final_result,
            },
            daemon=True,
        ).start()

    def _post_log(self):
        try:
            from api.logs import post_log
            post_log(self.API_KEY, self.AGENT_ID, self.current_run)
        except Exception as e:
            logger.warning("Failed to post log: %s", e)

    def _write_debug_file(self):
        try:
            debug_dir = os.path.join(os.path.dirname(__file__), "..", "debug_logs")
            os.makedirs(debug_dir, exist_ok=True)
            ts = datetime.now(timezone.utc).isoformat().replace(":", "-").replace(".", "-")
            path = os.path.join(debug_dir, f"log_{ts}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.current_run, f, indent=2)
            logger.debug("Debug log written to %s", path)
        except Exception as e:
            logger.warning("Failed to write debug log: %s", e)
