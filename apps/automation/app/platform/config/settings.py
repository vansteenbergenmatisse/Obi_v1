"""Environment-driven application settings.

Single source of truth for configuration. Loaded once and cached. Reads a repo-root or
app-local .env for local development; real deployments inject env vars directly.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.platform.config.knowledge_scopes import load_recognized_knowledge_scopes

if TYPE_CHECKING:
    from app.platform.config.platforms import PlatformRegistry

# Envs where a missing hosted-provider key or DB role falls back to a safe offline default
# instead of failing (PLAN 4.6.10) — was duplicated as a local constant in
# embeddings_client.py/reranker_client.py; both now call Settings.is_offline_env() instead.
_OFFLINE_ENVS = {"local", "test", "dev", "ci"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # runtime
    env: str = "local"
    log_level: str = "INFO"

    # database
    database_url: str = "postgresql+psycopg://rag:rag@localhost:5434/omniboost_rag"
    # non-owner rag_reader DSN for RLS-enforced retrieval reads (PLAN 3.5.3; ADR-0004).
    # Empty -> retrieval falls back to database_url (RLS is a no-op for a superuser/owner).
    database_reader_url: str = ""

    # confluence
    confluence_base_url: str = ""
    confluence_email: str = ""
    confluence_api_token: str = ""
    confluence_webhook_secret: str = ""
    confluence_service_account_id: str = ""
    confluence_breaker_threshold: int = 5  # consecutive failed calls -> open the fuse (PLAN 4.6.7)
    # attachment download caps (fixes/phase-2 wiring): bound memory/CPU against an oversized or
    # pathological attachment set. fileSize is checked (cheap, from metadata) before any bytes are
    # fetched; the streaming download also self-aborts past this cap regardless of what fileSize
    # claimed (defense in depth). No prior cap existed in this codebase to inherit — these are
    # deliberately generous safety ceilings, not a performance/scale claim.
    confluence_attachment_max_bytes: int = 20 * 1024 * 1024  # 20 MB per attachment
    confluence_attachment_max_per_page: int = 200  # attachments processed per page, per sync

    # models
    anthropic_api_key: str = ""
    routing_model: str = "claude-haiku-4-5-20251001"
    answer_model: str = "claude-sonnet-5"

    # embeddings (used from Phase 3)
    embedding_provider: str = "voyage"
    embedding_model: str = "voyage-3-large"
    embedding_dim: int = 1024
    voyage_api_key: str = ""
    openai_api_key: str = ""

    # embedding call controls (LLM-CALL security tier: C4 timeout/retry/breaker, C10 abuse cap)
    embedding_timeout_seconds: float = 30.0
    embedding_max_batch: int = 128  # texts per provider request
    embedding_max_retries: int = 3
    embedding_breaker_threshold: int = 5  # consecutive failed batches -> open the fuse
    embedding_max_texts_per_call: int = 20_000  # abuse guard on a single embed() invocation

    # contextualization call controls (LLM-CALL). Anthropic prompt-caches the document context.
    contextualization_enabled: bool = True
    contextualization_timeout_seconds: float = 30.0
    contextualization_max_retries: int = 2
    contextualization_max_doc_chars: int = 60_000  # cap document context sent to the model

    # reranker (PLAN 3.5.2). cross-encoder only — no general-LLM rerankers (ADR-0005).
    reranker_provider: str = ""  # cohere | fake | local ; "" -> fake offline
    reranker_api_key: str = ""
    reranker_model: str = "rerank-v3.5"  # hosted cross-encoder (Cohere v2)
    reranker_local_model: str = "BAAI/bge-reranker-base"

    # reranker depths + call controls (LLM-CALL security tier, mirrors embeddings)
    rerank_candidate_k: int = 75  # candidates fetched before rerank
    rerank_depth: int = 75  # max docs sent to the cross-encoder
    rerank_top_k: int = 5  # survivors returned
    rerank_timeout_seconds: float = 30.0
    rerank_max_retries: int = 3
    rerank_breaker_threshold: int = 5  # consecutive failed calls -> open the fuse
    rerank_max_docs: int = 1000  # C10 abuse cap on a single rerank() call

    # refusal threshold (PLAN 4, tuned from the 3.5.5 measurement). If the top survivor's
    # cross-encoder relevance score is below this, the answer runtime refuses ("not in the
    # docs") and routes to a human rather than hallucinate. Cohere rerank-v3.5 scores are in
    # [0, 1]. Provisional floor from the 3.5.5 fixture run; re-tune on the Phase-5 gold set.
    refusal_min_rerank_score: float = 0.10

    # answer workflow (PLAN 4.2)
    rewrite_enabled: bool = True  # conversational query rewrite (routing_model), always on
    crag_max_retries: int = 1  # corrective-retrieval cap on a weak first result (protects p95)

    # ambiguity/vagueness clarification branch (PLAN 9.2/9.3, ADR-0008). Off by default — an
    # ambiguous verdict now bypasses rewrite/retrieval/refusal and returns a clarifying question
    # on `Answer` (PLAN 9.3), so flipping this on is a real user-facing behavior change, not just
    # a logging toggle. Ships dark until tuned against `evaluation/datasets/ambiguity.json`
    # (PLAN 9.7).
    enable_clarification_branch: bool = False

    # answer-runtime Anthropic call controls (PLAN 4.4, LLM-CALL tier: C4 timeout/retry/breaker,
    # C10 abuse cap). Backs both the rewrite (routing_model) and generation (answer_model) calls —
    # they share one AnthropicMessagesClient instance built from these settings.
    answer_timeout_seconds: float = 30.0
    answer_max_retries: int = 2
    answer_breaker_threshold: int = 5  # consecutive failed calls -> open the fuse
    answer_max_input_chars: int = 20_000  # abuse cap on a single create_message() call

    # POST /chat + PATCH /chat/{trace_id}/feedback (PLAN 4.4). Both an HTTP and an LLM surface —
    # see securing-http-and-llm-endpoints controls in FEATURES.md / PLAN.md.
    chat_api_key: str = ""  # shared secret between the trusted web proxy and this API; fail-closed
    # accepted alongside chat_api_key during a rotation's overlap window (PLAN 5); empty = no
    # second key accepted. Drop back to "" once every caller has switched to the new chat_api_key.
    chat_api_key_previous: str = ""
    chat_rate_limit_per_minute: int = 20  # C2, keyed by client IP (never the caller-reported
    # principal alone — that would let a caller bypass the limit by rotating principal, PLAN 4.6.4)
    chat_rate_limiter_max_tracked_keys: int = 1000  # bounds in-process memory across distinct IPs
    chat_max_history_turns: int = 20  # C3/C10: caller-supplied conversation turns per request
    chat_max_message_chars: int = 4000  # C3: per-turn content length
    # PLAN 7.3/7.4, ADR-0009 decision 7: C3/C10 caps on the new `ChatMessage.images` field, folded
    # in alongside 7.3's LLM-call wiring rather than shipped separately — an uncapped image input
    # reaching a real vision call is a live cost/abuse surface the moment `images` exists, and
    # securing-http-and-llm-endpoints has no "add caps later" opt-out for an LLM-CALL surface.
    # chat_max_images_per_turn mirrors `apps/web/src/features/chat/ui/composer.tsx`'s existing,
    # already-shipped MAX_ATTACHMENTS=4 — a real cross-referenced value, not invented.
    # chat_max_image_bytes is a provisional ceiling under Anthropic's own documented ~5MB
    # per-image API limit (an external technical constraint, not an invented cost/scaling
    # number) — ADR-0009 explicitly leaves the *real*, usage-tuned value undecided; re-tune once
    # real image traffic exists.
    chat_max_images_per_turn: int = 4
    chat_max_image_bytes: int = 5_000_000
    chat_output_max_answer_chars: int = 8000  # C5: defensive cap on the streamed answer size
    chat_token_chunk_chars: int = 40  # C5: SSE token-event chunk size (paces bytes/sec streamed)
    chat_stream_interval_ms: int = 15  # C5: delay between SSE token events
    chat_idempotency_ttl_seconds: float = 300.0  # C7: Idempotency-Key replay window
    chat_idempotency_cache_max_entries: int = 500  # PLAN 4.6.4: bounds in-process memory, mirrors
    # chat_answer_cache_max_entries below (the idempotency cache had no bound before this fix)

    # PLAN 5: exact-match answer cache in front of AnswerService (answer_cache.py). Same TTL
    # default/shape as chat_idempotency_ttl_seconds — a bounded staleness tradeoff already
    # accepted there. Semantic caching is deliberately not built (see answer_cache.py docstring).
    chat_answer_cache_ttl_seconds: float = 300.0
    chat_answer_cache_max_entries: int = 500  # bounds in-process memory, not a cost/scale target

    # retrieval / budgets
    evidence_token_budget: int = 7000
    provider_timeout_seconds: float = 8.0

    # pgvector HNSW per-transaction knobs (PLAN 3.5.1). ef_search trades recall for latency;
    # iterative_scan (pgvector 0.8+) re-probes the index when an RLS/source predicate prunes
    # the candidate set, so a narrow scope still returns the full LIMIT. relaxed_order is safe
    # because we re-rank downstream. Set via SET LOCAL, so values are validated, not bound.
    hnsw_ef_search: int = 100
    hnsw_iterative_scan: str = "relaxed_order"  # off | relaxed_order | strict_order

    # reconciliation
    lightweight_recon_cron: str = "0 3 * * *"
    complete_recon_interval_days: int = 14

    # webhook ingress guards
    webhook_rate_limit_per_minute: int = 300
    webhook_max_body_bytes: int = 524_288  # 512 KiB
    worker_lease_seconds: int = 120

    # background scheduler + in-process worker (off unless explicitly enabled)
    enable_background_jobs: bool = False
    worker_tick_seconds: int = 5

    # pipeline version stamps (bumping these forces recompute / re-embed per ADR-0002)
    parser_version: int = 1
    chunker_version: int = 1
    # bumped to 3: the contextualizer discards LLM meta-refusals instead of baking them into
    # retrieval_content (PLAN 3b). v1 stored "I don't have access to the document…"; v2's detector
    # missed the "I cannot provide context … the document provided contains only …" phrasing seen
    # live (Opera/General re-embedded but stayed poisoned), so v3 widens the detector. The bump
    # routes every page through a full re-contextualize + re-embed on the next reconcile so the
    # corpus self-heals (index_config_change -> rebuild; diff-reuse disabled on a version mismatch).
    # Requires migration 0012 (the uq_document_version_idem widening) so a config-only rebuild at
    # the same cf_version does not collide.
    contextualization_version: int = 3
    retrieval_schema_version: int = 1

    # knowledge-scope tagging (PLAN 10.1; ADR-0011) — the recognized set of scope identifiers
    # itself lives in config/knowledge_scopes.json (see knowledge_scope_set below), not here;
    # this file only holds the runtime toggles for that feature.
    # deployment-level fallback scope when a chat request omits knowledge_scope (PLAN 10.5).
    # Empty -> obi-general-test-only.
    default_knowledge_scope: str = ""
    # rollout flag (PLAN 10.4). Off -> zero behavior change: HybridRetriever never applies the
    # `tags && ...` predicate regardless of what a caller passes, mirroring
    # enable_clarification_branch's dark-by-default posture.
    enable_knowledge_scope_filtering: bool = False
    # cap on always-present curated entries composed into evidence per answer (PLAN 10.6). Matches
    # rerank_top_k's order of magnitude — curated entries sit ahead of retrieved hits in the
    # numbered evidence block, so an unbounded cap could crowd out real retrieval evidence entirely.
    curated_knowledge_max_entries: int = 5

    # Obi embed platform registry (PLAN 11.1c; ADR-0014). The trusted-issuer + integration->scope
    # map itself lives in config/platforms.json (see platform_registry below), beside
    # knowledge_scopes.json; this file only holds where to read it and whether an empty registry
    # is tolerated. platforms_path empty -> the repo-root default. allow_empty_platforms is True
    # only in local/test (an empty registry stops startup in a real deployment).
    platforms_path: str = ""
    allow_empty_platforms: bool = False

    def is_offline_env(self) -> bool:
        """True in local/test/dev/ci — envs where a missing hosted key or DB role is a safe
        default-to-fake / default-to-writer fallback rather than a real deployment gap."""
        return self.env.lower() in _OFFLINE_ENVS

    @property
    def knowledge_scope_set(self) -> frozenset[str]:
        return load_recognized_knowledge_scopes()

    @property
    def platform_registry(self) -> PlatformRegistry:
        from app.platform.config.platforms import (
            DEFAULT_PLATFORMS_PATH,
            load_platform_registry,
        )

        path = Path(self.platforms_path) if self.platforms_path else DEFAULT_PLATFORMS_PATH
        return load_platform_registry(
            path, self.knowledge_scope_set, allow_empty=self.allow_empty_platforms
        )

    @model_validator(mode="after")
    def _require_general_knowledge_scope(self) -> Settings:
        _ = self.knowledge_scope_set  # fail fast at startup if the scopes config file is malformed
        return self

    @model_validator(mode="after")
    def _require_valid_platform_registry(self) -> Settings:
        # fail fast if platforms.json is malformed or maps unknown scopes
        _ = self.platform_registry
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
