#!/usr/bin/env bash
# Obi · quick "test online" tunnel for the embed widget (self-only, general-only).
#
# Exposes the LOCAL Next.js frontend (:3100) on a public HTTPS URL via a cloudflared
# quick tunnel, so you can open the widget in a browser over the internet. Only the
# frontend is tunneled — the backend stays on localhost:8000 (the Next server reaches
# it server-side via AUTOMATION_API_BASE_URL), so nothing internal is exposed.
#
# Why it edits the registry: the frontend derives its embed CSP `frame-ancestors` and
# its postMessage origin allow-list from the ACTIVE platform `domains` in
# knowledge-base/config/platforms.local.json, and local/dev mode adds NO wildcard and
# NO 'self'. So a tunnel hostname is blocked (iframe won't load, obi:open rejected)
# until it is in that list. cloudflared quick tunnels get a fresh random hostname each
# run, so this script injects that hostname for the session and restores the file
# verbatim on exit. The frontend re-reads the file per request — no restart, no rebuild.
#
# Prereqs (two OTHER terminals):
#   make api         # backend (FastAPI) on :8000
#   make embed-dev   # frontend (Next.js) on :3100 — builds obi.js, scope switcher on
# Then:
#   make tunnel      # or: scripts/tunnel-embed-test.sh
# Open the printed https URL at /test-hosts/none and click the launcher. Ctrl-C to stop.

set -euo pipefail

PORT="${1:-3100}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REG="$ROOT/knowledge-base/config/platforms.local.json"
LOG="$(mktemp -t obi-tunnel.XXXXXX)"
BAK="$(mktemp -t obi-reg.XXXXXX)"
CF_PID=""
_CLEANED=0

command -v cloudflared >/dev/null 2>&1 || { echo "cloudflared not found — install with: brew install cloudflared"; exit 1; }
command -v python3     >/dev/null 2>&1 || { echo "python3 not found (needed to edit the registry)."; exit 1; }
[ -f "$REG" ] || { echo "registry not found: $REG"; exit 1; }

cleanup() {
  [ "$_CLEANED" = 1 ] && return
  _CLEANED=1
  echo
  echo "→ stopping tunnel + restoring registry…"
  [ -n "$CF_PID" ] && kill "$CF_PID" 2>/dev/null || true
  [ -f "$BAK" ] && cp "$BAK" "$REG" && echo "  restored $REG"
  rm -f "$LOG" "$BAK"
}
trap cleanup EXIT INT TERM

cp "$REG" "$BAK"   # snapshot to restore verbatim on exit

# soft preflight — warn, don't block (servers may still be starting)
curl -sf -o /dev/null "http://localhost:$PORT/test-hosts/none" \
  || echo "⚠  frontend not answering on :$PORT yet — start it with 'make embed-dev' (this is the port that gets tunneled)."
curl -sf -o /dev/null "http://localhost:8000/" \
  || echo "⚠  backend not answering on :8000 yet — start it with 'make api' (answers 404 at / is fine; connection refused is not)."

echo "→ starting cloudflared quick tunnel to http://localhost:$PORT …"
cloudflared tunnel --url "http://localhost:$PORT" --no-autoupdate >"$LOG" 2>&1 &
CF_PID=$!

# capture the assigned https://<random>.trycloudflare.com (printed to cloudflared's log)
URL=""
for _ in $(seq 1 40); do
  URL="$(grep -Eo 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG" | head -n1 || true)"
  [ -n "$URL" ] && break
  # bail early if cloudflared already died
  kill -0 "$CF_PID" 2>/dev/null || { echo "cloudflared exited early. Log:"; cat "$LOG"; exit 1; }
  sleep 0.5
done
[ -n "$URL" ] || { echo "could not obtain a tunnel URL in time. cloudflared log:"; cat "$LOG"; exit 1; }
HOST="${URL#https://}"

# inject the tunnel host into every active entry's `domains` (bare host, no scheme/port)
python3 - "$REG" "$HOST" <<'PY'
import json, sys
path, host = sys.argv[1], sys.argv[2]
with open(path) as f:
    data = json.load(f)
for entry in data.get("platforms", {}).values():
    if entry.get("active"):
        doms = entry.setdefault("domains", [])
        if host not in doms:
            doms.append(host)
with open(path, "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
PY

echo
echo "════════════════════════════════════════════════════════════════"
echo "  Obi is live for you at:"
echo
echo "      $URL/test-hosts/none"
echo
echo "  Open it, click the round launcher, ask a question."
echo "  (general-only content — no partner or token needed)"
echo
echo "  Injected host into the local registry: $HOST"
echo "  Ctrl-C here to stop the tunnel and restore the registry."
echo "════════════════════════════════════════════════════════════════"
echo

wait "$CF_PID"
