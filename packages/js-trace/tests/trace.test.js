jest.mock("../apikeys-management/index.js", () => ({
  checkAPIKey: jest.fn().mockResolvedValue({ valid: true }),
}));

jest.mock("../logs-analysis/post.js", () => ({
  postLog: jest.fn().mockResolvedValue({ valid: true }),
}));

const Tracer = require("../trace.js");
const { postLog } = require("../logs-analysis/post.js");

function makeTracer(opts = {}) {
  return new Tracer("spk_test", "agent-1", { userId: "default", ...opts });
}

// ── Init ─────────────────────────────────────────────────────────────────────

test("throws without apiKey", () => {
  expect(() => new Tracer(null, "agent-1")).toThrow("apiKey is required");
});

test("throws without agentId", () => {
  expect(() => new Tracer("spk_test", null)).toThrow("agentId is required");
});

test("initializes with default userId", () => {
  const tracer = makeTracer();
  expect(tracer.userId).toBe("default");
});

test("initializes with custom userId", () => {
  const tracer = makeTracer({ userId: "user-123" });
  expect(tracer.userId).toBe("user-123");
});

test("debug defaults to false", () => {
  const tracer = makeTracer();
  expect(tracer.debug).toBe(false);
});

// ── startRun ─────────────────────────────────────────────────────────────────

test("startRun returns a run id", () => {
  const tracer = makeTracer();
  const runId = tracer.startRun("send weekly digest");
  expect(typeof runId).toBe("string");
  expect(runId).toHaveLength(36);
});

test("startRun stores correct fields", () => {
  const tracer = makeTracer({ userId: "user-abc" });
  tracer.startRun("send weekly digest", { env: "prod" });

  expect(tracer.currentRun.user_task).toBe("send weekly digest");
  expect(tracer.currentRun.user_id).toBe("user-abc");
  expect(tracer.currentRun.agent_id).toBe("agent-1");
  expect(tracer.currentRun.metadata).toEqual({ env: "prod" });
  expect(tracer.currentRun.steps).toEqual([]);
});

test("startRun throws without userTask", () => {
  const tracer = makeTracer();
  expect(() => tracer.startRun("")).toThrow("userTask is required");
});

// ── logStep ───────────────────────────────────────────────────────────────────

test("logStep records a successful step", async () => {
  const tracer = makeTracer();
  tracer.startRun("fetch emails");

  const fetch = tracer.logStep({ stepName: "fetch", stepType: "tool_call" })(
    async (data) => ({ emails: 5 })
  );

  await fetch({ query: "inbox" });

  expect(tracer.currentRun.steps).toHaveLength(1);
  const step = tracer.currentRun.steps[0];
  expect(step.step_name).toBe("fetch");
  expect(step.step_type).toBe("tool_call");
  expect(step.step_status).toBe("success");
  expect(step.step_output).toEqual({ emails: 5 });
  expect(step.step_error).toBeNull();
});

test("logStep records a failed step and re-throws", async () => {
  const tracer = makeTracer();
  tracer.startRun("fetch emails");

  const fetch = tracer.logStep({ stepName: "fetch", stepType: "tool_call" })(
    async () => { throw new Error("rate limited"); }
  );

  await expect(fetch({})).rejects.toThrow("rate limited");

  const step = tracer.currentRun.steps[0];
  expect(step.step_status).toBe("failed");
  expect(step.step_error).toBe("rate limited");
  expect(step.step_output).toBeNull();
});

test("logStep records latency", async () => {
  const tracer = makeTracer();
  tracer.startRun("task");

  const fn = tracer.logStep({ stepName: "step", stepType: "llm_call" })(
    async () => "done"
  );
  await fn({});

  expect(tracer.currentRun.steps[0].step_latency).toBeGreaterThanOrEqual(0);
});

// ── endRun ───────────────────────────────────────────────────────────────────

test("endRun posts log", () => {
  const tracer = makeTracer();
  tracer.startRun("task");
  tracer.endRun({ result: "ok" });
  expect(postLog).toHaveBeenCalledTimes(1);
});

test("endRun sets duration", () => {
  const tracer = makeTracer();
  tracer.startRun("task");
  tracer.endRun("done");
  expect(tracer.currentRun.duration).toBeGreaterThanOrEqual(0);
});

test("endRun throws without active run", () => {
  const tracer = makeTracer();
  expect(() => tracer.endRun("done")).toThrow("No active run");
});

test("endRun does not write debug file when debug is false", () => {
  const fs = require("fs");
  const spy = jest.spyOn(fs, "writeFileSync");
  const tracer = makeTracer({ debug: false });
  tracer.startRun("task");
  tracer.endRun("done");
  expect(spy).not.toHaveBeenCalled();
  spy.mockRestore();
});

// ── Learning integration ──────────────────────────────────────────────────────

test("endRun triggers spolm.record when spolm is set", async () => {
  const mockSpolm = { record: jest.fn().mockResolvedValue(undefined) };
  const tracer = makeTracer({ spolm: mockSpolm });
  tracer.startRun("send digest");
  tracer.endRun({ sent: true }, "complete");

  await Promise.resolve(); // flush microtask queue

  expect(mockSpolm.record).toHaveBeenCalledTimes(1);
  const args = mockSpolm.record.mock.calls[0][0];
  expect(args.task).toBe("send digest");
  expect(args.outcome).toBe("success");
});

test("endRun sets outcome to failure on non-complete status", async () => {
  const mockSpolm = { record: jest.fn().mockResolvedValue(undefined) };
  const tracer = makeTracer({ spolm: mockSpolm });
  tracer.startRun("task");
  tracer.endRun("done", "error");

  await Promise.resolve();

  const args = mockSpolm.record.mock.calls[0][0];
  expect(args.outcome).toBe("failure");
});

test("endRun does not call record when spolm is not set", () => {
  const tracer = makeTracer();
  tracer.startRun("task");
  tracer.endRun("done");
  expect(tracer._spolm).toBeNull();
});
