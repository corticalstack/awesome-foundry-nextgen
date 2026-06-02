# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.8.12] - 2026-06-01

A new `08-agents` lab: the 08-10 Copilot SDK container rehosted on the shared 1:N multi account, taking its inference from the APIM core gateway.

### Added

- New `08-agents/08-10b-hosted-copilot-sdk-agent-multi` section: the "B" variant of 08-10 that rehosts the **identical** Copilot SDK container on the existing shared `aif-spoke-multi` (1:N) account from 05-04, with inference from the APIM core gateway instead of a local model deployment. The lab is **self-contained** - it ships its own copy of the container source (`src/github-copilot-invocations/`) and demo data (`data/`), with no dependency on 08-10. The `08-10b-01` notebook mints a dedicated `foundry-gateway-copilot-sdk` APIM subscription, deploys a `gpt-5-mini` reasoning model on the gateway backend (`aif-core`), deploys the project + ACR Bicep, enables the account-level capability host (idempotent REST `PUT`), builds the agent image, registers + role-grants the hosted agent in APIM-direct mode, then runs the smoke tests and the M365 analytics demo.
- 08-10b points the Copilot SDK container **directly at the APIM gateway** (`base_url = <apim>/openai`, the subscription key in the `api-key` header, bare reasoning model `gpt-5-mini`), bypassing the Foundry project connection. Reason: Foundry's connection model-gateway (bring-your-own-model via an `ApiManagement` connection) is [supported only for *prompt* agents](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/ai-gateway) - a hosted agent calling the Responses API through a `connection/deployment` model string forwards the qualified name upstream and fails with `DeploymentNotFound`. A *reasoning* model is required because the Copilot CLI's Responses protocol carries encrypted reasoning content (`gpt-4.1-mini` returns `Encrypted content is not supported`). `main.py` gained an additive, env-driven APIM-direct branch (active only when `APIM_BASE_URL` + `APIM_KEY` are set); the standalone 08-10 path is unaffected. The reasoning model is deployed on the core account (`aif-core`), so `rg-foundry-multi`'s `deny-model-deployments` policy is untouched; agent RBAC is AcrPull + Foundry User only (the gateway key, not the managed identity, pays for inference). Tradeoff: the gateway key lives in the container env var (Key Vault connection or managed-identity-to-APIM noted as hardening).
- `08-10b-00` documentation: the 1:N governance framing and the why-direct-not-connection rationale (with the prompt-agents-only citation, the reasoning-model requirement, and the api-key-in-env tradeoff).

### Changed

- README `08-agents` sub-lab table: added a row for `08-10b`.

## [0.8.11] - 2026-05-30

Two new `08-agents` labs: invoking a Foundry agent over raw REST, and deploying a GitHub Copilot SDK agent as a Foundry hosted agent.

### Added

