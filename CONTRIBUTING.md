# Contributing

Thanks for taking the time to contribute. This repo is a growing collection of
Microsoft Foundry labs - every fix, clarification, and new scenario helps.

## Ground rules

- **Never commit directly to `main`.** All changes go through a pull request from a
  feature branch.
- **Auth is `DefaultAzureCredential`.** Don't introduce admin keys in notebooks - use
  RBAC, except where APIM subscription keys are the documented path.
- **Notebooks must run top-to-bottom** against the standard `.env` after the
  prerequisite labs have run.

## Local setup

This repo uses [pre-commit](https://pre-commit.com) to run a [gitleaks](https://github.com/gitleaks/gitleaks)
secret scan on every commit. Set it up once per clone:

```bash
pip install pre-commit   # or: uv tool install pre-commit
pre-commit install
```

The hook scans only your staged changes, so it blocks new secrets or environment
identifiers without re-flagging older content. It runs gitleaks via Docker, so
Docker must be available locally. Rules live in [`.gitleaks.toml`](.gitleaks.toml):
the default gitleaks rule set (API keys, tokens, connection strings) plus a
repo-specific rule that catches Azure subscription IDs in URLs and resource paths.

To scan the whole working tree manually:

```bash
docker run --rm -v "$PWD:/repo" zricethezav/gitleaks:v8.30.1 dir /repo
```

## Notebook output hygiene

Committed notebooks **keep their cell outputs** - they double as a "here is what
success looks like" reference. Because outputs are committed, treat them as content:

- **Restart and Run All** before committing so outputs are coherent and in order.
- **Scrub environment identifiers** from outputs before committing. Replace real
  Azure subscription IDs, resource/account/function-app names, internal hostnames,
  and any keys or tokens with placeholders (`{subscription-id}`, `{resource}`,
  `{project}`, and so on). The pre-commit hook catches subscription IDs and common
  secret shapes, but resource names and hostnames still need a manual pass.
- Use the canonical all-zeros subscription ID (`00000000-0000-0000-0000-000000000000`)
  for documented examples; it is allowlisted.

## Branching

```
feature/<issue-number>-<brief-description>
bugfix/<issue-number>-<brief-description>
```

Branch from `main`. Open the PR back to `main`.

## Adding a new lab

1. Pick the next free lab number (current free slots: **17**, **18**, and anything
   above **20**).
2. Create a top-level directory `NN-short-name/`.
3. Add an `NN-00-<topic>.md` intro covering: what the lab demonstrates, prerequisites,
   architecture, and how to run it.
4. Notebooks should be numbered `NN-01-…`, `NN-02-…`, etc., in execution order.
5. If the lab provisions resources, include a `main.bicep` and document the deployment
   step in the intro.
6. Add any new env vars to [`.env.example`](.env.example) with placeholder values.
7. Add the lab to the index table in [`README.md`](README.md).

## PR checklist

Before requesting review:

- [ ] On a feature branch (not `main`)
- [ ] Notebook runs top-to-bottom on a clean kernel
- [ ] `uv sync` succeeds; no new heavyweight deps without justification
- [ ] New env vars added to [`.env.example`](.env.example)
- [ ] Lab added (or updated) in the index table of [`README.md`](README.md)
- [ ] No secrets in committed files (`.env`, keys, connection strings)
- [ ] `pre-commit` hook passes (gitleaks secret scan)
- [ ] Notebook outputs scrubbed of subscription IDs, resource names, and hostnames
- [ ] Screenshots placed under [`docs/screenshots/`](docs/screenshots/)

## Reporting issues

Open a GitHub issue. Use navigable links to files
(`[config.py](src/config.py)`) rather than plain backticks so reviewers can click
through. Include the lab number and notebook step in the title where possible.

---

<sub>If you spot a typo, broken link, or stale screenshot, a one-line PR is perfectly
welcome.</sub>
