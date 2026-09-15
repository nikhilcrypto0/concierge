"""Runtime configuration. Every tunable lives here, loaded from env / .env — never from prompts."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Effort = Literal["low", "medium", "high"]


def _parse_named_keys(raw: str) -> dict[str, SecretStr]:
    """Parse "name:key,name2:key2" into {name: key}. Names show up in logs; keys never do."""
    keys: dict[str, SecretStr] = {}
    for pair in filter(None, (p.strip() for p in raw.split(","))):
        name, sep, key = pair.partition(":")
        if not sep or not name or len(key) < 16:
            raise ValueError("API keys must be 'name:key' pairs with keys of at least 16 chars")
        keys[name] = SecretStr(key)
    return keys


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["dev", "test", "prod"] = "dev"
    log_level: str = "INFO"

    database_url: str = "postgresql://localhost:5432/concierge"
    db_pool_min: int = 1
    db_pool_max: int = 10

    anthropic_api_key: SecretStr | None = None
    primary_model: str = "claude-opus-5"
    fallback_model: str = "claude-sonnet-5"
    classify_effort: Effort = "low"
    answer_effort: Effort = "medium"
    llm_timeout_seconds: float = 60.0
    llm_max_retries: int = 2

    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dimensions: int = 384
    embedding_cache_dir: str = ".cache/fastembed"
    retrieval_top_k: int = 4
    # Vector-only measured best on evals/retrieval_dataset.jsonl (see evals/results/retrieval.json).
    retrieval_mode: Literal["hybrid", "vector", "keyword"] = "vector"
    retrieval_keyword_weight: float = 0.5
    # Below this cosine similarity nothing in the help center is relevant: skip the LLM entirely.
    retrieval_min_similarity: float = 0.55

    # Budgets: breaching any of them halts the AI step and hands off to a human.
    max_tokens_per_conversation: int = 60_000
    max_tokens_per_day: int = 2_000_000
    max_input_chars: int = 2_000
    classification_confidence_floor: float = 0.6

    rate_limit_per_minute: int = 30
    # Public demo only: lets operators reset demo bookings from the console. Never on real data.
    demo_mode: bool = False
    client_api_keys_raw: str = Field(default="", alias="CLIENT_API_KEYS")
    operator_api_keys_raw: str = Field(default="", alias="OPERATOR_API_KEYS")

    langfuse_public_key: str | None = None
    langfuse_secret_key: SecretStr | None = None
    langfuse_host: str = "https://cloud.langfuse.com"

    @field_validator("client_api_keys_raw", "operator_api_keys_raw")
    @classmethod
    def _validate_keys(cls, raw: str) -> str:
        _parse_named_keys(raw)
        return raw

    @property
    def client_api_keys(self) -> dict[str, SecretStr]:
        return _parse_named_keys(self.client_api_keys_raw)

    @property
    def operator_api_keys(self) -> dict[str, SecretStr]:
        return _parse_named_keys(self.operator_api_keys_raw)

    @property
    def tracing_enabled(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
