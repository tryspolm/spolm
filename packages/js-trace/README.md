# @spolm/tracer

[![npm version](https://img.shields.io/npm/v/@spolm/tracer.svg)](https://www.npmjs.com/package/@spolm/tracer)
[![npm downloads](https://img.shields.io/npm/dm/@spolm/tracer.svg)](https://www.npmjs.com/package/@spolm/tracer)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

The **Spolm JavaScript SDK** enables JS developers to trace, visualize, and debug agent workflows in real time. It acts as the basis of all of Spolm's services.

The SDK is built from the ground up to integrate cleanly into custom agent implementations. We are working rigorously on framework compatibility at the moment, and hope to have it up soon.

------------------------------------------------------------------------

## Benefits

-   Real-time tracing of agent workflows in production
-   Step-level logging (LLM calls, tools, planners, etc.)
-   Token usage and latency tracking
-   Full, working compatibility with features on the Spolm website

------------------------------------------------------------------------

## Prerequisites

-   Node.js 18+
-   A Spolm account

> **Note**\
> The SDK uses an API key management system for authentication.\
> Visit the Spolm website to generate an **API key** and **agent ID**
> before integrating.

------------------------------------------------------------------------

## Installation

```bash
npm install @spolm/tracer
```

------------------------------------------------------------------------

## Quickstart

### 1. Initialize the Tracer

Create a Tracer instance in the same file where your agent is defined.

```javascript
const Tracer = require("@spolm/tracer");

const tracer = new Tracer(
  process.env.TRACER_API_KEY,   // API key from Spolm dashboard
  process.env.TRACER_AGENT_ID   // Agent ID from Spolm dashboard
);
```

------------------------------------------------------------------------

### 2. Start a Run

A run represents a single execution of your agent for a given user task.
All subsequent steps are automatically associated with this run.

```javascript
const runId = tracer.startRun(
  "this is my first prompt for my new agent!",
  {
    userId: "user_123",
    environment: "production",
  } // metadata
);
```

------------------------------------------------------------------------

### 3. Log Agent Steps

Identify functions in your agent that represent meaningful actions, such as:

- LLM calls
- Tool executions
- Planners or routers

Wrap each function using `logStep`.

```javascript
async function callLLM(prompt) { // replace callLLM with your own agent's function
  // Your LLM call logic here
  return response;
}

const tracedLLMCall = tracer.logStep({
  stepName: "llm_call",
  stepType: "model",
  provider: "openai",
})(callLLM);
```

**Important**: Repeat this step for every function in the agent workflow that you want to trace.

------------------------------------------------------------------------

### 4. Execute Your Agent

Use the traced functions inside your agent logic.

```javascript
async function runAgent(task) {
  return await tracedLLMCall(task);
}

const finalOutput = await runAgent(
  "This is my first prompt for my new agent!"
);
```

------------------------------------------------------------------------

### 5. End the Run

Once the agent completes execution, explicitly end the run.

```javascript
tracer.endRun(finalOutput);
```

Ending a run finalizes:

- Total run duration
- Final output
- All logged steps

And that's it! Your completed run will be available in the Spolm dashboard.

------------------------------------------------------------------------

## Tracer Class

The Tracer class is the core abstraction in the Spolm SDK. It contains all the functions and attributes required for managing the agent's lifecycle alongside the Spolm platform.

### Initialization

```javascript
const tracer = new Tracer(apiKey, agentId, options?)
```

| Name      | Type     | Required | Description                  |
| --------- | -------- | -------- | ---------------------------- |
| `apiKey`  | `string` | ✅        | Spolm API key                |
| `agentId` | `string` | ✅        | Agent ID from dashboard      |
| `options` | `object` | ❌        | Optional hooks and exporters (metadata) |

### Starting a Run

```javascript
const runId = tracer.startRun(userTask, metadata?)
```

| Name       | Type     | Required | Description                       |
| ---------- | -------- | -------- | --------------------------------- |
| `userTask` | `string` | ✅        | Description of the user's request to the agent |
| `metadata` | `object` | ❌        | Arbitrary metadata      |

**Returns:** 
- `string`: the generated run_id

### Logging a Step

```javascript
const wrappedFn = tracer.logStep({
  stepName: "", 
  stepType: "", 
  provider?: "", 
  options?: {}
})(originalFn)
```

**Dictionary Parameters**

| Key        | Type     | Required | Description                           |
| ---------- | -------- | -------- | ------------------------------------- |
| `stepName` | `string` | ✅        | Step name             |
| `stepType` | `string` | ✅        | Step category (`model`, `tool`, etc.) |
| `provider` | `string` | ❌        | Tool or model provider (`OpenAI`, `Gemini`, etc.)                |
| `options`  | `object` | ❌        | Arbitrary metadata               |

**Wrapped Function**

| Name         | Type       | Required | Description                           |
| ------------ | ---------- | -------- | ------------------------------------- |
| `originalFn` | `function` | ✅        | Step function for Spolm to log.       |

**Returns:** 
- `function`: the normal step function (originalFn) wrapped with logging capabilities

### Recording Token Usage

Inside a wrapped function, you can record token usage for LLM calls:

```javascript
const tracedLLMCall = tracer.logStep({
  stepName: "llm_call",
  stepType: "model",
  provider: "openai"
})(async (prompt) => {
  const response = await openai.chat.completions.create({
    model: "gpt-4",
    messages: [{ role: "user", content: prompt }]
  });
  
  // Record token usage
  if (tracer.recordTokens) {
    tracer.recordTokens({
      input: response.usage.prompt_tokens,
      output: response.usage.completion_tokens,
      total: response.usage.total_tokens
    });
  }
  
  return response.choices[0].message.content;
});
```

### Ending a Run

```javascript
tracer.endRun(finalOutput, status = "complete")
```

| Name          | Type     | Required | Description        |
| ------------- | -------- | -------- | ------------------ |
| `finalOutput` | `any`    | ✅        | Final agent result |
| `status`      | `string` | ❌        | Run status (`complete`, `failed`, etc.) |

**Returns:** 
- N/A, entire run is posted to Spolm platform

------------------------------------------------------------------------

## Complete Example

```javascript
const Tracer = require("@spolm/tracer");

async function main() {
  // Initialize tracer
  const tracer = new Tracer(
    process.env.SPOLM_API_KEY,
    process.env.SPOLM_AGENT_ID
  );
  
  // Start run
  const runId = tracer.startRun(
    "Process customer order",
    {
      orderId: "12345",
      customerId: "67890"
    }
  );
  
  // Define traced steps
  const validateOrder = tracer.logStep({
    stepName: "validate_order",
    stepType: "tool"
  })(async (order) => {
    // Validation logic
    return { valid: true, order };
  });
  
  const processPayment = tracer.logStep({
    stepName: "process_payment",
    stepType: "tool",
    provider: "stripe"
  })(async (order) => {
    // Payment processing
    return { success: true, transactionId: "tx_123" };
  });
  
  // Execute steps
  try {
    const order = { id: "12345", amount: 99.99 };
    const validated = await validateOrder(order);
    const payment = await processPayment(validated.order);
    
    tracer.endRun("Order processed successfully", "complete");
  } catch (error) {
    tracer.endRun(`Error: ${error.message}`, "failed");
  }
}

main();
```

------------------------------------------------------------------------

## Error Handling

The tracer automatically captures errors in wrapped functions:

```javascript
const riskyFunction = tracer.logStep({
  stepName: "risky_operation",
  stepType: "tool"
})(async () => {
  // If this throws, the error is automatically logged
  throw new Error("Something went wrong");
});

try {
  await riskyFunction();
} catch (error) {
  // Error is already logged in the step
  // Handle error as needed
}
```

------------------------------------------------------------------------

## Getting Your API Key

1. Sign up at [spolm.com](https://spolm.com)
2. Create an agent in your dashboard
3. Generate an API key in settings
4. Use the API key and agent ID in your code

------------------------------------------------------------------------

## License

MIT

------------------------------------------------------------------------

## Support

- 📖 [Documentation](https://github.com/Tanrocode/spolm)
- 🐛 [Report Issues](https://github.com/Tanrocode/spolm/issues)
- 💬 [Get Help](https://spolm.com/support)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
