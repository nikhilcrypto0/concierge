"""Claude, used for exactly two judgment calls: classifying intent and drafting grounded answers.

Everything else in the workflow (lookups, policy, approvals, templated replies) is plain code.
Both calls return schema-validated Pydantic objects; output that fails validation is retried
once and then rejected, so unstructured text never reaches downstream code.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal, Protocol

import anthropic
import structlog
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import Runnable, RunnableConfig
from pydantic import BaseModel, Field

from concierge.agent.prompts import ANSWER_SYSTEM_PROMPT, CLASSIFY_SYSTEM_PROMPT
from concierge.config import Effort, Settings

log = structlog.get_logger(__name__)

Intent = Literal["question", "booking_status", "refund_request", "human_handoff", "out_of_scope"]

# Transient provider failures switch to the fallback model; client errors (400s) do not.
FALLBACK_ON: tuple[type[BaseException], ...] = (
    anthropic.APIConnectionError,
    anthropic.APITimeoutError,
    anthropic.RateLimitError,
    anthropic.InternalServerError,
    anthropic.OverloadedError,  # 529 is not an InternalServerError subclass
)


class Classification(BaseModel):
    intent: Intent
    booking_reference: str | None = Field(
        default=None, description="Booking reference such as BK-1042, only if the customer gave one"
    )
    confidence: float = Field(ge=0.0, le=1.0)
    search_query: str = Field(
        description="Standalone help-center search query for the customer's latest need, "
        "rewritten so it makes sense without the earlier conversation"
    )


class GroundedAnswer(BaseModel):
    answerable: bool = Field(description="False when the documents do not contain the answer")
    answer: str = Field(description="Reply to the customer, 1-4 short sentences, plain text")
    cited_chunk_ids: list[str] = Field(description="ids of the documents the answer relies on")


@dataclass(frozen=True)
class LLMResult[T: BaseModel]:
    value: T
    model: str
    input_tokens: int
    output_tokens: int


class LLMOutputError(RuntimeError):
    """The model's output did not validate against the schema (or it refused)."""


class SupportLLM(Protocol):
    async def classify(
        self, history: Sequence[BaseMessage], config: RunnableConfig | None = None
    ) -> LLMResult[Classification]: ...

    async def answer(
        self,
        question: str,
        documents: str,
        history: Sequence[BaseMessage],
        config: RunnableConfig | None = None,
    ) -> LLMResult[GroundedAnswer]: ...


class AnthropicSupportLLM:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._classifier = self._structured(Classification, settings.classify_effort, 1_024)
        self._answerer = self._structured(GroundedAnswer, settings.answer_effort, 2_048)

    def _structured(
        self, schema: type[BaseModel], effort: Effort, max_tokens: int
    ) -> Runnable[Any, Any]:
        def build(model: str) -> Runnable[Any, Any]:
            chat = ChatAnthropic(
                model=model,
                max_tokens=max_tokens,
                output_config={"effort": effort},
                max_retries=self._settings.llm_max_retries,
                default_request_timeout=self._settings.llm_timeout_seconds,
                api_key=self._settings.anthropic_api_key,
            )
            return chat.with_structured_output(schema, method="json_schema", include_raw=True)

        primary = build(self._settings.primary_model)
        fallback = build(self._settings.fallback_model)
        return primary.with_fallbacks([fallback], exceptions_to_handle=FALLBACK_ON)

    async def classify(
        self, history: Sequence[BaseMessage], config: RunnableConfig | None = None
    ) -> LLMResult[Classification]:
        messages = [SystemMessage(CLASSIFY_SYSTEM_PROMPT), *history]
        return await self._invoke(self._classifier, messages, Classification, "classify", config)

    async def answer(
        self,
        question: str,
        documents: str,
        history: Sequence[BaseMessage],
        config: RunnableConfig | None = None,
    ) -> LLMResult[GroundedAnswer]:
        prompt = (
            f"<documents>\n{documents}\n</documents>\n\n"
            f"<customer_question>\n{question}\n</customer_question>"
        )
        messages = [SystemMessage(ANSWER_SYSTEM_PROMPT), *history, HumanMessage(prompt)]
        return await self._invoke(self._answerer, messages, GroundedAnswer, "answer", config)

    async def _invoke[T: BaseModel](
        self,
        runnable: Runnable[Any, Any],
        messages: list[BaseMessage],
        schema: type[T],
        step: str,
        config: RunnableConfig | None,
    ) -> LLMResult[T]:
        run_config: RunnableConfig = {**(config or {}), "run_name": step}
        for attempt in (1, 2):
            result = await runnable.ainvoke(messages, config=run_config)
            parsed, raw = result.get("parsed"), result.get("raw")
            if isinstance(parsed, schema) and raw is not None:
                usage = raw.usage_metadata or {}
                return LLMResult(
                    value=parsed,
                    model=str(raw.response_metadata.get("model", "unknown")),
                    input_tokens=int(usage.get("input_tokens", 0)),
                    output_tokens=int(usage.get("output_tokens", 0)),
                )
            stop_reason = raw.response_metadata.get("stop_reason") if raw is not None else None
            log.warning("llm.output_rejected", step=step, attempt=attempt, stop_reason=stop_reason)
            if stop_reason == "refusal":
                break
        raise LLMOutputError(f"{step}: output failed schema validation")