- New `08-agents/08-09-invoke-agent-via-rest` section: three notebooks that invoke a Foundry agent over raw REST (the responses API) instead of the SDK - `08-09-01-rest-single-shot`, `08-09-02-rest-multi-turn`, and `08-09-03-rest-streaming` - plus an `08-09-00` overview. Closes the gap where the repo only demonstrated agent consumption through the SDK.
- New `08-agents/08-10-hosted-copilot-sdk-agent` section: deploys a GitHub Copilot SDK agent (`CopilotClient` plus the `azure-ai-agentserver-invocations` protocol) as a Microsoft Foundry hosted agent. The `08-10-01` notebook walks Bicep (`az deployment sub create`), `az acr build`, and `AIProjectClient.agents.create_version`, with a two-pass register and bootstrap-version delete, runtime role grants on the per-agent managed identity (AgentIdentity), a smoke test, and an M365 license-analytics demo.
- BYOK Foundry model path in 08-10: the Copilot SDK routes inference to a Foundry-deployed `gpt-5.4-mini` over the project endpoint (`<project>/openai/v1/`, token audience `ai.azure.com`) via Managed Identity, with a `GITHUB_TOKEN` Copilot-model fallback.
- M365 license-analytics demo (Step 7) with markdown tables rendered inline (a new `render=True` mode on the notebook's `invoke()` helper) and an agent-generated, downloadable cost-by-department chart: the agent renders the chart (matplotlib, pip-installed into its own session shell, with a dependency-free SVG fallback) into the session sandbox, and the notebook retrieves it with a new `download_session_file()` helper (the read counterpart to `upload_session_file()`).
- `08-10-00` documentation covering the two-layer agentic loop (the outer Foundry-protocol shell in `main.py` versus the inner Copilot CLI reason/act/observe loop), the BYOK wiring, and the agent permission model (`PermissionHandler.approve_all` as the yolo-equivalent, a four-layer "what the agent is allowed to do" table, and tool-call observability).
- OpenTelemetry tracing (`tracing.py`) mapping Copilot `SessionEvent`s to GenAI-semantic-convention spans (`invoke_agent` parent with `execute_tool` and `chat <model>` children), surfaced in the Foundry portal Tracing tab.

### Changed

- `pyproject.toml`: bumped `azure-ai-projects` from `>=2.0.0b1` to `>=2.1.0` (required for the hosted-agent `agents.create_version` API used by section 08-10).

### Removed

- `pyproject.toml`: dropped the unused `azure-ai-inference>=1.0.0` from the `finetune` dependency group. It had zero usages in the repo and its `>=1.0.0` floor conflicted with `agent-framework-azure-ai`'s `<1.0.0b10` pin, blocking `uv lock`.
- Deleted an accidentally-committed upstream `.git` directory and azd scaffolding (azure.yaml, agent.yaml, git hook samples, pack files) from the old `08-agents/08-09` path.

## [0.8.10] - 2026-05-27

End-to-end fixes for the section 15 fine-tuning pipeline. The pipeline failed at multiple points; this release fixes them in sequence.

### Fixed

- `15-fine-tune/15-01-data-preparation.ipynb` failed at cell 3 with `ModuleNotFoundError: No module named 'torch'`. Two underlying issues: (1) `torch`, `transformers`, `peft`, `matplotlib`, `azure-storage-blob`, and `azure-ai-inference` were never declared in `pyproject.toml`, and (2) cell 2's inline `%pip install` silently failed in the uv-managed `.venv` (which doesn't ship `pip`, so `%pip` prints `No module named pip`). Same import-failure pattern would have hit `15-04-local-inference.ipynb`, which depends on torch/transformers/peft but had no install cell at all.
- `15-fine-tune/15-01-data-preparation.ipynb` cell 8 then failed with `OpenAIError: Missing credentials` because `FINETUNE_GATEWAY_KEY` was missing from `.env`. The Bicep at `15-fine-tune/main.bicep` does not create a dedicated `foundry-gateway-finetune` APIM subscription (unlike 10-01 / 11-01 which provision their own), so this env var was never going to be set. The teacher-model call only needs any valid APIM key, so the cell now reuses `ALPHA_GATEWAY_KEY` (already in `.env` from the project-spoke deployment). This removes a phantom env variable and one redundant Azure resource.
- `15-fine-tune/15-02-fine-tune.ipynb` ACA job failed with `The specified resource name length is not within the permissible limits`. Container name `"ft"` violated Azure Storage's 3-63 character minimum. The container creation silently failed (because the helper used `check=False`), then the in-job blob download from `"ft"` errored visibly. Renamed to `"finetune"` in 15-02 / 15-03 / 15-04 cell-3 constants and in `15-fine-tune/main.bicep` (which had the same bug). `azure_infra.py` takes the name as a parameter so no source change there.
- `15-fine-tune/15-03-evaluate.ipynb` raised `NameError: name 'eval_dataset' is not defined` when run in a fresh kernel. It implicitly relied on `eval_dataset` / `reports_data` / `env_id` / `accuracy` being in memory from 15-01 + 15-02. Cell 3 now re-derives all four: `eval_dataset` via `iss_utils.get_evaluation_dataset()`, `reports_data` via NASA fetch (~30s), `env_id` via `az containerapp env show`, and fallback teacher/base accuracies with comments explaining how to override. Also added `import pandas as pd` and `from IPython.display import display` to the imports cell (previously caused `NameError: pd not defined` in the comparison cell) and fixed an outdated `"DeepSeek-V3.2 (Teacher)"` label in the summary table to match the actual teacher (`gpt-4.1-mini`) used throughout the chain.
- `15-fine-tune/15-04-local-inference.ipynb` failed with `ImportError: cannot import name 'LossKwargs' from transformers.utils`. Phi-4-mini's custom remote modeling code (`modeling_phi3.py` from the Hugging Face hub) imports symbols (`LossKwargs`, etc.) that were removed in transformers 5.x. The `[finetune]` dep group's `transformers>=4.40.0` constraint allowed 5.x to be pulled in. Tightened to `>=4.46.0,<5.0.0` with a comment explaining the upper bound; matches the `transformers==4.53.3` pin the ACA fine-tune job uses inline.
- `15-fine-tune/15-04-local-inference.ipynb` `generate()` emitted a "The attention mask is not set and cannot be inferred" warning because `apply_chat_template` returned just the input_ids tensor and Phi-4-mini has `pad_token == eos_token`. Reworked to use `apply_chat_template(..., return_dict=True)` and pass `**inputs` to `generate()` so both `input_ids` and `attention_mask` are present.

