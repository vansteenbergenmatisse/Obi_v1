"""Pure answer-runtime domain logic: refusal and citation enforcement.

Framework-free and side-effect-free — no LLM, DB, clock, or settings reads. Modules here
are deep-imported within the feature (never through the feature root). Prompt assembly and
the workflow orchestration land alongside these in Phase 4.2.
"""
