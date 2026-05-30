# Copyright (c) Microsoft. All rights reserved.

"""OpenTelemetry tracing for the GitHub Copilot Foundry-hosted agent.

This module is the single place where Copilot SDK ``SessionEvent``s are mapped
to OpenTelemetry spans following the `GenAI semantic conventions
<https://opentelemetry.io/docs/specs/semconv/gen-ai/>`_ so that they render as
a tree in **Foundry portal → Tracing**:

    invoke_agent github-copilot-invocations  (SERVER, parent)
    ├── execute_tool <name>                  (INTERNAL, one per tool call)
    └── chat <model>                         (CLIENT, one per model call;
                                              carries token usage so Foundry
                                              can populate the Tokens (In/Out)
                                              and Estimated Cost columns)

Tracing is best-effort: any exception in here is caught and logged; it must
never break an invocation.
"""

from __future__ import annotations

import contextlib
import logging
import os
from typing import Iterator

logger = logging.getLogger(__name__)


# ── Bootstrap ────────────────────────────────────────────────────────────────


def setup_tracing() -> bool:
    """Initialize Azure Monitor OpenTelemetry exporter.

    Reads ``APPLICATIONINSIGHTS_CONNECTION_STRING`` (auto-injected by Foundry).
    Returns ``True`` if tracing is enabled, ``False`` otherwise.
    """
    if not os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING"):
        return False
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor

        configure_azure_monitor(
            logger_name=__name__,
            instrumentation_options={"azure_sdk": {"enabled": True}},
        )
        logger.info("Azure Monitor OpenTelemetry tracing enabled")
        return True
    except Exception as exc:  # pragma: no cover - tracing is best-effort
        logger.warning("Failed to initialize Azure Monitor tracing: %s", exc)
        return False


# ── Per-invocation span tree ────────────────────────────────────────────────


@contextlib.contextmanager
def trace_invocation(
    invocation_id: str,
    session_id: str | None,
    request_model: str,
):
    """Context manager that yields an ``on_event`` callback.

    Wire it onto the Copilot SDK session::

        with trace_invocation(...) as on_event:
            unsubscribe = session.on(on_event)
            ...

    The parent ``invoke_agent`` span is opened on entry and closed on exit;
    ``execute_tool`` / ``chat`` child spans are opened and closed as the
    underlying Copilot SDK events flow through ``on_event``.
    """
    from opentelemetry import trace
    from opentelemetry.trace import Span, SpanKind, Status, StatusCode
    from copilot.generated.session_events import SessionEventType

    tracer = trace.get_tracer("github-copilot-invocations")
    invoke_span = tracer.start_span(
        "invoke_agent github-copilot-invocations",
        kind=SpanKind.SERVER,
        attributes={
            "gen_ai.system": "github_copilot_sdk",
            "gen_ai.operation.name": "invoke_agent",
            "gen_ai.agent.name": "github-copilot-invocations",
            "gen_ai.conversation.id": session_id or "",
            "foundry.invocation.id": invocation_id,
            "gen_ai.request.model": request_model,
        },
    )
    parent_ctx = trace.set_span_in_context(invoke_span)
    tool_spans: dict[str, Span] = {}

    def on_event(event) -> None:
        try:
            etype = event.type
            data = event.data

            if etype == SessionEventType.TOOL_EXECUTION_START:
                tool_name = getattr(data, "tool_name", "tool")
                tool_call_id = getattr(data, "tool_call_id", "")
                attrs = {
                    "gen_ai.system": "github_copilot_sdk",
                    "gen_ai.operation.name": "execute_tool",
                    "gen_ai.tool.name": tool_name,
                    "gen_ai.tool.call.id": tool_call_id,
                }
                mcp_server = getattr(data, "mcp_server_name", None)
                if mcp_server:
                    attrs["gen_ai.tool.type"] = "mcp"
                    attrs["mcp.server.name"] = mcp_server
                    attrs["mcp.tool.name"] = getattr(data, "mcp_tool_name", "") or ""
                span = tracer.start_span(
                    f"execute_tool {tool_name}",
                    context=parent_ctx,
                    kind=SpanKind.INTERNAL,
                    attributes=attrs,
                )
                if tool_call_id:
                    tool_spans[tool_call_id] = span
                else:
                    span.end()

            elif etype == SessionEventType.TOOL_EXECUTION_COMPLETE:
                tool_call_id = getattr(data, "tool_call_id", "")
                span = tool_spans.pop(tool_call_id, None)
                if span is not None:
                    if bool(getattr(data, "success", True)):
                        span.set_status(Status(StatusCode.OK))
                    else:
                        err = getattr(data, "error", None)
                        msg = getattr(err, "message", None) if err else "tool execution failed"
                        span.set_status(Status(StatusCode.ERROR, msg or "error"))
                    span.end()

            elif etype == SessionEventType.ASSISTANT_USAGE:
                # Foundry populates Tokens (In)/(Out) and Estimated Cost from
                # ``chat <model>`` spans, NOT the parent invoke span.
                model = getattr(data, "model", None) or request_model or "unknown"
                chat_attrs = {
                    "gen_ai.system": "github_copilot_sdk",
                    "gen_ai.provider.name": "azure.ai.openai",
                    "gen_ai.operation.name": "chat",
                    "gen_ai.request.model": model,
                    "gen_ai.response.model": model,
                    "gen_ai.conversation.id": session_id or "",
                }
                for src, dst in (
                    ("input_tokens", "gen_ai.usage.input_tokens"),
                    ("output_tokens", "gen_ai.usage.output_tokens"),
                    ("reasoning_tokens", "gen_ai.usage.reasoning_tokens"),
                    ("cache_read_tokens", "gen_ai.usage.cache_read_tokens"),
                    ("cache_write_tokens", "gen_ai.usage.cache_write_tokens"),
                    ("ttft_ms", "gen_ai.server.time_to_first_token"),
                ):
                    val = getattr(data, src, None)
                    if val is not None:
                        chat_attrs[dst] = val
                cost = getattr(data, "cost", None)
                if cost is not None:
                    chat_attrs["gen_ai.usage.cost"] = cost

                logger.info(
                    "emitting chat span model=%s in=%s out=%s cost=%s",
                    model,
                    chat_attrs.get("gen_ai.usage.input_tokens"),
                    chat_attrs.get("gen_ai.usage.output_tokens"),
                    chat_attrs.get("gen_ai.usage.cost"),
                )
                chat_span = tracer.start_span(
                    f"chat {model}",
                    context=parent_ctx,
                    kind=SpanKind.CLIENT,
                    attributes=chat_attrs,
                )
                chat_span.end()

                # Also accumulate on the parent for at-a-glance totals.
                for src, dst in (
                    ("input_tokens", "gen_ai.usage.input_tokens"),
                    ("output_tokens", "gen_ai.usage.output_tokens"),
                    ("reasoning_tokens", "gen_ai.usage.reasoning_tokens"),
                ):
                    val = getattr(data, src, None)
                    if val is not None:
                        invoke_span.set_attribute(dst, val)
                if model:
                    invoke_span.set_attribute("gen_ai.response.model", model)

            elif etype == SessionEventType.SESSION_ERROR:
                msg = getattr(data, "message", "session error")
                invoke_span.set_status(Status(StatusCode.ERROR, msg))
        except Exception:  # pragma: no cover - tracing must never break
            logger.exception("tracing on_event failed")

    try:
        yield on_event
    finally:
        for span in tool_spans.values():
            span.end()
        invoke_span.end()