### Added

- New `[dependency-groups] finetune` entry in `pyproject.toml` declaring the heavy ML dependencies needed for section 15 (`torch>=2.0.0`, `transformers>=4.46.0,<5.0.0`, `peft>=0.10.0`, `matplotlib>=3.7.0`, `azure-storage-blob>=12.20.0`, `azure-ai-inference>=1.0.0`). Users run `uv sync --group finetune` once before opening section 15. Base install stays lean for everyone else (~3 GB saved when section 15 isn't needed). Matches the pattern used for `azure-ai-evaluation[redteam]` in section 14.
- Committed `15-fine-tune/data/train.jsonl` (100-example synthetic+real distillation training set generated against the gpt-4.1-mini teacher). Useful as a fixed artifact so 15-02 can be re-run without regenerating the data (saves ~200 teacher calls), and readers can inspect what the LoRA trains on. The `15-fine-tune/data/` directory remains gitignored - `train.jsonl` is tracked explicitly via `git add -f`.
- New entries in `.gitignore` for section 15 artifacts that should not be committed by accident: `15-fine-tune/data/` (regenerable training JSONL), `15-fine-tune/models/` (~350MB of LoRA adapter weights), `15-fine-tune/eval_job.json` and `15-fine-tune/job.json` (contain real subscription IDs when written by local runs).

### Changed

- Cell 2 of `15-01-data-preparation.ipynb` converted from a broken `%pip install` code cell to a markdown cell that points readers at the `uv sync --group finetune` command and explains why `%pip` doesn't work in this venv.
- Updated `15-00-fine-tune.md` prerequisites: step 4 now specifies `uv sync --group finetune`, with a note explaining what the group includes and why the base install was kept lean. Step 2's `.env` block now references `ALPHA_GATEWAY_KEY` (no separate `FINETUNE_GATEWAY_KEY`), step 5's `az deployment` command uses `$ALPHA_GATEWAY_KEY` as `apimSubscriptionKey`. A note above the block explains the rationale.
- Reduced default `TARGET_TOTAL` in `15-01-data-preparation.ipynb` from 500 to 100 (demo-sized, ~200 teacher calls), with a rationale block above the constant and an expanded markdown header pointing readers at the literature's 500-2000 sweet spot for narrow classification distillation and noting that cost / runtime scale linearly with the knob.

## [0.8.9] - 2026-05-27

### Added

- New [14-00-red-teaming.md](14-red-teaming/14-00-red-teaming.md) section overview: introduces the AI Red Teaming Agent (PyRIT), the region constraint, the two notebooks, the callback/APIM architecture, and links to the official Microsoft docs + PyRIT GitHub. Brings section 14 in line with every other section's `NN-00-*` intro page.
- Committed PyRIT scan output artifacts (`14-red-teaming/redteam_basic_output/` and `14-red-teaming/redteam_advanced_output/{strategies,multilang,custom}/`) so readers can see what the scans produce without running them. ~110KB total, no tenant identifiers.
- Added `14-red-teaming/custom_attack_prompts.json` as the source-of-truth seed file for the custom-objectives scan.
- Re-added the `[redteam]` extra to `azure-ai-evaluation` in `pyproject.toml` (pulls in PyRIT for section 14).

### Changed

- Renamed PyRIT `scan_name` arguments from the legacy `Lab16-*` form to descriptive `redteam-*` names (escaped the 0.8.0 "Lab N" cleanup): `Lab16-Basic` → `redteam-basic` in `14-01-red-team-basics.ipynb`; `Lab16-Advanced/MultiLang/Custom` → `redteam-advanced/multilang/custom` in `14-02-red-team-advanced.ipynb`. Updated in source cells and in cached outputs / committed scan JSON.
- Refreshed cached outputs in `13-02-create-bank-agent.ipynb` and `13-03-demo-guardrails.ipynb` from runs against the now-fixed `customBlocklists`-empty policy. Confirms the bank agent + 13-03 demo run cleanly via the agent_reference / Responses API path.

### Fixed

- Scrubbed absolute local paths (`/home/jp/...`) from cached outputs and stack traces in `14-01-red-team-basics.ipynb` (6 occurrences) and `14-02-red-team-advanced.ipynb` (80 occurrences), replaced with `<repo-root>` and `<uv-python>` placeholders per the notebook-output hygiene policy in `CONTRIBUTING.md`.

## [0.8.8] - 2026-05-27

### Fixed

- `13-guardrails/13-02-create-bank-agent.ipynb` (and the demo runner in `13-03`) returned `InternalServerError: 500` on every Responses API call. Root cause empirically isolated: when ANY `customBlocklists` entry is attached to the RAI policy (Prompt-side, Completion-side, or both), the Responses API runtime returns 500 on happy-path content while still correctly returning 400 `content_filter` on blocked content. Same policy works fine through Chat Completions. This is the service-side analogue of the Java SDK array-shape issue [#49196](https://github.com/Azure/azure-sdk-for-java/issues/49196).
- Fix applied in `13-01-configure-bank-guardrails.ipynb`: `customBlocklists` is now an empty list. The `bank-demo-blocklist` resource is still created (so it shows in the portal and can be re-attached with two lines once the service bug is fixed), but the attachment to the policy is removed. Standard content filters and Prompt Shields (Jailbreak / Indirect Attack / Protected Material) still work via the Responses API path used by all the other agent notebooks in this repo.

### Changed

- Updated the descriptions in `13-00-guardrails.md`, the top markdown of `13-01`, the architecture diagram, the portal-fallback steps, and `13-03-demo-guardrails.ipynb` to reflect the temporary limitation: PII-regex and custom-blocklist scenarios (codenames, competitors) will not block until the Responses API bug is fixed; Prompt Shields and standard filters continue to work.
- Added a detailed comment on the RAI policy cell in `13-01` explaining the bug, the empirical evidence, the workaround, and how to re-enable when Microsoft fixes the service.

## [0.8.7] - 2026-05-27

### Fixed

- `13-guardrails/13-00-guardrails.md` portal-fallback section referenced a hard-coded resource name `aif-core-6fe574`. Users following the doc against their own deployment will have a different suffix. Replaced with `aif-core-{suffix}` to match the placeholder convention used everywhere else in prose.

### Changed

- Normalised a stale older deployment suffix `6fe574` to the current canonical demonstration suffix `c2676f` across cached notebook outputs in `09-content-understanding-integration/09-01-deploy-setup.ipynb` (11 occurrences), `09-content-understanding-integration/09-02-cu-analyze.ipynb` (2), and `10-foundry-iq/10-03-knowledge-base-setup.ipynb` (2). The two suffixes co-existed in different files because the cached outputs were captured from two different deployment generations; readers now see a single consistent suffix.

## [0.8.6] - 2026-05-27

Tenant-identifier scrub of cached notebook outputs across sections 08 and 12, plus refreshed cached outputs for the deep-research notebooks.

### Changed

- Scrubbed nine tenant-specific UUIDs from cached notebook outputs to the conventional `00000000-0000-0000-0000-000000000000` placeholder. Per the notebook-output hygiene policy in `CONTRIBUTING.md`: deterministic resource-name suffixes (`c2676f`, `n5d3ja`) are kept; subscription IDs, Entra principal IDs, project managed-identity principals, eval-run IDs, and ACR build volume IDs are scrubbed.
  - `08-agents/08-03-hosted-agents/08-03-01-deploy-hosted-agent.ipynb` - Entra principal ID + ACR build volume ID
  - `08-agents/08-05-contoso-pmo-mcp/08-05-01-contoso-pmo-agent-setup.ipynb` - project MI principal
  - `08-agents/08-05b-contoso-private-banking-mcp/08-05b-01-private-banking-agent-setup.ipynb` - project MI principal
  - `08-agents/08-06-agent-offline-evaluation/08-06-05-results-and-portal.ipynb` - two eval-run IDs in portal URLs
  - `08-agents/08-07-agent-live-observability/08-07-01-deploy-observability-infra.ipynb` - Entra principal ID
  - `12-foundry-iq-deep-research/12-01-deploy-o3-backend.ipynb` - subscription ID + Entra principal ID
- Refreshed cached outputs in `12-foundry-iq-deep-research/12-01-deploy-o3-backend.ipynb` and `12-foundry-iq-deep-research/12-02-deep-research-loop.ipynb` from a successful end-to-end run after the v0.8.4 / v0.8.5 fixes landed.

### Kept (false positive flagged for completeness)

- `08-agents/08-03-hosted-agents/08-03-01-deploy-hosted-agent.ipynb` references `53ca6127-db72-4b80-b1b0-d745d6d5456d` as `FOUNDRY_USER_ROLE_ID`. This is the public Azure built-in role-definition ID for "Foundry User", identical across all Azure tenants - not personal data.

## [0.8.5] - 2026-05-27

### Fixed

- Raised the `o3-deep-research` model deployment capacity from 10 (10K TPM) to 200 (200K TPM) in both `05-foundry-project-pattern-setup/05-02-deploy-foundry-core-gateway/main.bicep` and `12-foundry-iq-deep-research/main.bicep`. The original 10K cap throttled multi-step deep-research runs with 429 errors before completion. 200K stays well under the Norway East `o3-DeepResearch` subscription quota (3000). Existing live deployments must be updated separately (`az cognitiveservices account deployment update --sku-capacity 200`) or via a fresh Bicep apply.

## [0.8.4] - 2026-05-27

### Fixed

- `12-foundry-iq-deep-research/12-01-deploy-o3-backend.ipynb` failed on Step 5 with `'subscription' is misspelled or not recognized` because it used `az apim subscription list-secrets`, which requires the `apim` Azure CLI extension. Same issue affected Step 3's `az apim backend show`. Both calls rewritten to use `az rest` against the ARM management endpoint, matching the pattern already used by `10-01-deploy-search-and-project.ipynb` and `11-01-deploy-setup.ipynb`. Step 2 now also resolves `SUB_ID` and an `APIM_BASE_URI` helper used by Steps 3 and 5. No new dependencies; works with the base Azure CLI.

## [0.8.3] - 2026-05-27

Two leftovers from prior cleanup passes: residual "Lab N" pointers in repo-root files, and a repo-wide em/en dash sweep that had never been done.

### Changed

- Removed remaining `Lab N` cross-references from `README.md` (line 48 "Lab 05" → "project pattern setup", line 69 "Lab 08 sub-labs" → "Agents sub-labs") and the `.github/ISSUE_TEMPLATE/lab_proposal.md` example. The `Lab` column header in the README labs table is kept since it is a concept noun, not a section pointer.
- Replaced every em dash (`—`) and en dash (`–`) with a single hyphen across 22 prose files: `README.md`, `CONTRIBUTING.md`, `SECURITY.md`, `.github/` templates, `04-01-foundry-enterprise-provisioning.md`, and 17 notebooks (markdown cells + cached cell outputs only - code cell sources left untouched to avoid altering string-literal behaviour). 139 character replacements in total. Per `CLAUDE.md` writing style: single hyphen only.

### Skipped (intentional)

- Simulated dataset JSON under `assets/contoso-*-dataset/` and `08-agents/08-05*/contoso-*-mcp/data/`: dashes there are authentic punctuation in mock meeting notes / research reports and removing them changes the dataset's character.
- `CHANGELOG.md`: historical release notes preserved as published.

## [0.8.2] - 2026-05-27

Repo-wide file-naming sweep: brought six off-convention files into the `NN-MM-NN-slug` pattern used by sibling sub-folders and updated all inbound cross-references.

### Changed

- Renamed five notebooks and one markdown stub:
  - `05-foundry-project-pattern-setup/05-02-deploy-foundry-core-gateway/deploy-foundry-core-gateway.ipynb` → `05-02-01-deploy-foundry-core-gateway.ipynb`
  - `05-foundry-project-pattern-setup/05-03-deploy-foundry-project-spoke/deploy-foundry-project-spoke.ipynb` → `05-03-01-deploy-foundry-project-spoke.ipynb`
  - `05-foundry-project-pattern-setup/05-04-deploy-foundry-multi-project/deploy-foundry-multi-project.ipynb` → `05-04-01-deploy-foundry-multi-project.ipynb`
  - `08-agents/08-03-hosted-agents/deploy-hosted-agent.ipynb` → `08-03-01-deploy-hosted-agent.ipynb`
  - `08-agents/08-04-agent-memory/deploy.ipynb` → `08-04-01-deploy-agent-memory.ipynb`
  - `08-agents/08-05-contoso-pmo-mcp/mcp-authentication-methods.md` → `08-05-04-mcp-authentication-methods.md`
- Updated all inbound cross-references: `04-00-control-plane.md` (2 links), `05-00-project-setup.md` (3 links), `05-01-architecture.md` (1 link), `08-03-00-hosted-agents.md` (2 links), `13-01-configure-bank-guardrails.ipynb` (2 links), `11-01-deploy-setup.ipynb` (1 prose mention), and `10-01-deploy-search-and-project.ipynb` (1 prose mention).

## [0.8.1] - 2026-05-27

Section 08 HITL lab cleanup: notebook rename, agent rename, and corrected guidance on MAF / Foundry approval mechanisms.

### Changed

- Renamed `08-agents/08-08-human-in-the-loop/hitl.ipynb` to `08-08-01-human-in-the-loop.ipynb` to match the `NN-MM-NN-slug` convention used by sibling sub-folders. Updated inbound references in `08-agents/08-00-what-is-an-agent.md` and the cross-reference in `08-agents/08-05b-contoso-private-banking-mcp/08-05b-02-private-banking-agent-queries.ipynb`.
- Renamed the demo agent from `08-06-hitl-agent` (wrong chapter prefix) to `payments-approval-agent`, matching the descriptive `{domain}-{role}-agent` naming used elsewhere in section 08.
- Replaced the "Future: MAF `approval_mode`" section in both the notebook and the overview with a "Related patterns" section that explains the three approval layers (MAF `@tool(approval_mode=...)`, Foundry `MCPTool(require_approval=...)`, manual interception) and when each applies.

### Fixed

- The MAF `approval_mode` guidance said "is developing" / "not yet available in published pip package". The feature has shipped in `agent-framework-core==1.0.0rc6` (the version this repo pins) and the decorator name in that release is `@tool`, not `@ai_function`. Text updated to reflect released status and corrected decorator name.
- The `extra_body` code sample in section 4 of the overview used the wrong key (`agent` instead of `agent_reference`), which would have failed if copy-pasted. Fixed both occurrences to match the working pattern in the notebook.

## [0.8.0] - 2026-05-22

Sections 13 (guardrails), 14 (red teaming), and 15 (fine-tuning) cleanup. This completes the systematic documentation pass over every section (00-15).

### Changed

- Cleaned up section 13 (guardrails), section 14 (red teaming), and section 15 (fine-tuning): sentence-case headings aligned with filenames and dropped `Lab NN` title prefixes.
- Replaced brittle `Lab N` cross-references with stable capability names (core gateway / project spoke deployments, the basic scan), keeping the correct link targets.
- RBAC role rename `Azure AI User` to `Foundry User` in notebook prose and Bicep comments.
- Scrubbed the real subscription ID from a guardrails notebook output to a placeholder.
- Added Next-page navigation links to the section overviews. The generated ARM template (`14-red-teaming/main.json`) was left untouched.

## [0.7.0] - 2026-05-22

The Foundry IQ family (sections 10-12) cleanup: single-agent IQ, multi-agent IQ, and deep research.

### Changed

- Cleaned up section 10 (Foundry IQ), section 11 (Foundry IQ multi-agent), and section 12 (Foundry IQ deep research) across overviews, notebooks, helper modules, Bicep, sample data, and tests: sentence-case headings aligned with filenames, dropped `Lab NN` title prefixes, and removed bare notebook section numbering.
- Replaced brittle `Lab N` cross-references with stable capability names throughout (core gateway / multi-project deployments, Foundry IQ, deploy steps), including the inconsistent `Lab 5C` / `Lab 1C` naming for the multi-project deployment and a wrong `Lab 04-05` label in Bicep.
- RBAC role rename `Azure AI User` to `Foundry User` in Bicep comments (role assignments already use role-definition IDs).
- Scrubbed environment identifiers from notebook outputs (subscription IDs, Entra principal/object IDs, local home paths) to placeholders, while keeping demonstration outputs and model-generated answers verbatim.
- Added Next-page navigation links to the three overviews.

## [0.6.0] - 2026-05-22

Section 09 (content understanding integration) cleanup.

### Changed

- Cleaned up section 09 across the overview, both notebooks, and the three Bicep files: sentence-case headings aligned with filenames, `Lab N` cross-references replaced with stable capability names, and a Next-page navigation link added.
- Scrubbed environment identifiers from the deploy-setup notebook outputs (subscription ID, Entra principal/object ID, APIM managed-identity object ID, and a local home path) to placeholders.

### Fixed

- Corrected the overview H1, which was mislabelled "08" (this is section 09), and dropped a wrong "Lab 10" label in the Bicep comments.
- Renamed `09-00-content-understanding-integation.md` to `09-00-content-understanding-integration.md` (filename typo; no inbound references).

## [0.5.1] - 2026-05-22

### Fixed

- Corrected a wrong-number cross-section reference in 07-01: the `.env` prerequisite pointed at `04-foundry-project-pattern-setup`, but the project pattern setup is section 05 (section 04 is the control plane). A word-boundary-guarded repo-wide audit confirmed this was the only genuine instance; other apparent matches were substrings of valid `NN-MM-slug` filenames.

## [0.5.0] - 2026-05-22

Section 08 (agents) cleanup - the largest section: versioned agents, code interpreter, hosted agents, agent memory, two MCP servers, offline evaluation, live observability, and human-in-the-loop.

### Changed

- Cleaned up all of section 08 across markdown, notebooks, Bicep, function apps, and helper modules: sentence-case headings aligned with filenames, demoted stray section-divider H1s to H2, and dropped broken/inconsistent section numbering from notebook headings. Numbered reference docs whose in-page tables of contents depend on the anchors kept their structure.
- Replaced brittle `Lab N` cross-references with stable capability names throughout.
- RBAC role rename `Azure AI User` to `Foundry User` in prose and Bicep comments. The one executable role assignment now uses the stable role-definition ID; the memory and observability Bicep already assigned by ID.
- Added the missing 08-05 and 08-05b rows to the section index.
- Scrubbed environment identifiers from committed notebook outputs and one generated data file (subscription IDs, Entra principal/object IDs, local home paths) to placeholders, while keeping demonstration outputs, synthetic example IDs, and model-generated agent answers verbatim.

### Fixed

- Corrected wrong-number titles and references: the tool-catalog notebook titled "Lab 09", the human-in-the-loop notebook titled "08-06" and its overview "08-07", and six notebooks that pointed at `04-foundry-project-pattern-setup` (the project pattern setup is section 05).
- Removed two links to a workshop-agenda document that is not present in the repository.

## [0.4.0] - 2026-05-22

Sections 06 (governance policy) and 07 (model inference) cleanup.

### Changed

- Cleaned up section 06 (governance policy) and section 07 (model inference) across both the markdown index pages and the notebooks: sentence-case headings aligned with filenames, "Directory Contents" renamed to "In this chapter", and Next-page navigation links added.
- Replaced brittle `Lab N` cross-references with stable capability names (core gateway / project spoke / multi-project deployments).
- Dropped an inconsistent numbered-section run in the model-inference notebook (un-numbered sections had broken the sequence).
- Scrubbed the real subscription ID from the governance-policy notebook outputs to a placeholder, while keeping the demonstration outputs and synthetic example IDs.

## [0.3.0] - 2026-05-22

Section 05 (project pattern setup) cleanup, plus repo-wide secret-scanning tooling.

### Added

- gitleaks pre-commit hook (`.pre-commit-config.yaml` + `.gitleaks.toml`) with a custom, context-scoped Azure subscription-ID rule on top of the default secret rules. Runs via Docker on staged changes only.
- Notebook output hygiene policy in `CONTRIBUTING.md`: keep outputs but scrub environment identifiers, plus local-setup steps and PR-checklist items.
- Next-page navigation links through section 05 (05-00 to 05-01 to 05-02).

### Changed

- Cleaned up section 05 across all files (05-00 through 05-04, both notebooks and Bicep): sentence-case headings aligned with filenames, with vestigial section numbering removed.
- Updated Foundry RBAC role names to the current naming (Foundry User / Project Manager / Account Owner / Owner) with a rename note and cross-reference to 04-01.
- Replaced brittle `Lab N` cross-references with stable capability names (Foundry IQ, Foundry IQ Multi-Agent, Contoso PMO KB, Agent Observability, Content Understanding, Memory API). This also corrected several that pointed at the wrong section (for example "Lab 09 Foundry IQ Multi-Agent" is actually section 11; "Lab 07-05 Agent Observability" is 08-07).
- Scrubbed environment identifiers from committed notebook outputs (subscription IDs, Entra principal/object IDs, local home paths) to placeholders, while keeping the demonstration outputs and the deterministic resource-name suffix.

### Fixed

- Architecture diagram (05-01): removed dead `H2`/`H4` node references from the mermaid `class` statement that broke stricter renderers.
- Corrected a wrong governance-policy notebook path in 05-01 (`06-01-deploy-governance-policy.ipynb`).

## [0.2.0] - 2026-05-20

Documentation pass over chapters 00-04 to improve consistency, navigability, and accuracy.

### Added

- Next-page navigation links across the entire reading flow (00 → 01 → 02 → 03 → 04), and through every chapter 04 subpage.
- "What is a control plane?" intro section in 04-00 for readers unfamiliar with the term.
- Side-by-side comparison table for the four built-in Foundry RBAC roles in 04-01, with a separate role-definition-ID lookup table.
- Cross-references from every page that mentions RBAC roles back to the canonical definitions in 04-01.
- Disclaimer and placeholder reference table in 04-09 so deep-link templates are usable from any reader's deployment.

### Changed

- Aligned H1/H2 sentence-case headings with filename slugs across all chapter index pages and chapter 04 subpages. Proper nouns and acronyms preserved.
- Updated Foundry RBAC role names from the legacy `Azure AI X` form to the current `Foundry X` form (User, Owner, Account Owner, Project Manager) to match Microsoft's recent platform-wide rename.
- Restructured 04-00 control-plane page: dropped opaque "Section 5X" numbering and reordered reference sections to match the four-pillar narrative.
- Restructured 04-04 cost page: introduced a proper H1, demoted stale `#` section dividers to `##`, folded orphan intro prose into a coherent intro paragraph.
- Consolidated "Related Resources" sections across chapter 04 into "Resources" with a uniform shape (primary-source link folded in as the first bullet).
- Bumped SDK package versions in 04-03 to current registry releases: Python `azure-ai-projects` 2.1.0 stable, JS `@azure/ai-projects` 2.1.1 stable, .NET `Azure.AI.Projects` 2.0.1 stable (`Azure.AI.Projects.OpenAI` 2.0.0-beta.1 preview), Java `azure-ai-projects` 2.1.0-beta.1.
- Templated 04-09 cheat sheet URLs: replaced personal deployment IDs with placeholder markers (`{tenant}`, `{rg}`, `{resource}`, `{project}`, etc.).
- Updated 04-02 to link to canonical sources: Azure OpenAI model availability list and Azure OpenAI quota increase request form.

### Renamed

- `04-foundry-control-plane/04-06-publish-agents.md` → `04-06-publish-agents-teams-m365-copilot.md` to reflect the file's scope. Cross-references in 04-00 and 04-05 updated.

### Fixed

- Multiple broken or stale Microsoft Learn URLs across chapter 04 Resources sections (`?view=foundry-classic` URLs that resolve to classic-only content; 404s removed).
- Locale-missing Pricing reference URLs in 04-04 (`/pricing/details/search/` and `/pricing/calculator/`) - added the `/en-us/` segment so they resolve directly.
- Broken `main.ipynb` link in 04-00 Related examples (replaced with the existing `14-01-red-team-basics.ipynb`).
- Typo `tooll` → `tool` in 04-09 cheat sheet.

### Removed

- Deprecated Prompt Flow / Azure ML compute row from the 04-04 Storage and compute table.
- Classic-only Microsoft Learn articles from 04-01 Resources (the three articles that explicitly state "applies only to Foundry classic portal").

## [0.1.0] — 2026-05-15

Initial public release of the **Awesome Foundry Nextgen** lab series.

### Added

- 16 hands-on labs covering Microsoft Foundry end-to-end:
  - **00–04** — Foundry concepts, portal tour (Home, Discover, Build), and the
    control plane.
  - **05** — Hub/spoke project pattern setup with Bicep (core gateway, single-
    project spoke, multi-project spoke).
  - **06** — Azure Policy that denies model deployments in spokes.
  - **07** — Model inference paths behind the APIM gateway.
  - **08** — Nine agent sub-labs: versioned agents, code interpreter, hosted
    agents, agent memory, MCP servers (Contoso PMO + private banking), offline
    evaluation, live observability, and human-in-the-loop.
  - **09** — Azure AI Content Understanding behind the APIM gateway.
  - **10–12** — Foundry IQ knowledge bases (single agent, multi-agent
    router-and-specialists, and deep research with `o3-deep-research`).
  - **13** — Three-layer guardrails (Prompt Shields, PII detection, custom
    blocklist) on a bank customer-service agent.
  - **14** — AI Red Teaming (PyRIT) basic and advanced scans.
  - **15** — Fine-tuning via knowledge distillation (`gpt-4.1-mini` teacher →
    `Phi-4-mini` student) with Olive + PEFT (LoRA).
- Shared `.env.example` and `pyproject.toml` driven by `uv`.
- `DefaultAzureCredential`-based auth throughout — no admin keys in notebooks.
- Contributor docs: [README.md](README.md), [CONTRIBUTING.md](CONTRIBUTING.md),
  [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md), [SECURITY.md](SECURITY.md).

[0.8.0]: https://github.com/corticalstack/awesome-foundry-nextgen/releases/tag/v0.8.0
[0.7.0]: https://github.com/corticalstack/awesome-foundry-nextgen/releases/tag/v0.7.0
[0.6.0]: https://github.com/corticalstack/awesome-foundry-nextgen/releases/tag/v0.6.0
[0.5.1]: https://github.com/corticalstack/awesome-foundry-nextgen/releases/tag/v0.5.1
[0.5.0]: https://github.com/corticalstack/awesome-foundry-nextgen/releases/tag/v0.5.0
[0.4.0]: https://github.com/corticalstack/awesome-foundry-nextgen/releases/tag/v0.4.0
[0.3.0]: https://github.com/corticalstack/awesome-foundry-nextgen/releases/tag/v0.3.0
[0.2.0]: https://github.com/corticalstack/awesome-foundry-nextgen/releases/tag/v0.2.0
[0.1.0]: https://github.com/corticalstack/awesome-foundry-nextgen/releases/tag/v0.1.0
