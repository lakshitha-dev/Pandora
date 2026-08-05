"""Application configuration.

One place, validated at startup, fails loudly on a missing key.
Never call os.getenv() anywhere else in the codebase.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed settings for the Pandora agent service."""

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Azure AI Foundry (Azure OpenAI) ──────────────────────────────────
    # The base host is <resource>.services.ai.azure.com. The
    # <resource>.openai.azure.com host does NOT exist for a Foundry resource
    # and returns 404 — verified against this deployment.
    azure_openai_endpoint: str
    azure_openai_api_key: str
    azure_openai_api_version: str = "2024-10-21"
    azure_openai_chat_deployment: str
    azure_openai_embedding_deployment: str

    # gpt-5-mini is a reasoning model. When true the chat client sends
    # max_completion_tokens (not max_tokens) and omits temperature, because
    # any value other than the default 1 is rejected with HTTP 400.
    is_reasoning_model: bool = True
    chat_max_completion_tokens: int = 16000

    # ── Azure AI Search ──────────────────────────────────────────────────
    # Admin key required: the query key is read-only and cannot create an
    # index or upload documents.
    azure_search_endpoint: str
    azure_search_api_key: str
    azure_search_index_name: str = "pandora-knowledge"

    # ── Internal auth ────────────────────────────────────────────────────
    agent_service_key: str = "dev-internal-key-change-me"

    # ── Retrieval ────────────────────────────────────────────────────────
    retrieval_candidate_k: int = 30
    retrieval_top_k: int = 6
    rerank_score_threshold: float = 0.45

    # ── Agentic layer ────────────────────────────────────────────────────
    # SOLUTION.md §5.5 specifies 8 s per specialist and a 25 s total budget,
    # but those numbers assume gpt-4o-mini. This deployment runs gpt-5-mini,
    # a reasoning model that spends a variable share of its budget thinking
    # before it emits a token — measured at ~25 s for a single rerank call.
    # At 8 s every specialist times out and the parallel path never runs, so
    # the limits are raised and left env-tunable. The *structure* of §5.5 is
    # unchanged: fixed caps, enforced by counters in orchestrator state.
    agentic_enabled: bool = True
    agent_timeout_seconds: int = 75
    orchestration_budget_seconds: int = 180
    max_retries: int = 1
    max_llm_calls_per_query: int = 8

    # Serves cached responses for the demo questions — zero API dependency.
    demo_mode: bool = False

    # ── Corpus ───────────────────────────────────────────────────────────
    corpus_path: str = "../Pandora_RAG_Knowledge_2026.md"

    log_level: str = "INFO"

    embedding_dimensions: int = Field(
        default=1536,
        description="text-embedding-3-small output size. Must match the index.",
    )

    @property
    def corpus_file(self) -> Path:
        """Absolute path to the Pandora knowledge corpus markdown."""
        p = Path(self.corpus_path)
        if p.is_absolute():
            return p
        return (Path(__file__).resolve().parents[2] / p).resolve()


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton. Raises at startup if a key is missing."""
    return Settings()  # type: ignore[call-arg]
