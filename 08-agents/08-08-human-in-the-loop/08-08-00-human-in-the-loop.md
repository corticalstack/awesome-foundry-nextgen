# Human-in-the-loop (HITL)

This lab demonstrates the **Human-in-the-Loop (HITL)** pattern: intercepting agent tool calls before execution to obtain human approval for high-impact or irreversible actions.

---

## Contents

1. [Concepts](#1-concepts)
2. [When to use HITL](#2-when-to-use-hitl)
3. [HITL approval loop](#3-hitl-approval-loop)
4. [Responses API pattern](#4-responses-api-pattern)
5. [Tool routing](#5-tool-routing)
6. [Approval and rejection flows](#6-approval-and-rejection-flows)
7. [Multi-step scenarios](#7-multi-step-scenarios)
8. [Related patterns](#8-related-patterns)
9. [Files in this lab](#9-files-in-this-lab)
10. [Primary sources](#10-primary-sources)

---

## 1. Concepts

**Human-in-the-Loop (HITL)** is a pattern where an agent pauses before executing certain tools and requires a human operator to approve or reject the action. This gives humans control over high-impact, irreversible, or compliance-sensitive operations while still delegating routine tasks to the agent automatically.

The Foundry Agent Service implements HITL naturally through the Responses API: when an agent has `FunctionTool` tools attached, it returns tool call requests as `function_call` output items rather than executing them. The caller is responsible for executing the tools - which means the caller can insert an approval step before doing so.

Key terms:

| Term | Description |
|------|-------------|
| `function_call` output item | An output item in `response.output` indicating the agent wants to call a tool - the API does **not** execute it |
| `function_call_output` | The message type used to submit tool execution results back to the Responses API |
| `previous_response_id` | Used to continue a response chain when submitting tool results in a new `responses.create()` call |
| `APPROVAL_REQUIRED_TOOLS` | Convention used in this lab: a set of tool names that trigger the human approval branch |

---

## 2. When to use HITL

HITL is appropriate whenever agent actions have consequences that warrant human oversight before execution:

| Scenario | Why HITL? |
|----------|-----------|
| **Financial transactions** | Fund transfers are irreversible - a mistake cannot be undone |
| **Email and messaging** | Sending a message to the wrong recipient or with incorrect content is hard to retract |
| **Data deletion or modification** | Deleting records or bulk-updating a database can cause data loss |
| **External API calls with side effects** | Placing orders, triggering deployments, or invoking billing APIs |
| **Compliance-sensitive operations** | Actions that require an audit trail or four-eyes approval under regulatory frameworks |

For read-only or idempotent operations (balance checks, searches, lookups), auto-execution is appropriate.

---

## 3. HITL approval loop

The HITL pattern implemented in [`08-08-01-human-in-the-loop.ipynb`](08-08-01-human-in-the-loop.ipynb) follows this loop:

```
responses.create(user_message)
    |
    v
response.output contains function_call items?
    |
    +-- No  --> return response.output_text   (done)
    |
    +-- Yes --> for each tool_call:
                    if name in APPROVAL_REQUIRED_TOOLS:
                        display tool name + arguments to operator
                        operator enters "yes" or "no"
                        if "yes"  --> execute tool, capture result
                        if "no"   --> result = "Action rejected by operator"
                    else:
                        auto-execute, capture result
                collect all tool_outputs
                responses.create(tool_outputs, previous_response_id=response.id)
                loop back ^
```

The loop exits when `response.output` contains no `function_call` items - at which point `response.output_text` holds the agent's final answer.

---

## 4. Responses API pattern

The core Responses API calls used in the HITL loop:

```python
# Initial call - start a new agent turn
response = openai_client.responses.create(
    input=[{"role": "user", "content": user_message}],
    extra_body={"agent_reference": {"name": agent.name, "type": "agent_reference"}},
)

# Continuation call - submit tool results and get the next response
response = openai_client.responses.create(
    input=tool_outputs,               # list of function_call_output dicts
    previous_response_id=response.id, # links this call to the previous turn
    extra_body={"agent_reference": {"name": agent.name, "type": "agent_reference"}},
)
```

Each `tool_outputs` entry has this structure:

```python
{
    "type": "function_call_output",
    "call_id": call.call_id,   # matches the call_id from the function_call item
    "output": result,           # string result of executing (or rejecting) the tool
}
```

`previous_response_id` tells the service that this call is a continuation of an existing response chain, allowing the agent to maintain context across multiple tool call rounds.

---

## 5. Tool routing

In this lab, the routing decision is made by checking whether a tool name is in the `APPROVAL_REQUIRED_TOOLS` set:

```python
APPROVAL_REQUIRED_TOOLS = {"transfer_funds"}

for call in tool_calls:
    if call.name in APPROVAL_REQUIRED_TOOLS:
        # Human approval required
        ...
    else:
        # Auto-execute
        result = TOOL_IMPLEMENTATIONS[call.name](json.loads(call.arguments))
```

**Advantages of the set-based convention:**
- Simple to understand and extend - add a tool name to the set to require approval
- No SDK dependency - works with any version of `azure-ai-projects`
- Explicit - the approval policy is visible in code without SDK knowledge

**Limitations:**
- Policy is defined in the client, not the tool - multiple clients must each maintain consistent sets
- No per-invocation context - the decision is based solely on the tool name, not the argument values

See [Section 8](#8-related-patterns) for how this manual routing relates to the MAF `@tool(approval_mode=...)` decorator (a different runtime layer) and the Foundry `MCPTool(require_approval=...)` server-side flag (MCP tools only).

---

## 6. Approval and rejection flows

### Approval

When the operator enters `yes`, the tool is executed with its original arguments and the result is submitted as a `function_call_output`:

```python
result = TOOL_IMPLEMENTATIONS[call.name](json.loads(call.arguments))
tool_outputs.append({
    "type": "function_call_output",
    "call_id": call.call_id,
    "output": result,
})
```

The agent receives the successful result and generates a confirmation response.

### Rejection

When the operator enters `no`, a rejection message is submitted as the tool result instead:

```python
result = f"Action '{call.name}' was rejected by the human operator."
tool_outputs.append({
    "type": "function_call_output",
    "call_id": call.call_id,
    "output": result,
})
```

The agent receives the rejection message and acknowledges that the action was not taken. Because the rejection is submitted as a valid `function_call_output`, the conversation continues normally - the agent can respond with an explanation or offer alternatives.

---

## 7. Multi-step scenarios

The HITL loop handles scenarios where a single user message triggers multiple tool calls, including a mix of auto-execute and approval-required tools.

In the multi-step scenario in [`08-08-01-human-in-the-loop.ipynb`](08-08-01-human-in-the-loop.ipynb), the agent:
1. Calls `get_account_balance` - auto-executed, no prompt shown
2. Then calls `transfer_funds` - HITL prompt appears

Both tool calls may be returned in the same `response.output` batch, or the agent may make them in sequence across multiple loop iterations. The `APPROVAL_REQUIRED_TOOLS` routing handles both cases correctly.

> **Note on batching:** The Responses API may return multiple `function_call` items in a single `response.output`. The HITL loop processes all of them before making the continuation `responses.create()` call - collecting all `tool_outputs` first and submitting them together.

---

## 8. Related patterns

Three different "approval" layers exist across the stack. This lab uses the third one because the first two do not cover its scenario (custom `FunctionTool` on a Foundry-hosted versioned agent).

### 8.1 MAF `@tool(approval_mode="always_require")` - client-side runtime approvals

Released in `agent-framework-core` and available in the version this repo pins (`1.0.0rc6`). Applies when the agent runs in the local [Microsoft Agent Framework (MAF)](https://learn.microsoft.com/en-us/agent-framework/tutorials/agents/function-tools-approvals?pivots=programming-language-python) runtime (`Agent(client=OpenAIChatClient(), ...)`), **not** when calling a Foundry-hosted agent through the Responses API. The MAF runtime returns `user_input_requests` on the run result; the caller replies with a `Message` containing `req.create_response(True|False)` to resume.

```python
from typing import Annotated
from agent_framework import tool

@tool
def get_account_balance(account_id: Annotated[str, "Account ID"]) -> str:
    ...

@tool(approval_mode="always_require")
def transfer_funds(from_account: Annotated[str, "Source account ID"],
                   to_account:   Annotated[str, "Destination account ID"],
                   amount:       Annotated[float, "Amount in USD"]) -> str:
    ...
```

The decorator name is `@tool` (the `@ai_function` alias appears in some API reference pages but is not exported by the `rc6` package this repo pins).

### 8.2 Foundry `MCPTool(require_approval="always")` - server-side MCP approvals

Native server-side approval routing on the Foundry Agent Service, but only for MCP tools. When approval is required the Responses API returns an `mcp_approval_request` output item; the client submits an `mcp_approval_response` to continue. See: [Connect to MCP Server Endpoints for agents](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/model-context-protocol).

### 8.3 Manual interception - what this lab does

For custom `FunctionTool` definitions on a Foundry-hosted agent there is no first-class `require_approval` flag in the current SDK (`azure-ai-projects` rc6 `FunctionTool` exposes only `name` / `description` / `parameters` / `strict` / `type`). The `APPROVAL_REQUIRED_TOOLS` set + Responses API loop demonstrated in this lab is the canonical pattern for this scenario.

---

## 9. Files in this lab

| File | Purpose |
|------|---------|
| [`08-08-01-human-in-the-loop.ipynb`](08-08-01-human-in-the-loop.ipynb) | Lab notebook - configuration, tool definitions, HITL loop helper, and three scenarios: approve, reject, and multi-step |

---

## 10. Primary sources

- [azure-ai-projects SDK - FunctionTool and PromptAgentDefinition](https://pypi.org/project/azure-ai-projects/) - Python SDK for the Foundry Agent Service
- [OpenAI Responses API - function calling](https://platform.openai.com/docs/guides/function-calling) - how function calls are returned as output items and how tool results are submitted via `previous_response_id`
- [MAF Function Tools with Human-in-the-Loop Approvals](https://learn.microsoft.com/en-us/agent-framework/tutorials/agents/function-tools-approvals?pivots=programming-language-python) - `@tool(approval_mode="always_require")` pattern for MAF client-side runtime agents
- [Connect to MCP Server Endpoints for agents](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/model-context-protocol) - Foundry server-side `MCPTool(require_approval="always")` approval routing
