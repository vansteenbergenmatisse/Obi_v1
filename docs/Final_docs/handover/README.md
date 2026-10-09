# handover/ — the three tag & integration documents

Three audience-separated documents, ordered by how close the reader is to the code:

1. **`tagging-guide.md`** — for anyone who writes Confluence pages. Which labels exist, what each one does, how to get a page into (or out of) the Obi chatbot.
2. **`tag-administration.md`** — for operators. How to add, remove, or rename a knowledge scope in the config today, with the real consequences and the verification commands.
3. **`integration-onboarding.md`** — for whoever onboards or offboards a whole platform integration, end to end.

Related, for page authors: the **"Applies to" authoring guide** lives at
`../5-integration-context/applies-to-authoring.md` (substep 8.2.1) — how a page states exactly
which setup it is for (five levels, explicit `any`, worked examples). Labels keep deciding
membership and sharing exactly as `tagging-guide.md` says; an `Applies to` table only narrows
relevance on top. Note: the table is read and enforced at sync from substep 8.2.2 onward.

**The living-doc rule (same as `../ingestion/` and `../retrieval/`):** every claim in these files describes what the system *provably does today*. A change to the system changes the matching doc **in the same substep** — a stale handover is worse than none. Sections that roadmap Step 5 (the scope-restamp fix) will invalidate are flagged in place.
