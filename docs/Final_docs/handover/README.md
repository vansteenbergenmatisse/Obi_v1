# handover/ — the three label & partner documents

Three audience-separated documents, ordered by how close the reader is to the code:

1. **`tagging-guide.md`** — for anyone who writes Confluence pages. Which routing labels exist, what each one does, how to get a page into (or out of) the Obi chatbot.
2. **`tag-administration.md`** — for operators. How the set of recognized labels changes (by adding, removing or renaming a system in the product catalog), with the real consequences and the verification commands.
3. **`integration-onboarding.md`** — for whoever connects or disconnects a partner (Base, Data Hub), end to end. The partner-facing guide is [how partners integrate with Obi](../1-how-partners-integrate-with-obi/how-partners-integrate-with-obi.md).

Related, for page authors: the **"Applies to" authoring guide** lives at
`../5-integration-context/applies-to-authoring.md` (substep 8.2.1) — how a page states exactly
which setup it is for (five levels, explicit `any`, worked examples). Labels keep deciding
membership and sharing exactly as `tagging-guide.md` says; an `Applies to` table only narrows
relevance on top. Note: the table is read and enforced at sync from substep 8.2.2 onward.

**The living-doc rule (same as `../ingestion/` and `../retrieval/`):** every claim in these files describes what the system *provably does today*. A change to the system changes the matching doc **in the same substep** — a stale handover is worse than none.
