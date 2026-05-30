# Invoke a Foundry-hosted agent via REST

Every other notebook in `08-agents` invokes agents through the SDK wrapper:

```python
openai_client = project_client.get_openai_client()
response = openai_client.responses.create(
    input=[{"role": "user", "content": "Tell me a one line story"}],
    extra_body={"agent_reference": {"name": agent.name, "type": "agent_reference"}},
)
```

That SDK call is a thin wrapper over an OpenAI-compatible HTTP endpoint. This lab strips the wrapper away and calls the same endpoint with `requests`, so the wire-level contract is visible. There is no new agent capability here - the point is to make the underlying protocol explicit and portable (any language, no SDK).

---

## Contents

1. [Concepts](#1-concepts)
2. [Endpoint and authentication](#2-endpoint-and-authentication)
3. [Request and response shape](#3-request-and-response-shape)
4. [SDK call vs raw REST](#4-sdk-call-vs-raw-rest)
5. [Notebooks in this lab](#5-notebooks-in-this-lab)
6. [Prerequisites](#6-prerequisites)
7. [When to prefer REST over the SDK](#7-when-to-prefer-rest-over-the-sdk)
8. [Primary sources](#8-primary-sources)

---

## 1. Concepts

The Foundry Agent Service exposes its agent runtime as an OpenAI-compatible **Responses API**. The same surface that the OpenAI Python SDK targets when you call `client.responses.create()` is reachable directly over HTTPS with any HTTP client.

Two facts make this work:

| Fact | Source |
|------|--------|
| The OpenAI client returned by `project_client.get_openai_client()` has its `base_url` set to `{project_endpoint}/openai/v1`. | `azure/ai/projects/_patch.py` (the SDK's `get_openai_client` method). |
| The same client uses a bearer token scoped to `https://ai.azure.com/.default` for authentication. | Same file - `get_bearer_token_provider(credential, "https://ai.azure.com/.default")`. |

Together they pin down the REST contract: a `POST` to `{project_endpoint}/openai/v1/responses` with an `Authorization: Bearer <token>` header.

---

## 2. Endpoint and authentication

**Endpoint shape:**

```
POST {ALPHA_FOUNDRY_PROJECT_ENDPOINT}/openai/v1/responses
```

For example, if `ALPHA_FOUNDRY_PROJECT_ENDPOINT` is
`https://alpha-foundry.services.ai.azure.com/api/projects/alpha-proj`, the full URL is
`https://alpha-foundry.services.ai.azure.com/api/projects/alpha-proj/openai/v1/responses`.

**Authentication:**

| Field | Value |
|-------|-------|
| Header | `Authorization: Bearer <access_token>` |
| Token audience (scope) | `https://ai.azure.com/.default` |
| How to obtain | `DefaultAzureCredential().get_token("https://ai.azure.com/.default")` |

The token expires (typically after one hour). The notebooks fetch a token once per invocation for clarity; production code should cache it and refresh on `401`.

---

## 3. Request and response shape

**Request body** (JSON):

```json
{
  "input": [
    { "role": "user", "content": "Tell me a one line story" }
  ],
  "agent_reference": {
    "name": "storytelling-agent",
    "type": "agent_reference"
  }
}
```

- `input` accepts the same shapes the SDK accepts: a plain string, a list of message objects, or a list mixing messages and tool outputs.
- `agent_reference` is the same object the SDK puts in `extra_body`. With `type: "agent_reference"` and a `name`, the service resolves the latest version of that agent; add `"version": "<n>"` to pin a specific version.

**Response body** (JSON, abbreviated):

```json
{
  "id": "resp_01H...",
  "object": "response",
  "status": "completed",
  "output": [
    {
      "type": "message",
      "role": "assistant",
      "content": [
        { "type": "output_text", "text": "..." }
      ]
    }
  ],
  "output_text": "..."
}
```

The `output_text` field is a convenience aggregate of all `output_text` parts across the output items. `output` is the structured form (and is where `function_call`, `mcp_tool_call`, and other item types appear).

**Multi-turn:** add `"previous_response_id": "resp_..."` at the top level on the follow-up call. See `08-09-02-rest-multi-turn.ipynb`.

**Streaming:** add `"stream": true` to receive a `text/event-stream` response. See `08-09-03-rest-streaming.ipynb`.

---

## 4. SDK call vs raw REST

The two are equivalent:

```python
# SDK (from 08-01)
openai_client.responses.create(
    input=[{"role": "user", "content": "Tell me a one line story"}],
    extra_body={"agent_reference": {"name": "storytelling-agent", "type": "agent_reference"}},
)
```

```python
# Raw REST (this lab)
requests.post(
    f"{endpoint}/openai/v1/responses",
    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    json={
        "input": [{"role": "user", "content": "Tell me a one line story"}],
        "agent_reference": {"name": "storytelling-agent", "type": "agent_reference"},
    },
)
```

What `extra_body` does in the SDK is exactly what flattening the dict into the JSON body does in the REST call.

---

## 5. Notebooks in this lab

| Notebook | Pattern |
|----------|---------|
| [`08-09-01-rest-single-shot.ipynb`](08-09-01-rest-single-shot.ipynb) | One `POST /responses`, print `output_text`. The smallest possible REST invocation. |
| [`08-09-02-rest-multi-turn.ipynb`](08-09-02-rest-multi-turn.ipynb) | Two `POST`s linked by `previous_response_id`, showing the same continuation primitive that HITL uses to submit tool results. |
| [`08-09-03-rest-streaming.ipynb`](08-09-03-rest-streaming.ipynb) | `stream: true` plus SSE parsing - reads `response.output_text.delta` events and prints text incrementally. |

All three target the same agent (`storytelling-agent` from `08-01`) so the variable is the protocol pattern, not the agent.

---

## 6. Prerequisites

1. Run [`08-01-create-versioned-storytelling-agent.ipynb`](../08-01-create-versioned-storytelling-agent.ipynb) once so that an agent named `storytelling-agent` exists in your project.
2. `ALPHA_FOUNDRY_PROJECT_ENDPOINT` set in the repo `.env` (the same variable every other 08-agents notebook reads).
3. Authenticated `az login` session - `DefaultAzureCredential` falls back to your Azure CLI credentials.

No new packages are required - `requests` and `azure-identity` are already in the repo's `pyproject.toml`.

---

## 7. When to prefer REST over the SDK

The SDK is the right default for production Python code: typed output items, automatic token refresh, retries, and streaming helpers come for free. Reach for raw REST when:

| Reason | Example |
|--------|---------|
| Non-Python language | A Go, Rust, .NET, or shell client that does not have a Foundry SDK. |
| Debugging the wire format | Confirming what headers, query parameters, or body shape the SDK sends. |
| Minimal-dependency environments | Edge functions or containers where pulling in `openai` + `azure-ai-projects` is too heavy. |
| Pinning behaviour | The SDK can change defaults across versions; a raw REST call freezes the contract you depend on. |

Trade-off: you give up SDK conveniences and own token refresh, retry, error parsing, and SSE parsing yourself.

---

## 8. Primary sources

- [Azure AI Foundry Responses API reference](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/responses) - the canonical contract.
- [OpenAI Responses API reference](https://platform.openai.com/docs/api-reference/responses) - field-by-field documentation for `input`, `output`, `previous_response_id`, and the streaming event types.
- `azure-ai-projects` `get_openai_client` implementation - source of the `{endpoint}/openai/v1` base URL and `https://ai.azure.com/.default` token scope used here.
