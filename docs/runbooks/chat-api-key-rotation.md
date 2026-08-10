# Runbook — rotating `CHAT_API_KEY`

`CHAT_API_KEY` is the shared secret between `apps/web`'s server-side chat proxy
(`platform/automation-api`) and `apps/automation`'s `POST /chat` / `PATCH /chat/{traceId}/feedback`
(`_verify_api_key`, `app/features/rag_agent/server/router.py`). It is never sent to the browser and
never logged (see the endpoint's `security_baseline` docstring, C1/C9).

## Why not a naive swap

The key lives in two separate `.env` files (root `.env` for `apps/automation`, `apps/web/.env.local`
for the proxy). Writing a new value to both is never atomic — restarting one process before the
other, or a deploy that updates one env and not the other, causes every chat request to 401 until
they agree. The fix is a bounded **overlap window**: the API accepts the current key *and* the
previous key at the same time, so either process can be updated first without an outage.

## Mechanism

- `Settings.chat_api_key` (current) and `Settings.chat_api_key_previous` (optional, empty by
  default) are both checked, in constant time, on every request. Either one authenticates.
- The web proxy only ever sends **one** key (`CHAT_API_KEY` in `apps/web/.env.local`) — it never
  needs the previous value; only the verifying side (`apps/automation`) needs to accept both.

## Recommended cadence

This is a private, server-to-server secret — never browser-exposed, never shared with a third
party. The threat model that justifies **weekly** rotation is for client-exposed or
third-party-shared credentials; it doesn't apply here. Recommended cadence is **monthly or
quarterly**, or on suspected compromise. If you have a specific compliance requirement for a
shorter cycle (e.g. weekly), the mechanism below supports any cadence — just run it more often,
ideally from a scheduler once there's a real deploy target (Phase 6).

## Procedure

1. **Rotate in the new key** (from `apps/automation`):

   ```
   uv run python scripts/rotate_chat_api_key.py --apply
   ```

   This writes a fresh 64-char hex key as `CHAT_API_KEY` in both `.env` and
   `apps/web/.env.local`, and moves the *old* value into `CHAT_API_KEY_PREVIOUS` (still accepted).

2. **Restart both processes** so they pick up the new env:

   ```
   # automation
   uvicorn app.main:app
   # web
   pnpm --filter web dev   # or your deployed process manager's restart
   ```

3. **Verify** the chat UI still works end to end (send a message, confirm a streamed answer).
   Both the new key (now `CHAT_API_KEY`) and the old key (now `CHAT_API_KEY_PREVIOUS`) are valid
   during this window — a caller that hasn't picked up the new value yet still authenticates.

4. **Close the window** once every caller (in practice: just the one `apps/web` proxy today) is
   confirmed on the new key:

   ```
   uv run python scripts/rotate_chat_api_key.py --finish
   ```

   This blanks `CHAT_API_KEY_PREVIOUS` — the old key stops working. Restart `apps/automation`
   once more to pick this up (an empty `chat_api_key_previous` never matches, since
   `_verify_api_key` requires a non-empty token).

## On a real deployment (Phase 6+)

Steps 1–4 assume local `.env` files. Once there's a real deploy target, replace the file-editing
half of `scripts/rotate_chat_api_key.py` with whatever secret store the platform uses (e.g. a
secrets manager), keeping the same two-step overlap-window shape — generate a new key, set
`CHAT_API_KEY_PREVIOUS`/`CHAT_API_KEY`, redeploy, verify, then close the window. Do not skip the
overlap step even in a "fast" deploy pipeline; that is exactly the naive swap this runbook exists
to avoid.
