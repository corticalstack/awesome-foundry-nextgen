# Copyright (c) Microsoft. All rights reserved.

"""Claude Agent SDK exposed via the Foundry agent invocations protocol.

This is the Claude Agent SDK counterpart to 08-10's GitHub Copilot SDK agent.
The Foundry hosting shell is identical - ``InvocationAgentServerHost`` registered
with ``AgentProtocol.INVOCATIONS`` - only the agent loop changes: a singleton
``ClaudeSDKClient`` drives the reason/act/observe loop inside a bundled
``claude`` CLI subprocess.

Backends (selected automatically from environment variables):
  - Foundry Claude model (preferred):
        ANTHROPIC_FOUNDRY_RESOURCE (or derived from AZURE_AI_PROJECT_ENDPOINT /
        FOUNDRY_PROJECT_ENDPOINT) + AZURE_AI_MODEL_DEPLOYMENT_NAME
        -> sets CLAUDE_CODE_USE_FOUNDRY=1 so the SDK targets
           https://<resource>.services.ai.azure.com/anthropic/v1/messages over
           Managed Identity (token scope https://ai.azure.com/.default). This is
           the no-translation match: the Claude Agent SDK speaks the Anthropic
           Messages API and Foundry serves Claude over that same surface.
           AZURE_CLIENT_ID should be pinned to the AgentIdentity client_id.
  - Anthropic API (fallback):
        ANTHROPIC_API_KEY set -> the public api.anthropic.com backend (a real
        Claude model, but model traffic leaves Foundry; not "BYO Foundry model").

Two extension surfaces, mirroring 08-10:
  - ``system_prompt.md``      -> appended to the Claude Code preset system prompt.
  - ``skills/<name>/SKILL.md`` -> Agent Skills, copied into the working dir's
    ``.claude/skills`` so the CLI discovers them (project setting source).

OpenTelemetry tracing for tool calls and token usage lives in ``tracing.py``;
per-invocation spans show up in Foundry portal -> Tracing.
"""

import asyncio
import json
import logging
import os
import pathlib
import shutil
import sys
import uuid

from dotenv import load_dotenv
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse

from azure.ai.agentserver.invocations import InvocationAgentServerHost
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    StreamEvent,
    TextBlock,
    ToolUseBlock,
)

from tracing import setup_tracing, trace_invocation

load_dotenv(override=False)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

setup_tracing()

HERE = pathlib.Path(__file__).parent
SKILLS_SRC = HERE / "skills"
SYSTEM_PROMPT_FILE = HERE / "system_prompt.md"

HOME = os.environ.get("HOME") or "/root"
WORKDIR = pathlib.Path(HOME) / "agent-workspace"

# Stream text token-by-token from raw partial-message events. If a future SDK
# stops emitting StreamEvents, flip this to False to stream per-turn TextBlocks.
USE_PARTIAL_STREAMING = True

app = InvocationAgentServerHost()
_client: ClaudeSDKClient | None = None
_client_lock = asyncio.Lock()
_session_id: str | None = None
_model: str | None = None


# ── Configuration ────────────────────────────────────────────────────────────


def _derive_foundry_resource() -> str | None:
    """The Foundry resource (account) name, explicit or derived from the endpoint."""
    explicit = os.environ.get("ANTHROPIC_FOUNDRY_RESOURCE")
    if explicit:
        return explicit
    endpoint = (
        os.environ.get("AZURE_AI_PROJECT_ENDPOINT")
        or os.environ.get("FOUNDRY_PROJECT_ENDPOINT")
        or ""
    )
    # https://<resource>.services.ai.azure.com/api/projects/<project>
    if ".services.ai.azure.com" in endpoint:
        host = endpoint.split("://", 1)[-1].split("/", 1)[0]
        return host.split(".")[0]
    return None


def _configure_backend() -> str | None:
    """Set the env vars the bundled ``claude`` CLI reads, from whatever backend
    is configured. Returns the primary model deployment name (or None to let the
    Anthropic backend pick its default)."""
    resource = _derive_foundry_resource()
    model = os.environ.get("AZURE_AI_MODEL_DEPLOYMENT_NAME")
    if resource and model:
        os.environ["CLAUDE_CODE_USE_FOUNDRY"] = "1"
        os.environ["ANTHROPIC_FOUNDRY_RESOURCE"] = resource
        # Point every model role at the single deployed Claude model so the
        # CLI's background (haiku) and extended-thinking (opus) roles resolve to
        # a real deployment instead of 404ing on an undeployed family.
        os.environ.setdefault("ANTHROPIC_DEFAULT_SONNET_MODEL", model)
        os.environ.setdefault("ANTHROPIC_DEFAULT_HAIKU_MODEL", model)
        os.environ.setdefault("ANTHROPIC_DEFAULT_OPUS_MODEL", model)
        logger.info("Backend: Foundry Claude (resource=%s, model=%s)", resource, model)
        return model
    if os.environ.get("ANTHROPIC_API_KEY"):
        logger.info("Backend: public Anthropic API")
        return os.environ.get("ANTHROPIC_MODEL")
    raise RuntimeError(
        "No model backend configured. Set ANTHROPIC_FOUNDRY_RESOURCE (or "
        "AZURE_AI_PROJECT_ENDPOINT) + AZURE_AI_MODEL_DEPLOYMENT_NAME for a Foundry "
        "Claude model, or ANTHROPIC_API_KEY for the public Anthropic API."
    )


def _system_prompt() -> dict:
    """Claude Code preset, with ``system_prompt.md`` appended when present."""
    preset: dict = {"type": "preset", "preset": "claude_code"}
    if SYSTEM_PROMPT_FILE.is_file():
        content = SYSTEM_PROMPT_FILE.read_text(encoding="utf-8").strip()
        if content:
            preset["append"] = content
    return preset


