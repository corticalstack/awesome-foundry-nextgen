# Hosted agents from source code, and their sessions

This lab deploys a hosted agent from a zip of Python source, with no container image and no
registry, then works the session API against it: isolation, file upload, idle timeout, stop and
delete.

The agent, `contoso-rm-notes-agent`, is a meeting-notes assistant for Contoso Wealth relationship
managers. It is the same Agent Framework shape as the [08-03](../08-03-hosted-agents/08-03-00-hosted-agents.md)
agent (`FoundryChatClient` through the `core-alpha` APIM connection, `ResponsesHostServer`), plus
four function tools that read and write under `$HOME`: `save_note`, `list_notes`, `read_file`
and `where_am_i`. `$HOME` is what the platform persists per session, so the notes make every
session operation visible.

## Code deployment versus a container image

| | Container image (08-03) | Source code (this lab) |
|---|---|---|
| You build | A Docker image, pushed to ACR | A flat zip: `main.py`, `requirements.txt`, optionally `packages/` |
| Definition field | `container_configuration=ContainerConfiguration(image=...)` | `code_configuration=CodeConfiguration(runtime, entry_point, dependency_resolution)` |
| Runtime | Whatever the Dockerfile says | A platform image: `python_3_13`, `python_3_14` or `dotnet_10` |
| Dependencies | Installed in the Dockerfile | `remote_build`: the service runs pip from `requirements.txt`. `bundled`: you ship extracted Linux wheels in `packages/` and the service installs nothing |
| Extra RBAC | AcrPull for the agent identity | None for the image; the identity still needs Foundry User on the project to call the model |
| Versioning | By image digest | By the zip's SHA-256 plus the definition: an identical upload returns the existing version |
| Audit | Pull the image | `download_code` returns the zip the service holds; compare its SHA-256 with `content_hash` |
| Limits | Image size per registry | 250 MB zip, flat at the root |

The two paths are mutually exclusive on a version, and both run in the same per-session sandbox
with the same tiers (`0.5`/`1Gi`, `1`/`2Gi`, `2`/`4Gi` CPU and memory).

Use `remote_build` for the fast inner loop and `bundled` when the build must be reproducible,
when packages are private or wheels-only, or when the remote build cannot resolve them.
Bundled wheels are built for the sandbox, not for your machine:
`uv pip install --target packages/ --python-platform x86_64-manylinux2014 --python-version 3.13 --only-binary :all:`.

## Sessions versus conversations

| | Session | Conversation |
|---|---|---|
| What it is | A sandbox with a persisted file system (`$HOME`) | The message history the platform stores for the Responses protocol |
| Identifier | `agent_session_id` | `previous_response_id` or a `conversation` ID |
| Created by | The first call that names no session, or `create_session` | The first response |
| Binds a call how | `extra_body={"agent_session_id": ...}` on `responses.create` | `previous_response_id=...` |
| Lifetime | Compute released after the idle timeout, files kept; deleted after 30 days without activity | Stored by the platform |

Passing a session ID binds a call to a sandbox. It does not replay earlier messages; that is what
`previous_response_id` does. The two are independent, and a chat that needs both passes both.

Session states: `creating`, `active` (compute running), `idle` (compute released, files kept),
`failed`, `deleting`, `deleted`, `expired`. `stop_session` releases the compute at once and keeps
the files; `delete_session` removes both.

## Idle timeout

The idle timeout is set per agent version with `SessionConfiguration(idle_timeout_seconds=...)`,
and a new value means a new version. Checked against the service on 2026-10-11: it accepts 120 to
3600 seconds (the default is 900) and rejects 60 and 14400 with
`'Session Configuration Idle Timeout Seconds' must be between 00:02:00 and 01:00:00`. The
240-minute maximum that the azd agents extension release notes mention does not apply here. The
same check rejected `python_3_12`: the supported runtimes are `python_3_13`, `python_3_14` and
`dotnet_10`.

This lab deploys with the 120-second minimum so that 08-12-02 can watch a session go idle and
resume within a notebook run.

## Permissions

| Who | Needs | For |
|---|---|---|
| You, deploying | Foundry Project Manager (or Owner) on the project | `create_version_from_code` |
| You, granting | Owner or User Access Administrator on the spoke resource group | The role assignment in 08-12-01 Step 6 |
| You, operating | Foundry User on the project | Listing, reading and deleting sessions created by other identities |
| The agent identity | Foundry User on the project | Calling the model through the project's Responses API |

Without Foundry User, a caller sees only the sessions its own identity created. For per-user
isolation and multiplexing many users onto one sandbox, see the session isolation documentation
linked below; that is a separate lab.

## Files

| File | Purpose |
|---|---|
| [`08-12-01-deploy-hosted-agent-from-code.ipynb`](08-12-01-deploy-hosted-agent-from-code.ipynb) | Zips the agent, registers `remote_build` and `bundled` versions, waits for `active`, grants the agent identity its role, tests the agent, shows dedup and `download_code`, probes the idle timeout bounds |
| [`08-12-02-manage-hosted-agent-sessions.ipynb`](08-12-02-manage-hosted-agent-sessions.ipynb) | Platform-created and explicit sessions, isolation, session files, listing by status, idle timeout, stop and delete |
| [`contoso-rm-notes-agent/main.py`](contoso-rm-notes-agent/main.py) | The agent code: a `FoundryChatClient` agent with four `$HOME` tools behind `ResponsesHostServer` |
| [`contoso-rm-notes-agent/requirements.in`](contoso-rm-notes-agent/requirements.in) | Direct dependencies; `requirements.txt` is compiled from it for Python 3.13 on manylinux2014 |
| [`data/meeting-agenda.md`](data/meeting-agenda.md) | The file 08-12-02 uploads into a session |

## Resources

- [Deploy a hosted agent from source code](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/deploy-hosted-agent-code)
- [Manage hosted agent sessions](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/manage-hosted-sessions)
- [Hosted agents in Foundry Agent Service](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents)
- [Isolate hosted agent sessions per user](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/isolate-sessions-per-user)
- [azure-ai-projects hosted agent samples](https://github.com/Azure/azure-sdk-for-python/tree/main/sdk/ai/azure-ai-projects/samples/hosted_agents)

---

[Next: Deploy a hosted agent from source code →](08-12-01-deploy-hosted-agent-from-code.ipynb)
