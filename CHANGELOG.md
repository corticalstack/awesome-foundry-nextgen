# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[0.1.0]: https://github.com/corticalstack/awesome-foundry-nextgen/releases/tag/v0.1.0
