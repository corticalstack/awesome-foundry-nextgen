# Copyright (c) Microsoft. All rights reserved.

"""OpenTelemetry tracing for the Claude Agent SDK Foundry-hosted agent.

The Claude counterpart to 08-10's ``tracing.py``: it maps Claude Agent SDK
messages to OpenTelemetry spans following the `GenAI semantic conventions
<https://opentelemetry.io/docs/specs/semconv/gen-ai/>`_ so they render as a tree
in **Foundry portal -> Tracing**:

    invoke_agent claude-agent-sdk        (SERVER, parent)
    +-- execute_tool <name>              (INTERNAL, one per ToolUseBlock)
    +-- chat <model>                     (CLIENT, carries token usage so Foundry
                                          populates Tokens (In/Out) and cost)

Tracing is best-effort: any exception in here is caught and logged; it must
never break an invocation.
"""

from __future__ import annotations

import contextlib
import logging
import os

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
    """Context manager that yields an ``on_message`` callback.

    Wire it onto the Claude SDK response stream::

        with trace_invocation(...) as on_message:
            async for message in client.receive_response():
                on_message(message)
                ...

    The parent ``invoke_agent`` span is opened on entry and closed on exit;
    ``execute_tool`` spans are emitted per ``ToolUseBlock`` and a ``chat <model>``
    span carrying token usage is emitted from the terminal ``ResultMessage``.
    """
    from opentelemetry import trace
    from opentelemetry.trace import SpanKind, Status, StatusCode

    # Imported lazily so this module loads even if the SDK is absent at import time.
    from claude_agent_sdk import AssistantMessage, ResultMessage, ToolUseBlock

    tracer = trace.get_tracer("claude-agent-sdk-invocations")
    invoke_span = tracer.start_span(
        "invoke_agent claude-agent-sdk",
        kind=SpanKind.SERVER,
        attributes={
            "gen_ai.system": "claude_agent_sdk",
            "gen_ai.operation.name": "invoke_agent",
            "gen_ai.agent.name": "claude-agent-sdk",
            "gen_ai.conversation.id": session_id or "",
            "foundry.invocation.id": invocation_id,
            "gen_ai.request.model": request_model,
        },
    )
    parent_ctx = trace.set_span_in_context(invoke_span)

    def on_message(message) -> None:
        try:
            if isinstance(message, AssistantMessage):
                # One execute_tool span per tool the model invoked this turn.
                for block in message.content:
                    if isinstance(block, ToolUseBlock):
                        span = tracer.start_span(
                            f"execute_tool {block.name}",
                            context=parent_ctx,
                            kind=SpanKind.INTERNAL,
                            attributes={
                                "gen_ai.system": "claude_agent_sdk",
                                "gen_ai.operation.name": "execute_tool",
                                "gen_ai.tool.name": block.name,
                                "gen_ai.tool.call.id": block.id,
                            },
                        )
                        span.end()

            elif isinstance(message, ResultMessage):
                usage = message.usage or {}
                model = getattr(message, "model", None) or request_model or "unknown"
                chat_attrs = {
                    "gen_ai.system": "claude_agent_sdk",
                    "gen_ai.provider.name": "azure.ai.anthropic",
                    "gen_ai.operation.name": "chat",
                    "gen_ai.request.model": model,
                    "gen_ai.response.model": model,
                    "gen_ai.conversation.id": session_id or "",
                }
                for src, dst in (
                    ("input_tokens", "gen_ai.usage.input_tokens"),
                    ("output_tokens", "gen_ai.usage.output_tokens"),
                    ("cache_read_input_tokens", "gen_ai.usage.cache_read_tokens"),
                    ("cache_creation_input_tokens", "gen_ai.usage.cache_write_tokens"),
                ):
                    val = usage.get(src)
                    if val is not None:
                        chat_attrs[dst] = val
                if message.total_cost_usd is not None:
                    chat_attrs["gen_ai.usage.cost"] = message.total_cost_usd

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
                ):
                    val = usage.get(src)
                    if val is not None:
                        invoke_span.set_attribute(dst, val)
                invoke_span.set_attribute("gen_ai.response.model", model)
                if message.is_error:
                    invoke_span.set_status(
                        Status(StatusCode.ERROR, message.result or "agent error")
                    )
        except Exception:  # pragma: no cover - tracing must never break
            logger.exception("tracing on_message failed")

    try:
        yield on_message
    finally:
        invoke_span.end()
