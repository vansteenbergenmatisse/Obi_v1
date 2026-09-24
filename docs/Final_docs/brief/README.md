# Brief — operator runbooks for embedding Obi

Short, do-this-now runbooks for wiring Obi into another company's software. Each one names the exact
files you edit and links to the code that enforces the behaviour, so a maintainer can follow it
without re-reading the whole codebase. These are the brief runbooks referenced by the
Phase-4 embed-security clean-exit criteria (the mandate names them the docs/brief runbooks; they
live here under `docs/Final_docs/brief/`).

| Runbook | Use it when |
|---|---|
| [`add-an-integration.md`](./add-an-integration.md) | adding an underlying software the customer runs (mews / toast / opera-cloud style) — a new `integration` claim value and its knowledge scope. Pure config. |
| [`add-a-host-platform.md`](./add-a-host-platform.md) | adding a place that embeds the widget and mints JWTs (datahub / base style) — a new trusted issuer. Config now, real values later. |
| [`localhost-test.md`](./localhost-test.md) | reproducing the full embed flow on your own localhost with throwaway keys — mint a token, load the widget, get a scoped answer, prove isolation. |

## The two buckets

Everything about going live splits cleanly in two:

### Bucket 2 — what we can do ourselves, right now (these runbooks)
- Add an integration (scope + mapping + allow-list + Confluence labels).
- Add a host platform entry as `active: false` (staged, verified-but-denied).
- Prove the entire embed path on localhost with self-signed test keys.
- Write the regression tests that protect each of the above.

### Bucket 1 — what needs the external platform's developers (cannot be done locally)
- The platform's real `issuer`, `jwks_url`, and browser `domains`.
- A token endpoint that mints a ≤60-min RS256/ES256 JWT with `iss` / `aud=obi` / `sub` / `iat` /
  `exp` + the all-or-none `company_id` / `company_name` / `integration` trio.
- A real staging token verified end to end, and migration `0010` applied in a pre-production DB.

The full go-live register (what changes on our side, what must come from them, and what is
deliberately out of scope for v1) lives in `docs/future-ideas.md` under **"Integration with other
software — putting Obi live in a host platform."** The developer-facing hand-over packs are in
`docs/embedding/` (`datahub.md`, `base.md`, `mews.md`, `toast.md`, `opera-cloud.md`).

## Rules these runbooks never break
- The request body never decides access — scope/integration come only from the verified JWT.
- Active production platforms must be real `https` issuers; the trust guard rejects
  placeholder / non-https / loopback / `.local` and fails closed.
- One canonical config source: `knowledge-base/config/knowledge_scopes.json` (scopes) and
  `platforms.json` (platforms + integration mapping). No second hand-maintained list.
- No change without its test; no retrieval change without a before/after gold-set number.
