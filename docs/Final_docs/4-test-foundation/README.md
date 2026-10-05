# 4 · Test foundation (roadmap Step 4) — index

The single home for everything roadmap Step 4 (test foundation + state verification,
`docs/Final_docs/plan.md` §A) produces. Same rule as `0.5-regression-tests/`: anything about
this phase goes here; look here first.

- `coverage-audit.md` — substep 4.2's audit: every contract mapped to its test, the gap list
  (G1–G19), the two doc corrections (D1–D2), and the deliberately-deferred items (X1–X6).
  The gaps' closing tests are recorded there as they land.
- Baselines (substep 4.1) live in `docs/plan/baseline.md` (the no-regression floor /obi-verify
  reads), not here — recorded 2026-10-05.
- `test-proof.md` — the 4.2 gap-closing tests' red/green inversion proofs.
- `browser-checks-4.4/` — substep 4.4's owner-run evidence (2026-10-05, all three PASSED):
  `toast-host-sees-toast-content.png` (cited Toast answer + the correct refusal of an
  undocumented question), `mews-host-isolated-from-toast.png` (the Toast question refused with
  no Toast source; the Mews question cited `[1] Mews Testpage`), `none-host-clean-refusal.png`.
- Substep 4.3's live-run output lives at `backend/webhook-rules-live-run.txt` (all 8 rules PASS
  through the real webhook, 2026-10-05); the runner itself is
  `backend/scripts/webhook_rules_live.py`. 4.5's gold-set before-gate is in
  `docs/plan/baseline.md` §4.5. 4.6–4.8 are recorded in the ledger (entries 4.6, 4.7, 4.8).
  **Step 4 completed 2026-10-05 — one ledger entry per substep.**