def _prepare_workspace() -> None:
    """Create the session working dir and expose bundled skills as project-scoped
    Agent Skills (``<cwd>/.claude/skills/<name>/SKILL.md``)."""
    WORKDIR.mkdir(parents=True, exist_ok=True)
    if SKILLS_SRC.is_dir():
        dest = WORKDIR / ".claude" / "skills"
        dest.mkdir(parents=True, exist_ok=True)
        for skill in SKILLS_SRC.iterdir():
            if skill.is_dir():
                shutil.copytree(skill, dest / skill.name, dirs_exist_ok=True)


# ── Session lifecycle ────────────────────────────────────────────────────────


async def _ensure_client() -> None:
    """Lazy-create the singleton Claude SDK client on first invocation."""
    global _client, _session_id, _model
    if _client is not None:
        return

    _session_id = os.environ.get("FOUNDRY_AGENT_SESSION_ID") or str(uuid.uuid4())
    _model = _configure_backend()
    _prepare_workspace()

    options = ClaudeAgentOptions(
        model=_model,
        system_prompt=_system_prompt(),
        # No human at the terminal: auto-approve every tool call. Direct
        # equivalent of 08-10's PermissionHandler.approve_all / Copilot yolo mode.
        permission_mode="bypassPermissions",
        cwd=str(WORKDIR),
        setting_sources=["project"],
        include_partial_messages=USE_PARTIAL_STREAMING,
        # Keep a hosted container from reaching non-essential endpoints.
        env={"CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"},
    )
    _client = ClaudeSDKClient(options=options)
    await _client.connect()
    logger.info("Claude SDK client connected (session=%s, model=%s)", _session_id, _model)


# ── Invocation handler ───────────────────────────────────────────────────────


def _sse(obj: dict) -> bytes:
    return f"data: {json.dumps(obj)}\n\n".encode()


async def _stream_response(invocation_id: str, input_text: str):
    """Drive one Claude turn and forward SDK messages as Server-Sent Events."""
    # Serialise turns: a single ClaudeSDKClient holds one conversation, so
    # concurrent queries on it would interleave.
    async with _client_lock:
        try:
            await _ensure_client()
        except Exception as exc:  # backend misconfiguration etc.
            yield _sse({"type": "error", "message": str(exc)})
            yield (
                f"event: done\ndata: {json.dumps({'invocation_id': invocation_id, 'session_id': _session_id})}\n\n"
            ).encode()
            return

        request_model = _model or "claude"
        streamed_chars = 0

        with trace_invocation(invocation_id, _session_id, request_model) as on_trace:
            await _client.query(input_text)
            async for message in _client.receive_response():
                on_trace(message)

                if isinstance(message, StreamEvent):
                    event = message.event or {}
                    if event.get("type") == "content_block_delta":
                        delta = event.get("delta") or {}
                        if delta.get("type") == "text_delta" and delta.get("text"):
                            streamed_chars += len(delta["text"])
                            yield _sse({
                                "type": "assistant.message_delta",
                                "data": {"deltaContent": delta["text"]},
                            })

                elif isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, ToolUseBlock):
                            yield _sse({
                                "type": "tool.use",
                                "data": {"name": block.name, "id": block.id},
                            })
                        elif isinstance(block, TextBlock) and not USE_PARTIAL_STREAMING:
                            streamed_chars += len(block.text)
                            yield _sse({
                                "type": "assistant.message_delta",
                                "data": {"deltaContent": block.text},
                            })

                elif isinstance(message, ResultMessage):
                    if message.is_error:
                        yield _sse({
                            "type": "error",
                            "message": (message.result or "agent error"),
                        })
                    # Safety net: if partial streaming produced no text, surface
                    # the final result text so the caller is never left empty.
                    elif streamed_chars == 0 and message.result:
                        yield _sse({
                            "type": "assistant.message_delta",
                            "data": {"deltaContent": message.result},
                        })
                    yield _sse({
                        "type": "result",
                        "data": {
                            "session_id": message.session_id,
                            "num_turns": message.num_turns,
                            "total_cost_usd": message.total_cost_usd,
                            "usage": message.usage,
                        },
                    })

            yield (
                f"event: done\ndata: "
                f"{json.dumps({'invocation_id': invocation_id, 'session_id': _session_id})}\n\n"
            ).encode()


@app.invoke_handler
async def handle_invoke(request: Request) -> Response:
    try:
        data = await request.json()
        if not isinstance(data, dict):
            raise ValueError("body is not a JSON object")
        input_text = data.get("input")
        if not isinstance(input_text, str) or not input_text.strip():
            raise ValueError('missing or empty "input" field')
    except (json.JSONDecodeError, ValueError):
        return JSONResponse(
            status_code=400,
            content={
                "error": "invalid_request",
                "message": (
                    'Request body must be a JSON object with a non-empty '
                    '"input" string, e.g. {"input": "What can you help me with?"}'
                ),
            },
        )
    invocation_id = getattr(request.state, "invocation_id", str(uuid.uuid4()))
    return StreamingResponse(
        _stream_response(invocation_id, input_text),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


if __name__ == "__main__":
    has_foundry = bool(
        _derive_foundry_resource() and os.environ.get("AZURE_AI_MODEL_DEPLOYMENT_NAME")
    )
    has_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY"))
    if not has_foundry and not has_anthropic:
        sys.exit(
            "Error: Set ANTHROPIC_FOUNDRY_RESOURCE (or AZURE_AI_PROJECT_ENDPOINT) + "
            "AZURE_AI_MODEL_DEPLOYMENT_NAME for a Foundry Claude model, or "
            "ANTHROPIC_API_KEY for the public Anthropic API."
        )
    app.run()
