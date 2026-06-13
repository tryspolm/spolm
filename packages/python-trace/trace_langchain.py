from langchain.callbacks.base import BaseCallbackHandler
import time
import uuid

class SpolmTracerCallbackHandler(BaseCallbackHandler):
    def __init__(self, tracer):
        self.tracer = tracer
        self.step_id = None
        self.step_start_time = None
        self.step_name = None
        self.step_type = None
        self.inputs = None

    def on_chain_start(self, serialized, inputs, **kwargs):
        self.step_id = str(uuid.uuid4())
        self.step_start_time = time.time()
        self.step_name = serialized.get("name", "chain")
        self.step_type = "chain"
        self.inputs = inputs

    def on_chain_end(self, outputs, **kwargs):
        step_end_time = time.time()
        step = {
            "step_id": self.step_id,
            "step_name": self.step_name,
            "step_type": self.step_type,
            "step_input": self.inputs,
            "step_output": outputs,
            "step_end_time": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "step_latency": int((step_end_time - self.step_start_time) * 1000),
            "step_status": "success",
        }
        if hasattr(self.tracer, "current_run") and self.tracer.current_run:
            self.tracer.current_run["steps"].append(step)

    def on_chain_error(self, error, **kwargs):
        step_end_time = time.time()
        step = {
            "step_id": self.step_id,
            "step_name": self.step_name,
            "step_type": self.step_type,
            "step_input": self.inputs,
            "step_output": None,
            "step_error": str(error),
            "step_end_time": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "step_latency": int((step_end_time - self.step_start_time) * 1000),
            "step_status": "failed",
        }
        if hasattr(self.tracer, "current_run") and self.tracer.current_run:
            self.tracer.current_run["steps"].append(step)

    # Optionally, implement other callback methods for more granular tracing
    # def on_tool_start(self, ...):
    # def on_tool_end(self, ...):
    # def on_agent_action(self, ...):
    # etc.
