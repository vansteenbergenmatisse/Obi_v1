# CI gate proof — substep 0.5.4

Date: 2026-09-16
Repo: https://github.com/vansteenbergenmatisse/Obi_v1 (public — required for free-tier branch
protection; see "Deviations" below)

## 1. The setting

**Branch:** `main`
**Where it lives:** GitHub repository settings → Branches → branch protection rule on `main`
(applied via `gh api -X PUT repos/vansteenbergenmatisse/Obi_v1/branches/main/protection`, since the
UI and the API write to the same place).

**Exact setting:**
```json
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["obi four-level check (0.5.1)"]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": null,
  "restrictions": null
}
```

A pull request into `main` cannot merge until the `obi four-level check (0.5.1)` check reports
success, and `enforce_admins: true` means this applies even to repo admins — no bypass.

## Deviations from the substep's literal wording

1. **"The four CI jobs from 0.5.1" is one job, not four.** `.github/workflows/ci.yml` (written in
   0.5.1) defines a single job, `obi-checks` (display name `obi four-level check (0.5.1)`), whose
   four *steps* run `make test-unit`, `make test-db`, `make test-ui`, and `make eval` in sequence —
   not four separate jobs. There is exactly one required status check, matching what actually
   exists. Not fixed here (0.5.4 is a gating substep, not a CI-restructuring one); flagged for a
   future design-review pass if four independent jobs (for parallelism / partial-failure signal)
   are ever wanted instead.
2. **The repo had to be made public.** GitHub's required-status-checks branch protection feature is
   Pro-only on private repositories (`403: Upgrade to GitHub Pro or make this repository public`).
   The owner chose to make the repo public rather than pay for Pro. `.env` was confirmed gitignored
   and not tracked before any push (`git ls-files .env` returns nothing); no secret is in the pushed
   history.
3. **No pre-existing remote.** `git remote -v` was empty at the start of this substep (a blocker
   already logged in 0.5.1/0.5.2/0.5.3's "Need from you"). The owner provided a fresh, empty GitHub
   repo (`vansteenbergenmatisse/Obi_v1`); it had no `main` branch of its own, so the local
   `feat/rag-phase-3.5` tip was pushed directly to `origin/main` (`git push origin
   feat/rag-phase-3.5:main`) rather than reconciling it with a separate, far-behind local `main`
   branch that existed only locally and had never been used for real work.
4. **A real, unrelated bug surfaced and was fixed first.** The initial deliberate-break PR run
   failed for the WRONG reason: `test_versioning_gate.py` (written in substep 0.5.2, Batch C) was
   missing `pytestmark = pytest.mark.db`, so `make test-unit` in CI tried to open a real Postgres
   connection with none running and errored before the intended signature-check test ever got a
   clean shot at being the sole cause of red. Fixed by adding the marker (matching every sibling
   `test_versioning_*.py` file's convention) and reverified locally (`make test-unit`: 460 passed,
   no DB errors; `make test-db`: picks the two tests up correctly) before re-running the proof. This
   is a real, disclosed correction to 0.5.2's work — not scope creep on 0.5.4 — since without it the
   revert step could never have gone green for the right reason.

## 2. The break

**Branch:** `prove-gate-2026-09-16`
**Behavior broken:** the webhook's HMAC signature check (`i1-checks` panel, `_verify_signature` in
`apps/automation/app/features/confluence_sync/server/webhook.py:76`), matching the substep's own
suggested example.
**The one-line change:**
```diff
-    if not hmac.compare_digest(provided, expected):
+    if not hmac.compare_digest(provided, provided):
```
Compares the provided signature against itself instead of the expected HMAC, so any signature
(including a forged one) is accepted.
**PR:** https://github.com/vansteenbergenmatisse/Obi_v1/pull/1 ("prove-gate-2026-09-16: deliberate
CI-gate break (0.5.4 proof, not for merge)")

## 3. The red run

**Run:** https://github.com/vansteenbergenmatisse/Obi_v1/actions/runs/35151345624
(after the `test_versioning_gate.py` marker fix above — the run before this one, 35151076986, is
the one that failed on the unrelated Postgres-connection error and is not the proof run)

**Failing test:** `app/features/confluence_sync/tests/test_webhook.py::test_bad_signature_is_rejected`
```
FAILED app/features/confluence_sync/tests/test_webhook.py::test_bad_signature_is_rejected - assert 200 == 401
==== 1 failed, 196 passed, 460 deselected, 1 xfailed, 2 warnings in 28.64s =====
```
Exactly the one test that exercises the broken check, and nothing else — confirms the break is
correctly isolated and caught.

## 4. The revert and the green run

Reverted with `git revert --no-edit <break-commit>` on the same branch (keeping the marker fix from
§1's deviation 4), pushed.

**Run:** https://github.com/vansteenbergenmatisse/Obi_v1/actions/runs/35151531728 — **pass**, 1m49s.

## 5. Close-out

- PR #1 closed without merging (`gh pr close 1 --delete-branch`).
- Remote branch `prove-gate-2026-09-16` deleted; local branch deleted; `origin` pruned.

## Hand-back

- Red run: https://github.com/vansteenbergenmatisse/Obi_v1/actions/runs/35151345624
- Green run: https://github.com/vansteenbergenmatisse/Obi_v1/actions/runs/35151531728
- Test name that caught the break: `test_bad_signature_is_rejected`
