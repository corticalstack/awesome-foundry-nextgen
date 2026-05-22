# MCP conceptual guide

This guide covers the Model Context Protocol (MCP) from first principles, explains how this lab's Contoso PMO KB server is built and deployed, and documents the full authentication landscape for MCP in Azure AI Foundry.

For operational setup steps and notebook walkthroughs, see [08-05-00-contoso-pmo-mcp.md](08-05-00-contoso-pmo-mcp.md).

---

## Contents

1. [Introduction to MCP](#1-introduction-to-mcp)
2. [The MCP protocol](#2-the-mcp-protocol)
3. [Local vs remote MCP servers](#3-local-vs-remote-mcp-servers)
4. [What this lab does: Contoso PMO KB MCP server](#4-what-this-lab-does-contoso-pmo-kb-mcp-server)
5. [How this lab authenticates the MCP connection](#5-how-this-lab-authenticates-the-mcp-connection)
6. [MCP authentication methods in Azure AI Foundry](#6-mcp-authentication-methods-in-azure-ai-foundry)

---

## 1. Introduction to MCP

**Model Context Protocol (MCP)** is an open protocol that standardises how AI models connect to external tools, data sources, and services. Originally developed by Anthropic and released as an open standard, MCP has been broadly adopted across the AI industry as the common interface for agentic tool invocation.

Before MCP, every AI framework invented its own integration pattern for calling external systems - a bespoke plugin format here, a custom function-calling schema there. MCP replaces these ad-hoc integrations with a single, interoperable protocol. An AI agent runtime that speaks MCP can connect to any compliant server without modification, and an MCP server written once works with any compliant agent framework.

In the context of Azure AI Foundry agents, MCP is the mechanism by which an agent discovers and calls tools hosted on a remote server. The agent runtime handles the protocol; you write the tools.

---

## 2. The MCP protocol

### Client-server model

MCP uses a three-layer architecture:

```
Host application (agent runtime)
    └── MCP client
            └── MCP server (your tools)
```

- **Host application**: the agent framework or runtime - in this lab, the Azure AI Foundry Agent Service.
- **MCP client**: the protocol layer embedded in the host that speaks MCP. The agent runtime handles this transparently.
- **MCP server**: the independently hosted process that exposes tools, resources, and prompts.

### Transport mechanisms

| Transport | Description | Use case |
|---|---|---|
| **stdio** | Standard input/output pipes; server runs as a subprocess in the same process space | Local/in-process tools, development utilities |
| **SSE (Server-Sent Events)** | HTTP-based streaming over HTTPS; server runs independently | Remote servers, Azure Functions, containers |
| **Streamable HTTP** | HTTP POST/GET with chunked transfer encoding; the successor to SSE | Remote servers where bidirectional streaming is required |

Remote MCP servers - including this lab's Azure Functions server - use SSE or Streamable HTTP. The Agent Service runtime only accepts remote endpoints; it cannot reach stdio servers.

### Protocol primitives

MCP defines three types of primitives that a server can expose:

| Primitive | Description |
|---|---|
| **Tools** | Invocable functions. The agent calls a tool by name with typed arguments; the server executes it and returns a result. |
| **Resources** | Readable data (files, database records, live feeds). The agent can read resources as context. |
| **Prompts** | Reusable prompt templates that the server exposes for the agent to fill in. |

This lab uses **tools** exclusively - 37 tools covering all CRUD operations on the Contoso PMO knowledge base.

### Tool discovery and `server_label`

When an agent connects to an MCP server, it queries the server for its tool list at runtime. The agent receives each tool's name, description, and parameter schema - the same information the model uses to decide whether and how to call a tool.

The `server_label` parameter on `MCPTool` is a unique identifier for the server within a given agent. It scopes the tool namespace so that multiple MCP servers can be attached to the same agent without naming collisions. In this lab the label is `'contoso_pmo_kb'`.

---

## 3. Local vs remote MCP servers

| | Local server | Remote server |
|---|---|---|
| **Transport** | stdio (in-process) | SSE / Streamable HTTP |
| **Deployment** | Same machine or container as the agent runtime | Independently hosted (Azure Functions, Container Apps, any HTTPS endpoint) |
| **Latency** | No network overhead | Network round-trip per tool call |
| **Scaling** | Co-located with the agent | Independently scalable |
| **Authentication** | Process-level isolation - no network auth needed | Requires explicit auth (key, Entra token, OAuth) |
| **Example** | Local filesystem tools, developer utilities | This lab's Contoso PMO KB server |

**When to choose local:** rapid prototyping, tools that need direct filesystem or OS access, scenarios where the agent runtime and tools are always co-located.

**When to choose remote:** production deployments, tools that need to scale independently, sharing a tool server across multiple agents or projects, or any scenario where the tool logic lives on managed infrastructure.

The Azure AI Foundry Agent Service runtime is a managed cloud service. It cannot reach stdio servers. All tools used by Foundry agents must be exposed as remote MCP servers over HTTPS.

---

## 4. What this lab does: Contoso PMO KB MCP server

This lab builds and deploys a **37-tool remote MCP server** on Azure Functions and connects it to a Foundry agent.

### The Contoso PMO knowledge base

The server is backed by a JSON knowledge base representing a fictional consumer product launch environment - Contoso PMO. The knowledge base is implemented in [contoso-pmo-mcp/kb.py](contoso-pmo-mcp/kb.py) and consists of two stores:

- **Registry** (`registry/`): structured records for projects, people, meetings, tasks, risks, and distribution lists
- **Documents** (`documents/`): full-text documents (minutes of meeting, lessons learned, risk reports) with an index

### The Azure Functions MCP server

[contoso-pmo-mcp/function_app.py](contoso-pmo-mcp/function_app.py) exposes every `kb.py` function as an MCP tool using the `mcpToolTrigger` binding from the standard Azure Functions extension bundle (`[4.0.0, 5.0.0)`). No beta bundle is required.

**Tool coverage by category:**

| Category | Tools |
|---|---|
| Projects | `create_project`, `get_project`, `list_projects`, `update_project` |
| People | `create_person`, `get_person`, `list_people` |
| Meetings | `create_meeting`, `get_meeting`, `list_meetings`, `update_meeting_status` |
| Tasks | `create_task`, `get_task`, `list_tasks`, `approve_task`, `update_task_status`, `reassign_task`, `delete_task` |
| Documents | `save_document`, `get_document`, `list_documents`, `approve_document`, `update_document`, `delete_document`, `search_documents` |
| Risks | `flag_risk`, `list_risks`, `search_risk_patterns` |
| Distribution lists | `create_distribution_list`, `get_distribution_list`, `update_distribution_list` |
| Cross-cutting | `get_pending_approvals`, `get_overdue_tasks`, `get_project_context`, `get_meeting_pack`, `search_lessons`, `get_person_tasks` |

**Total: 37 tools.**

### Deployment

The function app is deployed as **Flex Consumption** (Python) with managed identity for storage - no shared access keys. The bundled knowledge base is copied into `contoso-pmo-mcp/data/` at build time and deployed with the zip package.

**SSE endpoint pattern:**

```
https://<func-app>.azurewebsites.net/runtime/webhooks/mcp/sse
```

### Write persistence model

Azure Functions Flex Consumption mounts the deployed zip read-only. On the first write operation, [contoso-pmo-mcp/kb.py](contoso-pmo-mcp/kb.py) lazily copies the bundled data to `/tmp/contoso-pmo-data/` and redirects all mutations there. Writes persist within the instance lifetime but are lost on cold starts. This is intentional for a demo-grade knowledge base; production deployments should use a durable store (Cosmos DB, Azure SQL, Azure Blob Storage).

### Foundry agent

Notebook [08-05-01-contoso-pmo-agent-setup.ipynb](08-05-01-contoso-pmo-agent-setup.ipynb) creates a Foundry agent named `contoso-pmo-agent` on the admin project via `PromptAgentDefinition` (versioned-agent API) with the MCP tool dict pointing at the SSE endpoint:

```python
mcp_tool = MCPTool(
    server_label='contoso_pmo_kb',
    server_url=MCP_SSE_URL,
    require_approval='never',
)
```

`require_approval='never'` is set here because all 37 tools are fully trusted (this is a private, self-hosted server). See [Section 6d](#6d-key-security-considerations) for guidance on setting this in production.

---

## 5. How this lab authenticates the MCP connection

### The `mcp_extension` system key

The Azure Functions MCP extension generates a **system key** called `mcp_extension` after the function app first loads. This key is scoped to the MCP extension only - it is not the master function key and does not grant access to other function bindings.

Retrieve it with the Azure CLI:

```bash
az functionapp keys list \
  -g <resource-group> \
  -n <func-app-name> \
  --query "systemKeys.mcp_extension" \
  -o tsv
```

The notebook ([08-05-01-contoso-pmo-agent-setup.ipynb](08-05-01-contoso-pmo-agent-setup.ipynb)) retries this command up to 6 times (120 seconds total) while the extension initialises on first deployment.

### URL construction

The key is appended to the SSE URL as a `?code=` query parameter:

```
https://<func-app>.azurewebsites.net/runtime/webhooks/mcp/sse?code=<mcp_extension_key>
```

This full authenticated URL is passed directly to `MCPTool` as `server_url`. No separate `project_connection_id` is required in this lab setup.

### Inference-layer auth (separate concern)

This lab targets the **admin project** on the hub account, so the agent uses `DefaultAzureCredential` (Entra ID) for all model-inference calls - no APIM gateway, no shared key. The only `code=` query parameter you'll see is on the MCP SSE URL itself (the `mcp_extension` Azure Functions system key), which authenticates the **agent → MCP server** path.

The two layers and their auth:

- **Agent → model (LLM inference):** `DefaultAzureCredential` directly to admin (`project-admin-{suffix}` on `aif-core-{suffix}`).
- **Agent → MCP server (tool layer):** `mcp_extension` system key embedded in the SSE URL.

### Production note

Embedding the `mcp_extension` key directly in the `server_url` string is convenient for notebook demos. In production, store the credential in a Foundry project connection and reference it via `project_connection_id` on `MCPTool`. This keeps the credential out of source code and notebook outputs, and allows rotation without redeploying the agent. See [Section 6b](#6b-storing-credentials-in-foundry-project-connections) for details.

---

## 6. MCP authentication methods in Azure AI Foundry

### 6a. Supported authentication methods

| Method | Description | User context persists |
|---|---|---|
| **Key-based** | Provide an API key, personal access token, or other shared credential. Passed to the MCP server on every call. | No |
| **Microsoft Entra - agent identity** *(preview)* | The agent's own managed identity authenticates to the MCP server. Scoped per agent; requires role assignments on the underlying service. | No |
| **Microsoft Entra - project managed identity** *(preview)* | The Foundry project's shared managed identity authenticates to the MCP server. All agents in the project share the same access level. | No |
| **OAuth identity passthrough** | Each end user signs in and consents; their identity is used for all MCP calls. Requires `Foundry User` role on the project. | Yes |
| **Unauthenticated access** | No credential sent. Use only for public MCP servers or private servers protected by network isolation. | No |

### 6b. Storing credentials in Foundry project connections

Instead of embedding keys or URLs in code, store MCP server credentials in a **Foundry project connection** and reference the connection by name:

```python
mcp_tool = MCPTool(
    server_label='my_server',
    server_url='https://my-server.example.com/mcp/sse',
    project_connection_id='my-mcp-connection',
)
```

When the agent invokes a tool, Agent Service retrieves the credential from the project connection at invocation time and injects it into the outbound request. The credential never appears in notebook outputs or source code.

> **Security note:** Project connections are readable by anyone with access to the Foundry project. Store only shared secrets in project connections. For user-specific credentials, use OAuth identity passthrough.

### 6c. When to use each method

| Scenario | Recommended method |
|---|---|
| MCP server supports Microsoft Entra and you want zero secret management | Microsoft Entra (agent identity or project managed identity) |
| Multiple agents need different access levels on the same server | Microsoft Entra - agent identity (per-agent granularity) |
| All agents in a project need the same access level | Microsoft Entra - project managed identity |
| End-user identity or permissions must be preserved end-to-end | OAuth identity passthrough |
| MCP server only supports API key auth | Key-based |
| Public server or VNet-isolated private server with no auth requirement | Unauthenticated |

When in doubt, prefer Microsoft Entra over key-based auth. Entra tokens rotate automatically; API keys require manual rotation.

### 6d. Key security considerations

**`require_approval` setting**

The `require_approval` parameter on `MCPTool` controls whether a human must approve each tool call before it executes. It defaults to `'always'`.

| Value | Behaviour |
|---|---|
| `'always'` | Every tool call requires human approval (default) |
| `'never'` | No approval required - use only for fully trusted, private servers |
| `{"never": ["tool_a", "tool_b"]}` | Named tools bypass approval; all others require it |
| `{"always": ["tool_a", "tool_b"]}` | Named tools require approval; all others bypass it |

Set `require_approval='never'` only when the MCP server is fully trusted and private (as in this lab). For production deployments connecting to third-party or shared servers, keep the default `'always'` or use the selective list form.

**Additional considerations**

- Rotate API keys regularly; use least-privilege credentials.
- OAuth refresh tokens can expire - handle `oauth_consent_request` responses in your application and prompt users to re-consent if needed.
- The `?code=<key>` URL pattern is convenient for demos but risks key exposure in logs and notebook outputs. Use `project_connection_id` in production.
- Agent identity and project managed identity require correct role assignments on the underlying service before the agent can invoke tools - verify role propagation before testing.
