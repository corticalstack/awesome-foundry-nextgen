# Agent memory

This lab demonstrates how to use the Foundry Agent Service Memory API to give agents persistent, per-user memory across conversations. Agents can store facts, preferences, conversation summaries, and user profiles - and retrieve them automatically at inference time via the `memory_search` tool.

---

## Contents

1. [Concepts](#1-concepts)
2. [Infrastructure requirements](#2-infrastructure-requirements)
3. [Memory API reference](#3-memory-api-reference)
4. [Memory store operations](#4-memory-store-operations)
5. [Scope isolation](#5-scope-isolation)
6. [The `memory_search` tool](#6-the-memory_search-tool)
7. [Automatic memory extraction](#7-automatic-memory-extraction)
8. [Lab scenarios](#8-lab-scenarios)
9. [Known limitations](#9-known-limitations)
10. [Files in this lab](#10-files-in-this-lab)
11. [Primary sources](#11-primary-sources)

---

## 1. Concepts

A **memory store** is a named, project-scoped container that holds extracted memories for multiple users. Each memory store is backed by two local model deployments on the same Foundry account:

- A **chat model** (`gpt-4.1-mini`) for extraction operations: summarising conversations, extracting facts, building user profiles.
- An **embedding model** (`text-embedding-3-small`) for semantic indexing and similarity search over stored memories.

Memory stores hold items of the following types:

| Type | Description |
|------|-------------|
| `fact` | A discrete fact extracted from a conversation (e.g., "User is interested in Mars rovers") |
| `preference` | A stated or inferred preference (e.g., "User prefers concise answers") |
| `summary` | A rolling summary of one or more conversation turns |
| `profile` | A structured user profile built up over time from all interactions |

Each memory item is associated with a **scope** - a string that identifies the user or context the memory belongs to. Scope values are arbitrary strings in direct API calls; when using the `memory_search` tool in an agent, the server can resolve scope to the caller's Entra identity automatically (see [Scope isolation](#5-scope-isolation)).

---

## 2. Infrastructure requirements

### Why a dedicated account?

The Memory API requires **local** (non-APIM) model access for its internal summarisation and embedding operations. This makes it incompatible with the hub/spoke gateway pattern used in the other labs, where a deny-model-deployments policy blocks local deployments in spoke resource groups. A separate dedicated resource group (`rg-foundry-memory-{suffix}`) is used, which is excluded from that policy.

### Resources (from [`main.bicep`](main.bicep))

| Resource | Type | Name pattern |
|----------|------|--------------|
| Foundry account | `Microsoft.CognitiveServices/accounts` (AIServices, S0, SystemAssigned identity) | `aif-memory-{suffix}` |
| Chat model deployment | GlobalStandard, capacity 30, `gpt-4.1-mini@2025-04-14` | `gpt-4.1-mini` |
| Embedding model deployment | Standard, capacity 30, `text-embedding-3-small@1` | `text-embedding-3-small` |
| Project | `Microsoft.CognitiveServices/accounts/projects` (SystemAssigned identity) | `project-{teamName}-memory-{suffix}` |

### RBAC assignments

| Principal | Role | Role Definition ID |
|-----------|------|--------------------|
| Deployer (User) | Cognitive Services User | `a97b65f3-24c7-4388-baec-2e87135dc908` |
| Project managed identity (SP) | Foundry User | `53ca6127-db72-4b80-b1b0-d745d6d5456d` |
| Project managed identity (SP) | Cognitive Services OpenAI User | `5e0bd9bd-7b93-4f28-af87-19fc36ad61bd` |

All RBAC assignments are scoped to the Foundry account resource.

### Output environment variables

The Bicep outputs are used to populate `.env`:

| Output | Env var |
|--------|---------|
| `accountName` | `ALPHA_MEMORY_FOUNDRY_ACCOUNT` |
| `projectEndpoint` | `ALPHA_MEMORY_PROJECT_ENDPOINT` |

---

## 3. Memory API reference

### Endpoint pattern

```
https://{account_name}.services.ai.azure.com/api/projects/{project_name}/{path}?api-version=2025-11-15-preview
```

All paths used in this lab are relative to the project endpoint. The `MemoryClient` class in [`memory_helpers.py`](memory_helpers.py) constructs URLs as:

```python
self.base_url = f"https://{account_name}.services.ai.azure.com/api/projects/{project_name}"

def _url(self, path: str) -> str:
    return f"{self.base_url}/{path}?api-version={self.API_VERSION}"
```

**API version:** `2025-11-15-preview`

### Authentication

The Memory API uses bearer tokens scoped to `https://ai.azure.com`. The helper in [`memory_helpers.py`](memory_helpers.py) obtains tokens via `az account get-access-token`:

```python
result = subprocess.run(
    'az account get-access-token --resource https://ai.azure.com --query accessToken -o tsv',
    shell=True, capture_output=True, text=True
)
```

### Key endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `memory_stores` | Create a memory store |
| `DELETE` | `memory_stores/{name}` | Delete a memory store |
| `POST` | `memory_stores/{name}:update_memories` | Start async memory extraction (returns `update_id`) |
| `GET` | `memory_stores/{name}/updates/{update_id}` | Poll extraction status |
| `POST` | `memory_stores/{name}:search_memories` | Search memories by scope and query |

### Payload schemas

**Create store (`POST memory_stores`):**

```json
{
  "name": "space-expert-memory",
  "description": "...",
  "definition": {
    "kind": "default",
    "chat_model": "gpt-4.1-mini",
    "embedding_model": "text-embedding-3-small",
    "options": {
      "user_profile_enabled": true,
      "user_profile_details": "...",
      "chat_summary_enabled": true
    }
  }
}
```

**Update memories (`POST memory_stores/{name}:update_memories`):**

```json
{
  "scope": "user_alice_123",
  "items": [
    {"type": "message", "role": "user",      "content": [{"type": "input_text",  "text": "..."}]},
    {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "..."}]}
  ],
  "update_delay": 0
}
```

**Search memories (`POST memory_stores/{name}:search_memories`):**

```json
{
  "scope": "user_alice_123",
  "query": "which planet?",
  "max_num_results": 5
}
```

---

## 4. Memory store operations

The `MemoryClient` class in [`memory_helpers.py`](memory_helpers.py) wraps the three core operations.

### Instantiation

```python
from memory_helpers import MemoryClient

memory = MemoryClient(ACCOUNT_NAME, PROJECT_NAME)
```

### Create store

```python
result = memory.create_store(
    name="space-expert-memory",
    chat_model="gpt-4.1-mini",
    embedding_model="text-embedding-3-small",
    description="Memory store for the Space Expert agent",
    user_profile_details="Track users' interests in space topics, preferred planets, and mission preferences"
)
```

`create_store()` issues a `DELETE` to remove any existing store with the same name before creating the new one.

### Update memories (async + polling)

Memory extraction is asynchronous. The API returns an `update_id` which must be polled until the status is `completed` or `failed`.

```python
from memory_helpers import build_conversation

msgs = build_conversation(
    user_text="I'm really interested in Mars rovers and the search for life.",
    assistant_text="That's fascinating! The Perseverance rover has been collecting samples..."
)

result = memory.update_memories("space-expert-memory", "user_alice_123", msgs)
```

`update_memories()` implements the polling loop internally (checking every 2 seconds, up to `timeout=60` seconds):

```python
# POST to :update_memories → receives update_id
# GET memory_stores/{name}/updates/{update_id} until status == "completed"
```

### Search

```python
result = memory.search_memories(
    store_name="space-expert-memory",
    scope="user_alice_123",
    query="which planet is this user most interested in?",
    max_results=5
)
```

Returns a list of memory items with `kind` (fact/preference/summary/profile) and `content` fields.

---

## 5. Scope isolation

Scope strings partition memories within a store. Each `update_memories` and `search_memories` call includes a `scope` parameter. The service only returns memories that match the exact scope provided - there is no cross-scope leakage.

### Explicit scope

The caller supplies a concrete scope string (e.g., `"user_alice_123"`, `"user_bob_456"`). This is used in direct API calls and in agent definitions where the scope is fixed at registration time:

```python
tools=[{
    "type": "memory_search",
    "memory_store_name": MEMORY_STORE_NAME,
    "scope": "user_alice_123",
    "update_delay": 1
}]
```

An agent registered with an explicit scope will use the same scope for every caller - suitable for single-user agents or testing.

### `{{$userId}}` server-side resolution

For multi-user production scenarios, set `scope` to the literal string `"{{$userId}}"`. The server resolves this at inference time to `{tenantId}_{objectId}` from the caller's Entra token. This allows a single shared agent version to maintain isolated memories for every user without any client-side scope management:

```python
tools=[{
    "type": "memory_search",
    "memory_store_name": MEMORY_STORE_NAME,
    "scope": "{{$userId}}",
    "update_delay": 1
}]
```

---

## 6. The `memory_search` tool

Agents access memory stores via the built-in `memory_search` tool type. The tool is declared in the agent definition and is invoked automatically by the agent service during inference - the agent retrieves relevant memories before generating a response.

### Agent creation

```python
from azure.ai.projects.models import PromptAgentDefinition

agent = project_client.agents.create_version(
    agent_name="SpaceExpert",
    definition=PromptAgentDefinition(
        model=LOCAL_CHAT,
        instructions="You are a space expert. Use stored memories to personalise your answers.",
        tools=[{
            "type": "memory_search",
            "memory_store_name": MEMORY_STORE_NAME,
            "scope": "user_alice_123",
            "update_delay": 1
        }]
    )
)
```

`LOCAL_CHAT` is a string of the form `"{hub_connection}/{model_name}"` - e.g. `"aif-memory-{suffix}/gpt-4.1-mini"` - referencing the local deployment on the dedicated Foundry account.

### Responses API invocation

Agents are invoked via the OpenAI Responses API using an `agent_reference`:

```python
response = openai_client.responses.create(
    input=query,
    extra_body={
        "agent": {
            "name": agent.name,
            "version": agent.version,
            "type": "agent_reference"
        }
    }
)
```

The `openai_client` is an `openai.AzureOpenAI` instance pointed at the Foundry project endpoint, authenticated with a bearer token scoped to `https://ai.azure.com`.

---

## 7. Automatic memory extraction

When `update_delay` is set to a positive integer (e.g., `1`) in the `memory_search` tool definition, the agent service **automatically extracts memories** from each conversation turn in the background - no explicit `update_memories()` call is needed. The value represents a delay in seconds between the end of the conversation and the start of extraction.

```python
tools=[{
    "type": "memory_search",
    "memory_store_name": MEMORY_STORE_NAME,
    "scope": "{{$userId}}",
    "update_delay": 1   # extract memories 1 second after each turn
}]
```

With `update_delay=0` (the default in direct API calls), extraction must be triggered manually. With `update_delay=1`, each Responses API call passively accumulates memories from the conversation history, building up the user's memory store over time without any additional code.

---

## 8. Lab scenarios

All five scenarios are implemented in [`deploy.ipynb`](deploy.ipynb):

| # | Scenario | Description |
|---|----------|-------------|
| 1 | Create Memory Store | Creates `space-expert-memory` with `gpt-4.1-mini` + `text-embedding-3-small`; enables `user_profile` and `chat_summary` extraction. |
| 2 | Store User Memories | Manually extracts memories via `update_memories()` with async polling for two users: Alice (interested in Mars/rovers) and Bob (interested in Saturn/Europa). |
| 3 | Scope isolation | Searches both scopes with the same query; confirms each user's search only returns their own memories and not the other's. |
| 4 | Agent + Memory | Creates a `SpaceExpert` agent with explicit scope `"user_alice_123"`; demonstrates that the same query yields different personalised responses for Alice vs Bob. |
| 4b | `{{$userId}}` Scope | Creates a second version of `SpaceExpert` with `scope: "{{$userId}}"`; scope is resolved server-side from the caller's Entra token to `{tid}_{oid}`, enabling per-user isolation without client scope management. |
| 5 | Automatic Extraction | Creates an agent with `update_delay=1`; Charlie's conversation is automatically extracted into memory after each Responses API call, demonstrating passive accumulation without explicit `update_memories()` calls. |

---

## 9. Known limitations

- **BYO gateway model incompatibility**: The `memory_search` tool and the Memory API's internal extraction pipeline require **local** model deployments on the same Foundry account. APIM-routed models (the hub/spoke gateway pattern used in other labs) are not supported. This is why the agent memory deployment provisions a dedicated resource group with its own model deployments, separate from the spoke resource groups.

- **Preview API**: All Memory API functionality uses API version `2025-11-15-preview`. Preview APIs are subject to breaking changes and are not covered by production SLAs.

---

## 10. Files in this lab

| File | Purpose |
|------|---------|
| [`main.bicep`](main.bicep) | Bicep template - deploys dedicated Foundry account, model deployments, project, and RBAC assignments |
| [`deploy.ipynb`](deploy.ipynb) | Lab notebook - all five scenarios end-to-end |
| [`memory_helpers.py`](memory_helpers.py) | `MemoryClient` class and `build_conversation()` helper |
| [`display_helpers.py`](display_helpers.py) | Notebook display helpers: `show_config`, `show_store_created`, `show_memories`, `show_search_results`, `show_agent_created`, `show_conversation`, `show_error` |

---

## 11. Primary sources

- [Memory in Microsoft Foundry Agent Service](https://learn.microsoft.com/en-us/azure/ai-foundry/agents/concepts/what-is-memory?view=foundry&preserve-view=true&tabs=conversational-agent) - conceptual overview of memory types, store lifecycle, and scope model
- [Create and use memory in Foundry Agent Service](https://learn.microsoft.com/en-us/azure/ai-foundry/agents/how-to/memory-usage?view=foundry&tabs=python) - how-to guide: API calls, agent tool configuration, `{{$userId}}` pattern

---

[Next: Deploy agent memory →](deploy.ipynb)
