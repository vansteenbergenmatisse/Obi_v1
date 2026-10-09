"""Context-aware rerank request construction (panel mi-rerank, substep 8.3.2) — §D.6.

The Cohere v2 ``/rerank`` API carries no instruction / context field in any version
(``docs/Final_docs/5-integration-context/research-rerank-api.md``), so the only way to tell
the cross-encoder *who is asking* is to put it in the two string inputs it does accept:

* **(a)** the verified customer context prepended to the ``query`` string, and
* **(b)** a short YAML applicability block ahead of each document's text.

These are **pure request-construction** helpers, not a prompt — no model is asked to reason,
reorder or generate here (ADR-0005 keeps the reranker a cross-encoder), so this lives in the
retrieval domain and no prompt text leaves ``rag_agent``. Eligibility is already enforced in
the search SQL (8.3.1); enrichment only changes how the already-eligible candidates are
*scored and ordered* — it never widens the set.

Caps (from the research memo):

* the query is capped at **2,048 tokens** on ``rerank-v3.5``. The user question is NEVER
  truncated — the preamble yields first — because a truncated question would change the
  retrieval intent. Token length is estimated conservatively at ~4 characters/token (an
  industry heuristic, not an API-reported number; the v2 client adds no tokenizer).
* each document is capped at **4,000 characters**, metadata-first: the YAML block leads so it
  always survives, and only the body tail is truncated.

The YAML derives from the stamped applicability payload (the page-authored "Applies to"
table, validated against the catalog vocabulary at stamp time, 8.2.1) plus the chunk's
matched eligibility reason — no new vocabulary. Page-authored values are treated as untrusted
text: every scalar is sanitized (newlines/control characters stripped, length bounded) so a
hostile value cannot introduce a second YAML line, and the block is only ever sent as a
cross-encoder document string — never executed, never interpolated into SQL.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from app.features.retrieval.domain.applicability_match import CustomerContext

_QUERY_TOKEN_CAP = 2048
# Conservative English chars-per-token estimate (OpenAI/Cohere guidance), not an API number;
# used only to decide when the (tiny) preamble must yield so the question stays whole.
_CHARS_PER_TOKEN = 4
_QUERY_CHAR_BUDGET = _QUERY_TOKEN_CAP * _CHARS_PER_TOKEN
_DOC_CHAR_CAP = 4000
_MAX_SCALAR = 64


def context_preamble(context: CustomerContext) -> str:
    """One verified-context line for the rerank query.

    Only the filled §D.13 slots and a known host platform — all public catalog vocabulary.
    Never a company id, token or any secret (rule 10). An empty (slotless) context yields the
    empty string so the no-context path stays byte-identical to the pre-8.3.2 query.
    """
    parts: list[str] = []
    if context.slot_pos:
        parts.append(f"POS={context.slot_pos}")
    if context.slot_pms:
        parts.append(f"PMS={context.slot_pms}")
    if context.slot_accounting:
        parts.append(f"Accounting={context.slot_accounting}")
    if context.platform:
        parts.append(f"platform={context.platform}")
    if not parts:
        return ""
    return "Customer setup: " + "; ".join(parts) + "."


def build_rerank_query(preamble: str, question: str, char_budget: int = _QUERY_CHAR_BUDGET) -> str:
    """Prepend ``preamble`` to ``question``; the question is never truncated.

    An empty preamble returns the bare question. If the combined string would exceed the query
    cap the preamble yields — shortened to fit alongside the whole question, or dropped
    entirely when the question alone already fills the budget.
    """
    if not preamble:
        return question
    combined = f"{preamble}\n\n{question}"
    if len(combined) <= char_budget:
        return combined
    room = char_budget - len(question) - 2
    if room <= 0:
        return question  # the question wins the whole budget; no room for any preamble
    return f"{preamble[:room]}\n\n{question}"


def _scalar(value: object) -> str:
    """Sanitize a page-authored (untrusted) value for a single YAML scalar: collapse any
    newline/carriage return to a space, drop other control characters, bound the length."""
    text = "".join(ch if ch >= " " else " " for ch in str(value))
    return " ".join(text.split())[:_MAX_SCALAR]


def applicability_yaml(payload: Sequence[Mapping[str, object]] | None, reason: str | None) -> str:
    """A short YAML applicability block built from the stamped payload + the matched reason.

    Returns the empty string for a chunk with no applicability record (a label-only page): its
    document body is then left unchanged. Only the stamped vocabulary is serialized — ``level``,
    ``product``, ``platform`` and each connection's ``type``/``products``/``directions`` — plus
    the matched-rule reason slug.
    """
    if not payload:
        return ""
    lines = ["applies-to:"]
    for rule in payload:
        if not isinstance(rule, Mapping):
            continue
        lines.append(f"- level: {_scalar(rule.get('level'))}")
        if rule.get("product") is not None:
            lines.append(f"  product: {_scalar(rule.get('product'))}")
        if rule.get("platform") is not None:
            lines.append(f"  platform: {_scalar(rule.get('platform'))}")
        connections = rule.get("connections")
        if isinstance(connections, Sequence) and not isinstance(connections, str):
            for spec in connections:
                if not isinstance(spec, Mapping):
                    continue
                ctype = _scalar(spec.get("type"))
                products = spec.get("products")
                prod = (
                    ",".join(
                        f"{_scalar(role)}:{_scalar(pid)}" for role, pid in sorted(products.items())
                    )
                    if isinstance(products, Mapping)
                    else ""
                )
                directions = spec.get("directions")
                dirs = (
                    ",".join(_scalar(d) for d in directions)
                    if isinstance(directions, Sequence) and not isinstance(directions, str)
                    else ""
                )
                lines.append(f"  connection: {ctype} [{prod}] ({dirs})")
    if reason:
        lines.append(f"matched-rule: {_scalar(reason)}")
    return "\n".join(lines)


def build_rerank_document(yaml_block: str, body: str, char_cap: int = _DOC_CHAR_CAP) -> str:
    """Compose the reranker document: the YAML block leads, the body (title + the exact matched
    child content, rule 6) follows, and the whole string is capped so the metadata survives —
    only the body tail is truncated. An empty YAML block returns the capped body unchanged."""
    if not yaml_block:
        return body[:char_cap]
    return f"{yaml_block}\n{body}"[:char_cap]
