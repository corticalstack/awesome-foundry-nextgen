# Copyright (c) Microsoft. All rights reserved.

"""GitHub Copilot SDK exposed via the Foundry agent invocations protocol.

Auth modes (selected automatically from environment variables):
  - GITHUB_TOKEN set
        → talks to the GitHub Copilot model (quickest start; no Azure needed).
  - FOUNDRY_PROJECT_ENDPOINT + AZURE_AI_MODEL_DEPLOYMENT_NAME set
        → talks to a BYOK Foundry model via Managed Identity. main.py appends
          `/openai/v1/` to the project endpoint, so the Copilot SDK calls
          `<project-endpoint>/openai/v1/responses`. Token audience is
          `https://ai.azure.com`.
          AZURE_CLIENT_ID should be pinned to the AgentIdentity client_id
          (`instance_identity.client_id` from version metadata).

Two extension surfaces customers should know about:
  - ``system_prompt.md`` — persona / global policy appended to the CLI's
    built-in system message. Edit it, redeploy, get a fresh personality.
  - ``skills/<name>/SKILL.md`` — task-specific procedures the model can
    discover and follow on demand (see the bundled ``m365-license-analytics`` skill).

OpenTelemetry tracing for tool calls and token usage lives in
``tracing.py``; per-invocation spans show up in Foundry portal → Tracing.
"""

import asyncio
import json
import logging
import os
import pathlib
import sys
import uuid

from dotenv import load_dotenv
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse

from azure.ai.agentserver.invocations import InvocationAgentServerHost
from copilot import CopilotClient, SubprocessConfig
from copilot.session import PermissionHandler, ProviderConfig
from copilot.generated.session_events import SessionEventType

from tracing import setup_tracing, trace_invocation

load_dotenv(override=False)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

setup_tracing()

HERE = pathlib.Path(__file__).parent
SKILLS_DIR = str(HERE / "skills")
SYSTEM_PROMPT_FILE = HERE / "system_prompt.md"

app = InvocationAgentServerHost()
_client: CopilotClient | None = None
_session = None
_session_id: str | None = None


# ── Configuration ────────────────────────────────────────────────────────────


def _byok_provider() -> tuple[ProviderConfig | None, str | None]:
    """Build a Foundry ProviderConfig from env vars, or return (None, None).

    The Foundry project exposes an OpenAI-compatible surface at
    ``<project-endpoint>/openai/v1/``. We read the project endpoint - which the
    hosted-agent platform auto-injects as ``FOUNDRY_PROJECT_ENDPOINT`` - and
    append ``/openai/v1/`` so the Copilot CLI's ``responses`` wire API targets
    ``<project-endpoint>/openai/v1/responses``. (The upstream sample used the
    project endpoint as-is, with no ``/openai/v1/`` suffix, so its calls 404'd;
    appending the suffix is the fix.) Auth is Managed Identity, audience
    ``ai.azure.com``.
    """
    model = os.environ.get("AZURE_AI_MODEL_DEPLOYMENT_NAME", "")

    # APIM-direct mode: point the Copilot CLI straight at an APIM-fronted Azure
    # OpenAI gateway, bypassing the Foundry project's connection model-gateway.
    # That connection path today supports only *prompt* agents - a hosted agent
    # calling the Responses API through a `connection/deployment` model string
    # fails to resolve (the gateway sees the qualified name, not a deployment).
    # APIM authenticates with the gateway subscription key in the `api-key`
    # header, which the `azure` provider type sends; `model` is the bare
    # deployment name (e.g. `gpt-5-mini`), which must be a *reasoning* model
    # because the Copilot CLI's responses protocol carries encrypted reasoning
    # content that non-reasoning models reject.
    apim_base = os.environ.get("APIM_BASE_URL", "")
    apim_key = os.environ.get("APIM_KEY", "")
    if apim_base and apim_key and model:
        return ProviderConfig(
            type="azure",
            base_url=apim_base.rstrip("/"),
            api_key=apim_key,
            wire_api="responses",
            azure={"api_version": os.environ.get("APIM_API_VERSION", "2025-03-01-preview")},
        ), model

    # Default mode: the Foundry project's OpenAI-compatible surface at
    # ``<project-endpoint>/openai/v1/``, authenticated with Managed Identity
    # (audience ``ai.azure.com``). This is the standalone 08-10 path.
    endpoint = (
        os.environ.get("FOUNDRY_PROJECT_ENDPOINT")
        or os.environ.get("AZURE_AI_PROJECT_ENDPOINT")
        or ""
    )
    if not endpoint or not model:
        return None, None

    base_url = endpoint.rstrip("/") + "/openai/v1/"
    from azure.identity import DefaultAzureCredential
    token = DefaultAzureCredential().get_token("https://ai.azure.com/.default").token
    return ProviderConfig(
        type="openai",
        base_url=base_url,
        wire_api="responses",
        bearer_token=token,
    ), model


