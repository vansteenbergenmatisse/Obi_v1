# Tagging guide — getting your Confluence page into (and out of) Obi

> **Audience:** anyone who writes or maintains pages in the Omniboost Confluence.
> **Living doc:** describes the system as proven on 2026-10-03. If Obi changes, this file changes with it.

Obi is the chatbot that answers customer questions from our Confluence documentation. It only
answers from pages you have **labeled**. No label, no answer — and the label also decides *which
customers* can see the content.

## The labels

| Label | Who sees content with this label |
|---|---|
| `obi-general-test` | **Everyone.** Every customer on every platform. Use for content that applies to all. |
| `obi-mews-test` | Only customers connected through Mews. |
| `obi-operacloud-test` | Only customers connected through Opera Cloud. |
| `obi-toast-test` | Only customers connected through Toast. |
| `classified` | **Nobody.** Adding this label removes the page from Obi immediately, whatever other labels it has. Use it to pull sensitive content without touching the other labels. |

Rules of thumb:

- A page may carry **more than one** label — tag it `obi-mews-test` + `obi-toast-test` and both
  customer groups can use it. It is never shown to groups you did not tag.
- Labels you invent (`draft`, `finance`, `base`, `general`…) mean nothing to Obi. They never put a
  page in and never keep one in.
- Capitalization doesn't matter — Confluence lowercases labels, and Obi normalizes them.

## How to add or remove a label

On the page, open the label editor (the label icon at the bottom of the page, or press `L` while
viewing it), then add or remove the label. That's all — no deploy, no ticket.

## What happens, and how fast

Every change below was proven live against the production pipeline. Typical delay is **5–60
seconds**; allow up to ~3 minutes before assuming something is wrong.

| You do | Obi does |
|---|---|
| Add a first label to a page | Reads, chunks, and indexes the whole page. It becomes answerable. |
| Edit a labeled page (body **or** title) | Re-indexes the whole page fresh. Old content is gone immediately — no stale answers. |
| Add a second label | The page becomes visible to that group too. Instant, no re-indexing. |
| Remove one label (another remains) | That group loses the page; the other keeps it. |
| Remove the **last** label | The page is fully deleted from Obi — not hidden, deleted. |
| Add `classified` | The page is fully deleted from Obi, regardless of other labels. Remove `classified` again (with a real label still on) and it re-indexes fresh. |
| Move the page to **trash** | Fully deleted from Obi. Restoring it from trash re-indexes it fresh. |

## The one trap: archiving

**Archiving a page does NOT remove it from Obi.** Archive sends no signal the pipeline listens to,
so an archived page's content stays answerable until the page is trashed or the periodic
reconciliation sweep catches it. If content must disappear **now**: remove the labels, add
`classified`, or trash the page — don't archive and assume it's gone.

## Checking your work

Ask the chatbot a question only your page can answer. A correct answer cites your page by title
with a link. If after a few minutes it still refuses, check: is the page **published** (not draft),
does it carry a label **from the table above**, spelled exactly? Still stuck → ask the Obi owner
(Matisse) — the pipeline logs every change and the cause is quickly visible.
