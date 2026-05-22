# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
