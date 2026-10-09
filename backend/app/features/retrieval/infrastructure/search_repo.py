"""Dense (pgvector) and keyword (tsvector) candidate search over the active child index.

Both paths enforce the mandatory pre-model filters (active, child, current status, optional space)
in SQL. Dense search casts to ``halfvec`` for >2000-dim models to match the index. Results are
returned as ``(page_id, score)`` rows in rank order; a page may appear multiple times (once per
matching child) and is de-duplicated by the caller.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.features.retrieval.domain.applicability_match import EligibilityParams

_HALFVEC_MIN_DIM = 2001

# pgvector 0.8+ iterative-scan modes. Whitelisted because SET LOCAL cannot bind parameters,
# so the value is interpolated into SQL — an unchecked string here would be an injection point.
_ITERATIVE_SCAN_MODES = frozenset({"off", "relaxed_order", "strict_order"})


def apply_hnsw_gucs(session: Session, *, ef_search: int, iterative_scan: str) -> None:
    """Set the per-transaction pgvector HNSW knobs on ``session``.

    ``SET LOCAL`` scopes the change to the current transaction and takes effect only within
    it (the retriever never commits between this call and its searches, so it holds). It cannot
    bind parameters, so values are *validated*, not bound: ``ef_search`` is coerced to ``int``
    and ``iterative_scan`` is whitelisted, defaulting to ``relaxed_order`` on an unknown value.
    """
    ef = int(ef_search)
    mode = iterative_scan if iterative_scan in _ITERATIVE_SCAN_MODES else "relaxed_order"
    session.execute(text(f"SET LOCAL hnsw.ef_search = {ef}"))
    session.execute(text(f"SET LOCAL hnsw.iterative_scan = '{mode}'"))


def apply_source_scope(session: Session, allowed_sources: Sequence[str]) -> None:
    """Set the RLS scope GUC ``app.allowed_sources`` for this transaction (ADR-0004).

    Uses ``set_config(..., is_local=true)`` with a **bound** parameter: ``SET LOCAL`` cannot bind,
    and interpolating the caller's source list would be an injection vector or a silent
    default-deny. Scoped to the transaction, matching the searches that follow. An empty list
    yields an empty string -> the policy matches nothing -> default-deny.
    """
    session.execute(
        text("SELECT set_config('app.allowed_sources', :s, true)"),
        {"s": ",".join(allowed_sources)},
    )


# The '*' sentinel is an explicit opt-out from customer-scope RLS, distinct from an unset GUC (which
# the RESTRICTIVE `chunk_scope_read` policy reads as default-deny). Public retrieval always resolves
# a real scope list; only the internal/eval path (`knowledge_scopes is None`) sets '*' (ADR-0014).
KNOWLEDGE_SCOPE_WILDCARD = "*"


def apply_knowledge_scope(session: Session, allowed_scopes: Sequence[str] | None) -> None:
    """Set the customer/knowledge-scope RLS GUC ``app.allowed_knowledge_scopes`` for this txn.

    Enforces the customer-isolation backstop (ADR-0014, Phase 11.1a) **independent of the
    ``enable_knowledge_scope_filtering`` app-layer flag** — that flag only governs the redundant SQL
    predicate; RLS always enforces so a dropped predicate or a flag flip can no longer leak.

    * ``None`` -> the ``'*'`` wildcard (unrestricted; the internal/eval opt-out). NOT unset: an
      unset GUC fails closed and would return zero rows for every legacy caller.
    * a list -> bound and joined; the RESTRICTIVE policy overlaps ``chunk.tags`` against it. An
      empty list yields ``''`` -> the policy matches nothing -> default-deny (fail closed).

    Bound param, never interpolated (same injection-safety discipline as ``apply_source_scope``).
    Binding alone is not enough, though: the policy splits the GUC with ``string_to_array(.., ',')``
    and compares the whole value against ``'*'``, so a single *element* carrying an embedded comma
    would semantically widen to every scope it names, and a list joining to the literal ``'*'``
    would unlock the wildcard opt-out. Every production scope-GUC write funnels through here
    (search txn, parent expansion, curated), so this is the choke point: such an element is
    rejected before the join (fail closed — coverage gap G14).
    """
    if allowed_scopes is None:
        value = KNOWLEDGE_SCOPE_WILDCARD  # the intentional internal opt-out sentinel
    else:
        for scope in allowed_scopes:
            if "," in scope or KNOWLEDGE_SCOPE_WILDCARD in scope:
                raise ValueError(
                    f"invalid knowledge scope value {scope!r}: ',' and '*' would alter the "
                    "RLS scope predicate"
                )
        value = ",".join(allowed_scopes)
    session.execute(
        text("SELECT set_config('app.allowed_knowledge_scopes', :s, true)"),
        {"s": value},
    )


# ---------------------------------------------------------------------------------------------
# Substep 8.3.1 (panel mi-filter, plan.md §D.5): the applicability predicate, inside the same
# WHERE clause as the access filters — before ORDER BY/LIMIT, never a shortlist cleaned up later.
# It MIRRORS `domain.applicability_match.match_applicability` (the §D.4 semantics of record):
#   - a chunk with NO record (`applicability IS NULL`) keeps label-only behavior — absence never
#     excludes (§D.11 default);
#   - OR between rules, a rule with a `variants` requirement never matches at launch (never
#     assumes);
#   - general always matches; software/platform-interface match a FILLED slot (plus the verified
#     platform); connection/workflow rules must be satisfied by a connection the company actually
#     has — the bound `:elig_connections` JSON, derived from filled slots (plus real records),
#     with the explicit `any` binding to the connection's concrete product and every required
#     direction enabled on that SAME connection.
# All context values are BOUND (`:elig_products`, `:elig_platform`, `:elig_connections`) — never
# interpolated; the SQL text below is static. Malformed JSON shapes (impossible for stamped
# payloads, which pass the 8.2.1 validator) fail closed via jsonb_typeof guards.
# One documented bound vs. the Python matcher: the workflow distinct-assignment check is encoded
# as "every spec satisfied AND distinct satisfying connections >= specs", which is exactly
# Hall's condition for every launch-reachable input (derived connections are one-per-type; real
# records don't exist yet) and for every two-connection workflow; a 3+-spec workflow against
# multiple same-type REAL connection records would need a true matching — revisit when §D.1's
# richer context record lands (noted in docs/Final_docs/retrieval/eligibility-filtering.md).


def _sat_sql(spec: str, conn: str) -> str:
    """The `_satisfies` predicate in SQL: same type, every role side held by the SAME actual
    connection (`any` binds to its concrete product), every required direction enabled on it."""
    return (
        f"{spec}->>'type' = {conn}->>'type'"
        f" AND jsonb_typeof({spec}->'products') = 'object'"
        f" AND jsonb_typeof({spec}->'directions') = 'array'"
        f" AND NOT EXISTS (SELECT 1 FROM jsonb_each_text({spec}->'products') AS _p(prole, pwant)"
        f" WHERE {conn}->'products'->>_p.prole IS NULL"
        f" OR (_p.pwant <> 'any' AND _p.pwant <> {conn}->'products'->>_p.prole))"
        f" AND NOT EXISTS"
        f" (SELECT 1 FROM jsonb_array_elements_text({spec}->'directions') AS _d(dir)"
        f" WHERE NOT ({conn}->'directions' @> to_jsonb(_d.dir)))"
    )


_CONNS = "CAST(:elig_connections AS jsonb)"
_WF_CANDIDATE = "(NOT jsonb_exists(_r.rule, 'bindings') OR (_c.conn->>'derived')::boolean)"

_ELIGIBILITY_CLAUSE = (
    # No record = label-only behavior, in BOTH spellings: SQL NULL (the migration default the
    # sync path leaves untouched) and jsonb 'null' (what the ORM writes for a Python None —
    # JSONB none_as_null defaults off). Absence never excludes (§D.11).
    " AND (applicability IS NULL OR jsonb_typeof(applicability) = 'null'"
    " OR (jsonb_typeof(applicability) = 'array' AND EXISTS ("
    "SELECT 1 FROM jsonb_array_elements(applicability) AS _r(rule) "
    "WHERE NOT jsonb_exists(_r.rule, 'variants') AND ("
    "_r.rule->>'level' = 'general'"
    " OR (_r.rule->>'level' = 'software' AND _r.rule->>'product' = ANY(:elig_products))"
    " OR (_r.rule->>'level' = 'platform-interface'"
    " AND _r.rule->>'product' = ANY(:elig_products)"
    " AND _r.rule->>'platform' = :elig_platform)"
    " OR (_r.rule->>'level' = 'connection'"
    " AND jsonb_typeof(_r.rule->'connections') = 'array'"
    " AND jsonb_array_length(_r.rule->'connections') >= 1"
    f" AND EXISTS (SELECT 1 FROM jsonb_array_elements({_CONNS}) AS _c(conn)"
    f" WHERE {_sat_sql("_r.rule->'connections'->0", '_c.conn')}))"
    " OR (_r.rule->>'level' = 'workflow'"
    " AND jsonb_typeof(_r.rule->'connections') = 'array'"
    " AND jsonb_array_length(_r.rule->'connections') >= 2"
    " AND NOT EXISTS (SELECT 1 FROM jsonb_array_elements(_r.rule->'connections') AS _s(spec)"
    f" WHERE NOT EXISTS (SELECT 1 FROM jsonb_array_elements({_CONNS}) AS _c(conn)"
    f" WHERE {_WF_CANDIDATE} AND {_sat_sql('_s.spec', '_c.conn')}))"
    " AND (SELECT count(DISTINCT _c.conn->>'index')"
    " FROM jsonb_array_elements(_r.rule->'connections') AS _s(spec),"
    f" jsonb_array_elements({_CONNS}) AS _c(conn)"
    f" WHERE {_WF_CANDIDATE} AND {_sat_sql('_s.spec', '_c.conn')})"
    " >= jsonb_array_length(_r.rule->'connections'))"
    "))))"
)


def _eligibility_bind_params(eligibility: EligibilityParams) -> dict[str, object]:
    """The three bound values the clause consumes — values only, never SQL text."""
    return {
        "elig_products": list(eligibility.products),
        "elig_platform": eligibility.platform,
        "elig_connections": json.dumps(
            [
                {
                    "index": index,
                    "type": conn.connection_type,
                    "products": dict(conn.products),
                    "directions": list(conn.directions),
                    "derived": conn.derived,
                }
                for index, conn in enumerate(eligibility.connections)
            ]
        ),
    }


def _base_filters(
    space_id: int | None,
    sources: Sequence[str] | None,
    knowledge_scopes: Sequence[str] | None = None,
    eligibility: EligibilityParams | None = None,
) -> str:
    clause = "is_active AND kind = 1 AND page_status = 'current'"
    if space_id is not None:
        clause += " AND space_id = :space_id"
    if sources is not None:
        # explicit source filter alongside RLS: correctness + recall, and lets the planner use
        # ix_chunk_active_source. RLS is the security net; this is the query's own predicate.
        clause += " AND source_id = ANY(:sources)"
    if knowledge_scopes is not None:
        # PLAN 10.4 / ADR-0011: array-overlap against the tags GIN index (0007_knowledge_scope).
        # Bound, never interpolated — same discipline as `sources` above. A chunk with no
        # knowledge-scope tag at all (empty array) overlaps nothing, so it does not participate
        # (Decision 1: "no recognized tag -> does not participate", not a silent fallback-visible).
        clause += " AND tags && :knowledge_scopes"
    if eligibility is not None:
        # 8.3.1: applicability narrows INSIDE what access already allows — RLS and the scope
        # predicates above are untouched and still apply first (never-bend rule 3).
        clause += _ELIGIBILITY_CLAUSE
    return clause


# Natural-language questions rarely have every term in one short chunk, so plainto_tsquery's
# implicit AND matches nothing. Convert it to an OR query (any term matches) and let ts_rank order
# by how well each chunk matches — Postgres does the lexemization, so this stays injection-safe.
_OR_TSQUERY = "replace(plainto_tsquery('english', :q)::text, '&', '|')::tsquery"


def keyword_search(
    session: Session,
    query: str,
    space_id: int | None,
    limit: int,
    sources: Sequence[str] | None = None,
    knowledge_scopes: Sequence[str] | None = None,
    eligibility: EligibilityParams | None = None,
) -> list[tuple[int, float]]:
    sql = text(
        f"SELECT page_id, ts_rank(tsv, {_OR_TSQUERY}) AS score "
        f"FROM chunk "
        f"WHERE {_base_filters(space_id, sources, knowledge_scopes, eligibility)} "
        f"AND tsv @@ {_OR_TSQUERY} "
        f"ORDER BY score DESC, page_id ASC LIMIT :limit"
    )
    params: dict[str, object] = {"q": query, "limit": limit}
    if space_id is not None:
        params["space_id"] = space_id
    if sources is not None:
        params["sources"] = list(sources)
    if knowledge_scopes is not None:
        params["knowledge_scopes"] = list(knowledge_scopes)
    if eligibility is not None:
        params.update(_eligibility_bind_params(eligibility))
    return [(int(pid), float(score)) for pid, score in session.execute(sql, params)]


def _vector_literal(vec: Sequence[float]) -> str:
    return "[" + ",".join(repr(float(x)) for x in vec) + "]"


def dense_search(
    session: Session,
    query_vec: Sequence[float],
    space_id: int | None,
    limit: int,
    dim: int,
    sources: Sequence[str] | None = None,
    knowledge_scopes: Sequence[str] | None = None,
    eligibility: EligibilityParams | None = None,
) -> list[tuple[int, float]]:
    # >2000-dim models are indexed as halfvec; cast both sides so the ANN index is used.
    if dim >= _HALFVEC_MIN_DIM:
        lhs = f"embedding::halfvec({dim})"
        rhs = f"CAST(:qvec AS halfvec({dim}))"
    else:
        lhs = "embedding"
        rhs = "CAST(:qvec AS vector)"
    sql = text(
        f"SELECT page_id, ({lhs} <=> {rhs}) AS dist "
        f"FROM chunk "
        f"WHERE {_base_filters(space_id, sources, knowledge_scopes, eligibility)} "
        f"AND embedding IS NOT NULL "
        f"ORDER BY dist ASC, page_id ASC LIMIT :limit"
    )
    params: dict[str, object] = {"qvec": _vector_literal(query_vec), "limit": limit}
    if space_id is not None:
        params["space_id"] = space_id
    if sources is not None:
        params["sources"] = list(sources)
    if knowledge_scopes is not None:
        params["knowledge_scopes"] = list(knowledge_scopes)
    if eligibility is not None:
        params.update(_eligibility_bind_params(eligibility))
    return [(int(pid), float(dist)) for pid, dist in session.execute(sql, params)]


@dataclass(frozen=True)
class RerankCandidate:
    """One page's representative child chunk, ready for the cross-encoder + later grounding.

    ``applicability`` carries the chunk's stamped payload (the §D.4 rules) when a verified
    context is present, so the retriever can build the 8.3.2 YAML enrichment block; it stays
    ``None`` on the no-context path (and for a label-only chunk), leaving the reranker document
    byte-identical to the pre-8.3.2 shape."""

    chunk_id: int
    title: str
    source_url: str
    text: str
    applicability: Sequence[Mapping[str, object]] | None = None


def fetch_rerank_texts(
    session: Session,
    page_ids: Sequence[int],
    space_id: int | None,
    sources: Sequence[str] | None = None,
    knowledge_scopes: Sequence[str] | None = None,
    eligibility: EligibilityParams | None = None,
) -> dict[int, RerankCandidate]:
    """One representative child chunk per page for the cross-encoder, keyed by page id.

    The retriever deals in page ids; reranking needs text, and Phase 4 grounding needs that same
    chunk's id (to join its parent) plus title/url (for citations) — one query serves all three,
    keyed by page id. Picks the earliest active child chunk under the same pre-model filters as
    search (including 8.3.1 eligibility), so a page the filters would exclude never gets
    reranked in.
    """
    if not page_ids:
        return {}
    # 8.3.2 (panel mi-rerank): the stamped applicability payload rides along ONLY on the
    # context path (eligibility present), so the retriever can build the YAML enrichment. The
    # no-context/internal/eval path selects the exact pre-8.3.2 columns — the word
    # "applicability" never enters that SQL, keeping the 8.3.1 byte-for-byte guarantee.
    select_applicability = eligibility is not None
    columns = (
        "page_id, id AS chunk_id, title, source_url, "
        "left(title || ' ' || retrieval_content, 4000) AS txt"
    )
    if select_applicability:
        columns += ", applicability"
    sql = text(
        f"SELECT DISTINCT ON (page_id) {columns} "
        f"FROM chunk "
        f"WHERE {_base_filters(space_id, sources, knowledge_scopes, eligibility)} "
        f"AND page_id = ANY(:page_ids) "
        f"ORDER BY page_id, seq"
    )
    params: dict[str, object] = {"page_ids": list(page_ids)}
    if space_id is not None:
        params["space_id"] = space_id
    if sources is not None:
        params["sources"] = list(sources)
    if knowledge_scopes is not None:
        params["knowledge_scopes"] = list(knowledge_scopes)
    if eligibility is not None:
        params.update(_eligibility_bind_params(eligibility))
    out: dict[int, RerankCandidate] = {}
    for row in session.execute(sql, params):
        if select_applicability:
            pid, cid, title, url, txt, payload = row
        else:
            pid, cid, title, url, txt = row
            payload = None
        out[int(pid)] = RerankCandidate(
            chunk_id=int(cid),
            title=str(title),
            source_url=str(url),
            text=str(txt),
            applicability=payload if isinstance(payload, list) else None,
        )
    return out


def fetch_page_scopes(
    session: Session, page_ids: Sequence[int]
) -> tuple[dict[int, int], dict[int, set[str]]]:
    """Space id + persisted restricted-principal set for each candidate page (PLAN 4.3).

    Loaded fresh per search, scoped to the fused candidate set — never the whole corpus. A page's
    principal list can change on any sync, so pre-loading it once at retriever construction would
    go stale; this feeds a request-scoped ``PrincipalPermissionPolicy`` instead. A page with no
    ``page_restriction`` rows is unrestricted, matching that policy's existing pure contract.
    """
    if not page_ids:
        return {}, {}
    space_of = {
        int(pid): int(space_id)
        for pid, space_id in session.execute(
            text("SELECT page_id, space_id FROM page_source WHERE page_id = ANY(:page_ids)"),
            {"page_ids": list(page_ids)},
        )
    }
    restrictions: dict[int, set[str]] = {}
    for pid, principal in session.execute(
        text("SELECT page_id, principal FROM page_restriction WHERE page_id = ANY(:page_ids)"),
        {"page_ids": list(page_ids)},
    ):
        restrictions.setdefault(int(pid), set()).add(str(principal))
    return space_of, restrictions


def fetch_parent_context(session: Session, chunk_ids: Sequence[int]) -> dict[int, str]:
    """Each child chunk's parent verbatim text, keyed by the *child* chunk id.

    Children retrieve, parents ground (PLAN 4.2): the generator is fed the parent's
    ``display_content`` for surrounding context, not the narrow child window that matched. No
    extra scope filter is needed — a chunk id here already came from a scoped, permitted search,
    and its parent shares the same page/doc-version. A child whose parent is missing (should not
    happen post-ingestion, but the FK is nullable) is simply absent from the result.
    """
    if not chunk_ids:
        return {}
    sql = text(
        "SELECT c.id AS child_id, p.display_content AS parent_text "
        "FROM chunk c JOIN chunk p ON p.id = c.parent_chunk_id "
        "WHERE c.id = ANY(:chunk_ids)"
    )
    rows = session.execute(sql, {"chunk_ids": list(chunk_ids)})
    return {int(cid): str(txt) for cid, txt in rows}
