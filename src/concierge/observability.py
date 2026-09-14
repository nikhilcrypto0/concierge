"""Structured JSON logs with request correlation, plus optional Langfuse tracing of graph steps."""

import logging
import sys
from contextlib import AbstractContextManager, nullcontext
from typing import TYPE_CHECKING, Any
from uuid import UUID

import structlog

if TYPE_CHECKING:
    from langchain_core.callbacks import BaseCallbackHandler

    from concierge.config import Settings


def configure_logging(level: str, json_logs: bool) -> None:
    renderer: structlog.types.Processor = (
        structlog.processors.JSONRenderer() if json_logs else structlog.dev.ConsoleRenderer()
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelNamesMapping()[level.upper()]
        ),
        logger_factory=structlog.PrintLoggerFactory(sys.stderr),
        cache_logger_on_first_use=True,
    )


def init_tracing(settings: "Settings") -> None:
    if not settings.tracing_enabled or settings.langfuse_secret_key is None:
        return
    from langfuse import Langfuse

    Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key.get_secret_value(),
        host=settings.langfuse_host,
        environment=settings.environment,
    )


def tracing_callbacks(settings: "Settings") -> list["BaseCallbackHandler"]:
    if not settings.tracing_enabled:
        return []
    from langfuse.langchain import CallbackHandler

    return [CallbackHandler(public_key=settings.langfuse_public_key)]


def trace_session(settings: "Settings", conversation_id: UUID) -> AbstractContextManager[Any]:
    """Group every trace of one conversation into a single Langfuse session."""
    if not settings.tracing_enabled:
        return nullcontext()
    from langfuse import propagate_attributes

    return propagate_attributes(session_id=str(conversation_id))


def shutdown_tracing(settings: "Settings") -> None:
    if not settings.tracing_enabled:
        return
    from langfuse import get_client

    get_client(public_key=settings.langfuse_public_key).shutdown()
