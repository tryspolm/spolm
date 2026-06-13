const { v4: uuidv4 } = require("uuid");
const { checkAPIKey } = require("./api/keys.js");
const { postLog } = require("./api/logs.js");
const fs = require("fs");
const path = require("path");

class Tracer {
  /**
   * @param {string} apiKey - Spolm API key
   * @param {string} agentId - Agent identifier
   * @param {Object} options
   * @param {string} options.userId - User identifier for multi-tenancy (default: "default")
   * @param {boolean} options.debug - Write debug files to disk (default: false)
   * @param {Object} options.spolm - Spolm learning SDK instance for auto-learning on endRun()
   * @param {string} options.baseUrl - Override the API base URL (self-hosted only, default: "https://api.tryspolm.com")
   */
  constructor(apiKey, agentId, { userId = "default", debug = false, spolm = null, baseUrl = null } = {}) {
    if (!apiKey) throw new Error("apiKey is required");
    if (!agentId) throw new Error("agentId is required");

    this.apiKey = apiKey;
    this.agentId = agentId;
    this.userId = userId;
    this.debug = debug;
    this._spolm = spolm;
    this.currentRun = null;
    this.baseUrl = baseUrl || process.env.SPOLM_BASE_URL || "https://api.tryspolm.com";

    // fire-and-forget validation — never blocks constructor
    checkAPIKey(apiKey, this.baseUrl).then((result) => {
      if (!result.valid) {
        console.warn("[spolm] Invalid API key — calls will fail");
      }
    }).catch(() => {});
  }

  startRun(userTask, metadata = {}) {
    if (!userTask) throw new Error("userTask is required to start a run");

    this.currentRun = {
      run_id: uuidv4(),
      user_id: this.userId,
      agent_id: this.agentId,
      start_timestamp: new Date().toISOString(),
      user_task: userTask,
      metadata,
      steps: [],
      final_output: null,
      duration: 0,
    };

    return this.currentRun.run_id;
  }

  logStep({ stepName, stepType, provider = null, options = {} } = {}) {
    if (!stepName || !stepType) {
      throw new Error("stepName and stepType are required");
    }

    return (fn) => {
      const tracer = this;

      return async function (...args) {
        if (!tracer.currentRun) throw new Error("No active run. Call startRun first.");

        const stepStart = Date.now();
        const stepId = uuidv4();
        const input = args.length === 1 ? args[0] : args;

        tracer._stepMeta = {};
        tracer.recordTokens = (usage) => {
          tracer._stepMeta.tokenUsage = usage;
        };

        let result, error;
        try {
          result = await fn.apply(tracer, args);
        } catch (err) {
          error = err;
        }

        const step = {
          step_id: stepId,
          step_name: stepName,
          step_type: stepType,
          step_input: input,
          step_output: error ? null : result,
          step_error: error ? error.message : null,
          step_end_time: new Date().toISOString(),
          step_latency: Date.now() - stepStart,
          tool_provider: provider,
          options,
          step_status: error ? "failed" : "success",
          ...(tracer._stepMeta.tokenUsage && { tokens: tracer._stepMeta.tokenUsage }),
        };

        tracer.currentRun.steps.push(step);

        delete tracer._stepMeta;
        delete tracer.recordTokens;

        if (error) throw error;
        return result;
      };
    };
  }

  endRun(finalResult, status = "complete") {
    if (!this.currentRun) throw new Error("No active run. Call startRun first.");

    const endTimestamp = new Date().toISOString();
    this.currentRun.final_output = finalResult;
    this.currentRun.status = status;
    this.currentRun.end_timestamp = endTimestamp;
    this.currentRun.duration = new Date(endTimestamp) - new Date(this.currentRun.start_timestamp);

    if (this.debug) {
      this._writeDebugFile();
    }

    this._postLog();

    if (this._spolm) {
      this._triggerLearning(finalResult, status);
    }
  }

  _triggerLearning(finalResult, status) {
    const outcome = status === "complete" ? "success" : "failure";
    const run = this.currentRun;
    // fire and forget — never blocks endRun
    Promise.resolve().then(() =>
      this._spolm.record({
        task: run.user_task,
        outcome,
        trajectory: run.steps,
        result: finalResult,
      })
    ).catch(() => {});
  }

  _postLog() {
    postLog(this.apiKey, this.agentId, this.currentRun, this.baseUrl).catch(() => {});
  }

  _writeDebugFile() {
    try {
      const debugDir = path.resolve(__dirname, "../debug-logs");
      if (!fs.existsSync(debugDir)) fs.mkdirSync(debugDir, { recursive: true });
      const ts = new Date().toISOString().replace(/[:.]/g, "-");
      fs.writeFileSync(
        path.join(debugDir, `log_${ts}.json`),
        JSON.stringify(this.currentRun, null, 2),
        "utf8"
      );
    } catch (e) {
      console.warn("[spolm] Failed to write debug log:", e.message);
    }
  }
}

module.exports = Tracer;
