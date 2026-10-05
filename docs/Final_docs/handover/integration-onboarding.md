# Integration onboarding & offboarding — adding or removing a platform, end to end

> **Audience:** whoever connects a new platform (PMS/POS) to Obi, or disconnects one.
> **Living doc:** describes the system as proven on 2026-10-03. The §15 multi-scope decision and
> roadmap Step 5 will change flagged parts — update this file in those substeps.

An *integration* is a platform whose customers get a scoped Obi widget: the platform signs a short
token ("the note") for each user, the widget sends it, and the backend derives from it exactly which
knowledge scopes that user may search. Everything below follows from that one mechanism.

## Adding an integration (say, Cloudbeds)

**1. Give it a scope** — follow `tag-administration.md` → "Adding a scope" (new entry in
`knowledge_scopes.json`). One integration ↔ one scope is today's model (see the flag at the bottom).

**2. Register the platform in `knowledge-base/config/platforms.json`** — the platform entry (issuer
URL, JWKS location, allowed integrations, token lifetime, allowed algorithms, `active: true`) and
the integration→scope mapping. The loader enforces at boot: mapped scopes must exist in
`knowledge_scopes.json`; `classified` is never mappable; `obi-general-test` is never hand-listed
(every integration gets it automatically); lifetime 1–1440 minutes; outside local dev the issuer
must be HTTPS and non-loopback. Production uses `platforms.json`; local testing uses
`platforms.local.json` + the `/test-hosts/*` fake issuers.

**3. Deploy** — commit, redeploy the backend (the platform registry is cached in-process: **a file
edit without restart does nothing**, by design), rebuild the widget (`pnpm --filter web build:obi`).

**4. Platform side** — they embed the widget and mint the note:
```html
<script src="…/obi.js"></script>
<script>Obi.init({ tokenUrl: "/their-endpoint/obi-token" });</script>
```
Their token endpoint returns a short-lived RS256 JWT with the agreed claims (issuer, kid,
company_id, company_name, integration) signed by a key whose **public JWKS is served at the issuer
URL registered in step 2** — the backend's TokenVerifier fetches it from there. The local test-host
pages (`frontend/src/app/test-hosts/`, keys in `frontend/.env.local`) are the working reference
implementation. Remember: locally-signed test tokens verify only against a locally-run backend —
the deployed backend can't reach a laptop's JWKS.

**5. Label content** — tag the integration's Confluence pages with its scope
(see `tagging-guide.md`; mind the finding-A workaround in `tag-administration.md` for pages that
carried the label before the scope existed).

**6. Verify, in order** — `/health` lists the new scope · a token from the platform answers a
question only the new scope's content can answer, with a citation · the same question **without** a
token (or with another platform's token) refuses · trash/label round-trip on one test page behaves
per `tagging-guide.md`.

## Removing an integration

1. Remove the integration (or set the platform `active: false`, or delete the platform entry) in
   `platforms.json`; commit + **restart/redeploy** — nothing changes until the restart. From that
   moment every one of its tokens is a clean **401** on the next request (unknown issuer / unknown
   integration / not-allowed / inactive — all four gates are tested). Tokens are stateless, so there
   is nothing else to revoke.
2. The platform removes the widget embed from their product (cosmetic — the backend already
   refuses).
3. Content: pages tagged **only** with its scope are now unreachable by every customer; either leave
   them (dead weight) or untag/retag them in Confluence. To retire the scope itself, follow
   `tag-administration.md` → "Removing a scope" (ordering matters: platforms.json first).
4. Old `query_trace` rows keep their historical scope values — they're an audit record, nothing
   re-interprets them.

## Flagged: things that will change

- **⚠ §15 multi-scope (decision pending):** today an integration maps to its scope(s) statically,
  and a property that is both POS + PMS (e.g. Toast + Mews) has no way to get both scopes from one
  note. The owner-chosen direction (list-in-token-claim vs precedence) lands with its own
  regression-floor test waves (`docs/Final_docs/sync-rules/plan.md` §15–15.2) — step 4 of "Adding"
  above gets rewritten then.
- **⚠ Step 5 restamp fix:** shrinks the finding-A/B caveats referenced in steps 1 and 5.