def _system_message() -> dict | None:
    """Append ``system_prompt.md`` to the Copilot CLI's built-in system message."""
    if not SYSTEM_PROMPT_FILE.is_file():
        return None
    content = SYSTEM_PROMPT_FILE.read_text(encoding="utf-8").strip()
    if not content:
        return None
    return {"mode": "append", "content": content}


# ── Session lifecycle ────────────────────────────────────────────────────────


async def _ensure_session() -> None:
    """Lazy-create the singleton Copilot session on first invocation."""
    global _client, _session, _session_id
    if _session is not None:
        return

    _session_id = os.environ.get("FOUNDRY_AGENT_SESSION_ID") or str(uuid.uuid4())

    provider, model = _byok_provider()
    github_token = os.environ.get("GITHUB_TOKEN")

    if provider:
        _client = CopilotClient(auto_start=False)
    elif github_token:
        _client = CopilotClient(
            SubprocessConfig(github_token=github_token), auto_start=False)
    else:
        raise RuntimeError(
            "Set GITHUB_TOKEN (Copilot model) or "
            "FOUNDRY_PROJECT_ENDPOINT + AZURE_AI_MODEL_DEPLOYMENT_NAME "
            "(BYOK Foundry model)")
    await _client.start()

    common = dict(
        on_permission_request=PermissionHandler.approve_all,
        streaming=True,
        skill_directories=[SKILLS_DIR],
        working_directory=os.environ.get("HOME", "/home"),
        provider=provider,
        model=model,
        system_message=_system_message(),
    )

    try:
        _session = await _client.resume_session(_session_id, **common)
        logger.info("Resumed session: %s", _session_id)
    except Exception:
        _session = await _client.create_session(session_id=_session_id, **common)
        logger.info("Created session: %s", _session_id)


# ── Invocation handler ───────────────────────────────────────────────────────


async def _stream_response(invocation_id: str, input_text: str):
    """Forward Copilot SDK session events as Server-Sent Events."""
    await _ensure_session()
    queue: asyncio.Queue = asyncio.Queue()
    request_model = os.environ.get("AZURE_AI_MODEL_DEPLOYMENT_NAME", "")

    with trace_invocation(invocation_id, _session_id, request_model) as on_trace:

        def on_event(event):
            on_trace(event)
            if event.type == SessionEventType.SESSION_IDLE:
                queue.put_nowait(None)
            elif event.type == SessionEventType.SESSION_ERROR:
                queue.put_nowait(RuntimeError(
                    getattr(event.data, "message", "error")))
            else:
                queue.put_nowait(event)

        unsubscribe = _session.on(on_event)
        try:
            await _session.send(input_text)
            while True:
                item = await queue.get()
                if item is None:
                    break
                if isinstance(item, Exception):
                    yield f"data: {json.dumps({'type': 'error', 'message': str(item)})}\n\n".encode()
                    break
                yield f"data: {json.dumps(item.to_dict())}\n\n".encode()
            yield (
                f"event: done\ndata: "
                f"{json.dumps({'invocation_id': invocation_id, 'session_id': _session_id})}\n\n"
            ).encode()
        finally:
            unsubscribe()


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
    return StreamingResponse(
        _stream_response(request.state.invocation_id, input_text),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


if __name__ == "__main__":
    has_token = bool(os.environ.get("GITHUB_TOKEN"))
    has_byok = bool(
        os.environ.get("FOUNDRY_PROJECT_ENDPOINT")
        and os.environ.get("AZURE_AI_MODEL_DEPLOYMENT_NAME")
    )
    if not has_token and not has_byok:
        sys.exit(
            "Error: Set GITHUB_TOKEN (Copilot model) or "
            "FOUNDRY_PROJECT_ENDPOINT + AZURE_AI_MODEL_DEPLOYMENT_NAME "
            "(BYOK Foundry model)")
    app.run()
