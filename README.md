# Awesome Foundry Nextgen [![Awesome](https://awesome.re/badge.svg)](https://awesome.re)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Release](https://img.shields.io/github/v/release/corticalstack/awesome-foundry-nextgen?include_prereleases&sort=semver)](https://github.com/corticalstack/awesome-foundry-nextgen/releases)
[![Last commit](https://img.shields.io/github/last-commit/corticalstack/awesome-foundry-nextgen)](https://github.com/corticalstack/awesome-foundry-nextgen/commits)
[![Made with Jupyter](https://img.shields.io/badge/Made%20with-Jupyter-orange?logo=jupyter&logoColor=white)](https://jupyter.org/)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Azure AI Foundry](https://img.shields.io/badge/Azure-AI%20Foundry-0078D4?logo=microsoftazure&logoColor=white)](https://learn.microsoft.com/en-us/azure/ai-foundry/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

A hands-on lab series for **Microsoft Foundry NextGen** - Azure's unified PaaS for enterprise AI
operations, model builders, and application development. Each lab demonstrates a specific Foundry pattern:
provisioning, agents, MCP tools, knowledge bases, fine-tuning, guardrails, red-teaming,
observability, and more.

Foundry unifies agents, models, and tools under one Azure resource provider namespace
with built-in tracing, monitoring, evaluations, and a single RBAC/networking/policy
surface. These labs put that platform through its paces end-to-end.

![Microsoft Foundry high-level overview](docs/screenshots/foundry-high-level-overview.png)



## Prerequisites

- **Azure CLI** v2.60+ - [install](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli)
- **`cognitiveservices` CLI extension** - `az extension add -n cognitiveservices`
- **`uv`** Python package manager - [install](https://docs.astral.sh/uv/getting-started/installation/)
- Signed in: `az login`

## Quick start

```bash
git clone https://github.com/corticalstack/awesome-foundry-nextgen.git
cd awesome-foundry-nextgen
cp .env.example .env             # then fill in your values
uv sync
uv run jupyter notebook
```

Auth is **`DefaultAzureCredential`** throughout - no admin keys in notebooks.
See [`.env.example`](.env.example) for the full variable list.

## Labs

Labs are numbered roughly in dependency order - start with the conceptual overviews
(00-04), provision the platform (05-06), then pick whichever capability lab interests
you. Most capability labs assume the multi-project spoke from the [project pattern setup](05-foundry-project-pattern-setup/).

| # | Lab | What it covers |
|---|-----|----------------|
| 00 | [What is Foundry](00-what-is-foundry/) | High-level overview of Microsoft Foundry as a unified PaaS for enterprise AI. |
| 01 | [Portal - Home](01-foundry-portal-home-page/) | Tour of the Foundry (new) portal home, project switcher, and resource boundaries. |
| 02 | [Portal - Discover](02-foundry-portal-discover-page/) | The Netflix-style catalog for models and agents across providers. |
| 03 | [Portal - Build](03-foundry-portal-build-page/) | Developer control plane for agents, models, workflows, fine-tunes, and playgrounds. Includes creating a project and deploying/testing models. |
| 04 | [Control plane](04-foundry-control-plane/) | Operating a fleet of agents - provisioning, regions, SDKs, costs, custom-agent registration, publishing, the VS Code extension. |
| 05 | [Project pattern setup](05-foundry-project-pattern-setup/) | Hub/spoke architecture with Bicep: deploy the core gateway, a single-project spoke, and a multi-project spoke. |
| 06 | [Governance policy](06-governance-policy/) | Azure Policy that denies model deployments in spokes, forcing all traffic through the core APIM gateway. |
| 07 | [Model inference](07-model-inference/) | Inference paths behind APIM - Azure OpenAI vs Foundry project clients, chat/embeddings/responses, server-side router, deep-research, streaming. |
| 08 | [Agents](08-agents/) | Agent fundamentals across nine sub-labs: versioned agents, code interpreter, hosted agents, memory, MCP (PMO + private banking), offline eval, live observability, human-in-the-loop. |
| 09 | [Content Understanding integration](09-content-understanding-integration/) | Plumb Azure AI Content Understanding behind the core APIM with managed-identity backend auth. |
| 10 | [Foundry IQ](10-foundry-iq/) | Managed knowledge base end-to-end: provision Azure AI Search, ingest 3k arXiv NLP papers, build a KB, ground an agent. |
| 11 | [Foundry IQ - multi-agent](11-foundry-iq-multi-agent/) | Router + specialist pattern over three KBs (HR, Marketing, Products) using Microsoft Agent Framework `WorkflowBuilder`. |
| 12 | [Foundry IQ - deep research](12-foundry-iq-deep-research/) | `o3-deep-research` agentic loop over the arxiv-nlp KB with cited synthesis by `gpt-4.1-mini`. |
| 13 | [Guardrails](13-guardrails/) | Three-layer guardrails (Prompt Shields, PII detection, custom blocklist) stacked on a bank customer-service agent. |
| 14 | [Red teaming](14-red-teaming/) | Basic and advanced AI Red Teaming Agent (PyRIT) scans against a Foundry project. |
| 15 | [Fine-tune](15-fine-tune/) | Knowledge distillation from a `gpt-4.1-mini` teacher to a `Phi-4-mini` student via Olive + PEFT (LoRA). |

### Agents sub-labs

The agents lab is large enough to warrant its own breakdown:

| # | Sub-lab | What it covers |
|---|---------|----------------|
| 08-01 | [Versioned storytelling agent](08-agents/08-01-create-versioned-storytelling-agent.ipynb) | Create a versioned agent and iterate on its definition. |
| 08-01b | [Versioned Contoso wealth agent](08-agents/08-01b-create-versioned-contoso-wealth-agent.ipynb) | Versioning applied to a domain-specific wealth-advisory agent. |
| 08-02 | [Code interpreter tool](08-agents/08-02-create-agent-with-code-interpreter-tool.ipynb) | Attach the Code Interpreter tool to an agent. |
| 08-03 | [Hosted agents](08-agents/08-03-hosted-agents/) | Deploy a hosted (containerised) agent backed by ACR. |
| 08-04 | [Agent memory](08-agents/08-04-agent-memory/) | Add Foundry agent memory for cross-turn context. |
| 08-05 | [MCP - Contoso PMO](08-agents/08-05-contoso-pmo-mcp/) | Custom MCP server with a tool catalog for a project-management scenario. |
| 08-05b | [MCP - Contoso private banking](08-agents/08-05b-contoso-private-banking-mcp/) | Second MCP scenario, intent-over-endpoint tool design. |
| 08-06 | [Offline evaluation](08-agents/08-06-agent-offline-evaluation/) | Quality, agent-specific, and custom evaluators run against a test set. |
| 08-07 | [Live observability](08-agents/08-07-agent-live-observability/) | Tracing, real-time observability, and continuous evaluation in production. |
| 08-08 | [Human in the loop](08-agents/08-08-human-in-the-loop/) | Pause an agent run for human approval before sensitive tool calls. |

## Repository layout

```
├── 00-what-is-foundry/ … 15-fine-tune/   # Lab content (notebooks + Bicep)
├── assets/                               # Shared images, data, prompts
├── docs/screenshots/                     # Portal/architecture screenshots
├── scripts/                              # Notebook builders, helpers
├── .env.example                          # Variable template
└── CONTRIBUTING.md                       # How to contribute
```

## Contributing

Issues, lab additions, and fixes are very welcome - see [CONTRIBUTING.md](CONTRIBUTING.md)
for branching, lab numbering, and PR checklist.
