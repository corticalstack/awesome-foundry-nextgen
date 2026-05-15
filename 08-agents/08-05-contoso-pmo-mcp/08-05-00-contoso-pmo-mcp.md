# 08-05 – Contoso PMO KB MCP Server

Demonstrates building a self-hosted **37-tool custom MCP (Model Context Protocol) server** on Azure Functions backed by a JSON knowledge base, and connecting it to a Foundry agent on the **admin project** via the **versioned-agent API** (`PromptAgentDefinition` + `create_version`). The knowledge base covers projects, people, meetings, tasks, risks, documents, and distribution lists for a fictional consumer product launch environment.

```
assets/contoso-pmo-dataset/      ←── JSON knowledge base (registry + documents)
    │
    ▼
contoso-pmo-mcp/                 ←── Azure Functions app (Flex Consumption, Python)
  function_app.py               37 mcpToolTrigger wrappers
  kb.py                         Business logic (read + write operations)
  host.json                     Standard GA extension bundle [4, 5)
  data/                         Bundled knowledge base (copied at build time)
          │
          ▼ SSE endpoint: https://<func-app>.azurewebsites.net/runtime/webhooks/mcp/sse
          │
  PromptAgentDefinition     ←── tools=[{type:'mcp', require_approval:'never'}]
          │
          ▼ project_client.agents.create_version on project-admin-{suffix}
  Foundry Agent (versioned) ←── contoso-pmo-agent v1, v2, …
```

## What it does

Single-notebook deployment + agent setup ([`08-05-01-contoso-pmo-agent-setup.ipynb`](08-05-01-contoso-pmo-agent-setup.ipynb)):

| Phase | Actions |
|---|---|
| 1 – Build | Writes `host.json` and `requirements.txt`; verifies `function_app.py` and `kb.py`; bundles `assets/contoso-pmo-dataset/` into `contoso-pmo-mcp/data/` |
| 2 – Deploy | Provisions a resource group, storage account (Entra ID only), and Flex Consumption function app via `az` CLI; assigns storage roles; sets `DATA_DIR=data` |
| 3 – Package & deploy | Zips `contoso-pmo-mcp/` (including bundled knowledge base) and zip-deploys to the function app |
| 4 – Retrieve | Reads back the `mcp_extension` system key and constructs the authenticated SSE endpoint URL |
| 5 – Agent | Creates `contoso-pmo-agent` on `project-admin-{suffix}` via `project_client.agents.create_version` + `PromptAgentDefinition` with the MCP tool dict (`require_approval='never'` baked in); reuse-or-create idempotent via `list_versions` |

Two follow-on notebooks consume the agent:

| Notebook | Purpose |
|---|---|
| [`08-05-02-contoso-pmo-agent-queries.ipynb`](08-05-02-contoso-pmo-agent-queries.ipynb) | Interactive smoke-test against the deployed agent via the Responses API |
| [`08-05-03-contoso-pmo-tool-catalog.ipynb`](08-05-03-contoso-pmo-tool-catalog.ipynb) | Registers the MCP server in the Foundry Tool Catalog (separate teaching exercise) |

## Getting started

### 1. Install dependencies

```bash
uv sync
```

### 2. Authenticate

```bash
az login
```

### 3. Configure `.env`

The lab derives everything else deterministically from the active subscription. Only one var is required:

| Variable | Description |
|---|---|
| `CHAT_MODEL` | Model deployment name on the hub account (e.g. `gpt-4.1-mini`) |

Optional overrides:

| Variable | Default |
|---|---|
| `AZURE_SUBSCRIPTION_ID` | active `az` subscription |
| `CONTOSO_PMO_MCP_RESOURCE_GROUP` | `rg-foundry-contoso-pmo-mcp` |
| `CONTOSO_PMO_MCP_LOCATION` | `swedencentral` |
| `CONTOSO_PMO_FUNC_APP_NAME` | `func-contoso-pmo-mcp-{md5(sub-id+rg)[:6]}` |

The admin endpoint is `https://aif-core-{suffix}.services.ai.azure.com/api/projects/project-admin-{suffix}` — same pattern as the offline-evaluation and continuous-evaluation labs.

### 4. Run the notebooks

| Order | Notebook |
|---|---|
| 1 | [`08-05-01-contoso-pmo-agent-setup.ipynb`](08-05-01-contoso-pmo-agent-setup.ipynb) — deploy MCP server + create agent |
| 2 (optional) | [`08-05-02-contoso-pmo-agent-queries.ipynb`](08-05-02-contoso-pmo-agent-queries.ipynb) — interactive queries |
| 3 (optional) | [`08-05-03-contoso-pmo-tool-catalog.ipynb`](08-05-03-contoso-pmo-tool-catalog.ipynb) — Tool Catalog registration |

## Requirements

- Python 3.11+
- Azure CLI (`az login` with `Contributor` + `User Access Administrator` on the subscription)
- Hub estate deployed (provides `aif-core-{suffix}` + `project-admin-{suffix}` + a `CHAT_MODEL` deployment)
- **Azure AI Developer** role on the admin project

## Verification

| Step | Expected result |
|---|---|
| Imports & config | Prints `Project endpoint`, `Function app`, `Agent name`, `Chat model` |
| Phase 1 (build) | Prints sizes for `function_app.py` and `kb.py`; reports JSON files bundled |
| Phase 2 (deploy) | `✓` lines for resource group, storage, function app, all storage roles, and `DATA_DIR=data` |
| Phase 3 (package) | Prints `Zip archive` size and `✓ code deployed` |
| Phase 4 (key) | Prints `Function base URL` and `MCP SSE endpoint` |
| Phase 5 (agent) | Prints `Created agent 'contoso-pmo-agent'` (or `Reusing existing agent ...` on re-run) |

## Notes

- **Data layer:** The knowledge base consists of plain JSON files in `assets/contoso-pmo-dataset/` (registry and documents sub-directories). No database or Azure Storage is used — reads and writes go directly to the JSON files.
- **Write persistence in Azure:** Azure Functions Flex Consumption mounts the deployed zip read-only. On first write, `kb.py` lazily copies the bundled data to `/tmp/contoso-pmo-data/` and redirects all mutations there. Writes persist within the instance lifetime but are lost on cold starts — this is sufficient for demo use.
- **Standard GA extension bundle:** The `mcpToolTrigger` binding is included in the standard `Microsoft.Azure.Functions.ExtensionBundle` ([4.0.0, 5.0.0)). No beta or Experimental bundle is required.
- **Managed identity storage:** The function app uses managed identity (not shared keys) for storage authentication, following Entra ID-only best practices.
- **Keyless Foundry auth:** The agent talks to admin via `DefaultAzureCredential` — no APIM, no shared key. The only `code=` query parameter is on the MCP SSE URL itself (the `mcp_extension` Azure Functions system key), which authenticates the **agent → MCP server** path, not the **agent → model** path.
