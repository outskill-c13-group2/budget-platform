# START HERE

This package is everything the data + backend work produced, arranged in the
repo's folders so it's easy to place.

## What to do

1. Read **`_handoff/STATUS-for-architect.md`** — the one-page summary (share this
   with the architect).
2. Use **`_handoff/FOLDER-MAP.md`** to copy files into your cloned repo. Copy the
   four folders — `contract/`, `supabase/`, `mock-data/`, `docs/` — into the repo.
   The `_handoff/` folder is a guide; **don't commit it.**
3. Commit and push, then open the PR and paste **`_handoff/PR-description.md`**.

## What's inside

- `contract/` — the data contract (schema).
- `supabase/` — the database migration and the AI proxy edge function.
- `mock-data/` — the demo + testing fixtures, their seed loaders, and tooling.
- `docs/` — guides and the two builder specs.

## The one open decision

Where the AI call runs — edge function or n8n. Recommendation (in the status
sheet): use the edge function, cut n8n. Everything else is either done or belongs
to the front-end builder.
