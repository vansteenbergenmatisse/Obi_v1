# Tagging guide — getting your Confluence page into (and out of) Obi

> **Audience:** anyone who writes or maintains pages in the Omniboost Confluence.
> **Living doc:** describes the system after `ADR-routing-labels-sole-content-axis` (2026-10-12) and
> `ADR-source-system-decides-widget-eligibility` (2026-10-20). If Obi changes, this file changes with it.

Obi is the chatbot that answers customer questions from our Confluence documentation. It only
answers from pages you have **labeled** with a routing label. No routing label, no answer — and the
label also decides *which connections* the content is used for.

## The labels

A customer chat in Obi is about one connection: a **source** system sending data to a **target**
system (for example Toast → Mews). Obi searches only pages carrying one of that chat's four labels.

| Label | Content is used for |
|---|---|
| `obi-general` | **Every chat.** Use for content that applies to everyone. |
| `{system}-general`, e.g. `toast-general`, `mews-general`, `opera-cloud-general` | Every chat where that system is the source **or** the target. |
| `{system}-to-{pos\|pms\|accounting}`, e.g. `toast-to-pms` | Only chats from that source to a target of that kind (`toast-to-pms` is Toast → a PMS such as Mews; it is not used for Mews → Toast). |
| `classified` | **Nobody.** Adding this label removes the page from Obi immediately, whatever other labels it has. Use it to pull sensitive content without touching the other labels. |

The systems are the ones in `knowledge-base/config/product_catalog.json`: `toast`, `mews`,
`opera-cloud`, `quickbooks-online`, `xero`. A Toast → Mews chat searches `obi-general`,
`toast-general`, `mews-general` and `toast-to-pms`. If the target is a system Obi does not know, the
chat searches `obi-general` and `{source}-general` only.

Rules of thumb:

- A page may carry **more than one** label — tag it `toast-general` + `mews-general` and chats
  involving either system can use it. It is never used for chats none of its labels match.
- Labels that are not in the forms above (`draft`, `finance`, `base`, `general`, the old
  `obi-*-test` tags…) mean nothing to Obi. They never put a page in and never keep one in.
- Capitalization doesn't matter — Confluence lowercases labels, and Obi normalizes them.

## How to add or remove a label

On the page, open the label editor (the label icon at the bottom of the page, or press `L` while
viewing it), then add or remove the label. That's all — no deploy, no ticket.

## What happens, and how fast

These behaviours were proven live against the production pipeline on 2026-10-03, when the labels were still the old `obi-*-test` tags; routing labels use the same webhook and sync path. Typical delay is **5–60
seconds**; allow up to ~3 minutes before assuming something is wrong.

| You do | Obi does |
|---|---|
| Add a first routing label to a page | Reads, chunks, and indexes the whole page. It becomes answerable. |
| Edit a labeled page (body **or** title) | Re-indexes the whole page fresh. Old content is gone immediately — no stale answers. |
| Add a second label | Chats matching that label can use the page too. The labels are restamped; no re-embedding. |
| Remove one label (another routing label remains) | Chats that only matched the removed label lose the page; the rest keep it. |
| Remove the **last** routing label | The page is fully deleted from Obi — not hidden, deleted. |
| Add `classified` | The page is fully deleted from Obi, regardless of other labels. Remove `classified` again (with a routing label still on) and it re-indexes fresh. |
| Move the page to **trash** | Fully deleted from Obi. Restoring it from trash re-indexes it fresh. |

## The one trap: archiving

**Archiving a page does NOT remove it from Obi.** Archive sends no signal the pipeline listens to,
so an archived page's content stays answerable until the page is trashed or the periodic
reconciliation sweep catches it. If content must disappear **now**: remove the labels, add
`classified`, or trash the page — don't archive and assume it's gone.

## Checking your work

Ask the chatbot a question only your page can answer. A correct answer cites your page by title
with a link. If after a few minutes it still refuses, check: is the page **published** (not draft),
does it carry a routing label **from the table above** that matches the connection you are testing, spelled exactly? Still stuck → ask the Obi owner
(Matisse) — the pipeline logs every change and the cause is quickly visible.
