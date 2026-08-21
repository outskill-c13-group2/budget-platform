# Budget Negotiator — mock data, validation & seeding

New to this repo? Read this whole page once. It explains what the data is, the
handful of rules that make it valid, and exactly how to check it and load it.
For a click-by-click Supabase walkthrough, see **`TESTING-in-supabase.md`**.

> **Two fixtures live here.** `budget-fixture.demo.json` is the **demo** set —
> a clean September baseline, 7 categories, no seeded negotiations (savings is a
> single number, not a category). `budget-fixture.sample.json` is the **testing**
> set — 8 categories with a seeded proposal, used to exercise the write path.
> Sections below that mention savings-as-a-category or the goal-math check
> describe the **testing** fixture; the demo fixture omits both by design.

---

## 1. What this is (the 60-second version)

Our app helps a family negotiate a shared budget toward a savings goal. Before
anyone writes app code or n8n workflows, the team needs **one shared set of fake
data** so we're all building against the same numbers. That's what lives here.

Three files (owned by the project architect) form the **contract**:

- `fixture.schema.json` — describes the *shape* every data file must have.
- `supabase-mvp-schema.sql` — the actual database (tables + one function).
- `fixture-to-supabase-mapping.md` — explains how the JSON maps into the tables.

This folder adds the **data itself** plus tools to check and load it:

| File | What it is | Commit to Git? |
|---|---|---|
| `budget-fixture.sample.json` | The mock data. One household, 3 members, 8 categories, a $5,000 goal, historical actuals, the active budget, and one pending proposal. | **Yes** |
| `seed.sql` | Loads that data into Supabase. | **Yes** |
| `validate_fixture.py` | Checks the JSON against every contract rule. No installs needed. | **Yes** |
| `generate_fixture.py` | Builds `budget-fixture.sample.json`. Edit this to change the data. | **Yes** |
| `generate_seed.py` | Builds `seed.sql` from the JSON. | **Yes** |
| `README-fixtures.md` | This file. | **Yes** |
| `TESTING-in-supabase.md` | Hands-on Supabase load-and-verify guide. | **Yes** |

Everything is plain UTF-8 text (`.json`, `.sql`, `.py`, `.md`), 2-space JSON
indent, one trailing newline. Nothing binary. No database dump.

---

## 2. Six things you must know before touching the data

**1. Money is stored as whole cents (never dollars, never decimals.)**
`5000` means **$50.00**. The field names end in `_minor` (the currency's "minor
unit"). To show a dollar value, divide by 100. This avoids rounding bugs. The
currency is USD, set once on the household — it is *not* repeated on every row.

**2. Months come in two shapes.** The JSON uses `"2026-09"` (year-month text).
The database uses a real date pinned to the first of the month, `2026-09-01`.
`seed.sql` does that conversion for you.

**3. Every id is a UUID**, e.g. `e569cb3a-7223-4e05-90fa-46ea9596aa9b`. The seed
inserts these ids *explicitly*, so the database keeps them and every foreign-key
reference already lines up. (See the one contract change in section 6.)

**4. The data has two time windows with two different jobs.**
- **Historical actuals** (`spend_summaries`, Sep 2025–Jan 2026) are read-only
  reference — "here's what we actually spent a year ago." They never change.
- **The active budget** (`budget_items`, Sep 2026–Jan 2027) is the live plan.
  It changes **only** through an agreed proposal.

**5. Categories have per-member ownership.** A category isn't one number — it's
split into a line per member who owns a share. Groceries is 100% Parent 1; bars
is 100% Parent 2; apparel is split across all three. So one category+month can
have up to three `budget_item` rows (one per member).

**6. Two categories have a hard floor.** Groceries and Savings can't be
negotiated below their `floor_amount_minor`. Every budget line has a floor;
`planned_amount_minor` must always be ≥ `floor_amount_minor`.

---

## 3. What's in the data (the story it tells)

- A comfortable two-parent + one-teen household, discretionary spending only
  (fixed costs like rent live outside this budget).
- **8 categories:** Groceries, Dining out & takeout, Liquor store, Bars &
  nightlife, Entertainment & subscriptions, Shopping & apparel, Travel &
  outings, and Savings.
- **Two offsetting pairs** show a lifestyle shift from the historical numbers to
  the plan: dining **down** / groceries **up** (cook more at home), and bars
  **down** / liquor **up** (drink at home more).
- **Seasonality:** September is higher (back-to-school) and December is higher
  (holidays); savings dips in those two months and rises in the cheaper ones.
- **The goal:** reach **$5,000** by **Feb 1, 2027**. It works out exactly:
  $1,500 already saved + $3,500 of planned monthly savings (Sep 2026–Jan 2027).
- **One pending proposal:** Parent 1 asks Parent 2 to spend $120 less on dining
  in September — $40 moves to groceries, $80 to savings. It nets to zero and is
  waiting on Parent 2's agreement, ready for you to test the "agree" flow.

---

## 4. The one write rule that matters

When a family member agrees to a proposal, **do not** `UPDATE budget_item`
yourself. Call the database function instead:

```sql
select agree_to_proposal('<proposal-uuid>', '<responding-member-uuid>');
```

In a single transaction it checks the responder is required and the proposal is
still pending, that the changes still net to zero and match the current budget,
that nothing drops below a floor, and only then applies the changes and marks
the proposal `agreed`. The app and n8n must always go through this function.
`TESTING-in-supabase.md` walks you through calling it and seeing it work.

---

## 5. How to validate the data (do this before every commit)

No installs required — pure Python standard library:

```bash
python3 validate_fixture.py budget-fixture.sample.json
```

Exit code `0` = pass, `1` = fail. It checks field shapes, types, patterns, and
enums **and** the cross-record rules JSON Schema can't express (ids resolve,
budgets stay above floors, proposals net to zero, the $5,000 math). On failure
it names the exact record.

Want standard JSON-Schema validation as well (this covers only shape, not the
cross-record rules)? With internet access:

```bash
pip install check-jsonschema
check-jsonschema --schemafile fixture.schema.json budget-fixture.sample.json
```

---

## 6. Loading the data into Supabase (`seed.sql`)

**Order matters. Run the schema first, then the seed.**

1. In the Supabase **SQL Editor**, run the team's `supabase-mvp-schema.sql`
   once. This creates the ten tables and the `agree_to_proposal` function.
2. Then run `seed.sql`.

What `seed.sql` does and assumes:

- It runs inside one `begin; … commit;` transaction — all rows load or none do.
- It inserts rows in dependency order (household → members → categories → goal →
  goal_plan_month → spend_summary → budget_item → proposal → proposal_change).
- It supplies each row's UUID explicitly, and fills in the `household_id` /
  `goal_id` that the flat JSON doesn't carry (there's exactly one of each).
- It loads the pending proposal into `proposal` + `proposal_change` **without**
  touching `budget_item` — the budget only moves when someone agrees.
- It assumes the target tables are **empty**. Running it twice without clearing
  first will fail on unique constraints. There's a commented-out `truncate`
  block at the top of the file — uncomment it to wipe and reload from scratch.

> **The one contract assumption:** this data uses UUID ids, which the *original*
> `fixture.schema.json` rejected (it required ids to start with a letter). It
> assumes the `id` rule in the schema's `$defs` was changed to a UUID pattern:
> `^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$`.
> Confirm that change is in the shared schema before merging.

> **DEV only.** The schema has no authentication or row-level security by
> design (it's a hackathon demo). Don't load real personal data, and don't
> promote this schema to production unchanged.

---

## 7. Changing the data safely

Never hand-edit `budget-fixture.sample.json` or `seed.sql` — it's easy to
silently break the net-to-zero or floor rules. Instead, edit the model tables at
the top of `generate_fixture.py` (household totals, ownership shares, the savings
schedule, the proposal), then regenerate and re-check **in this order**:

```bash
python3 generate_fixture.py > budget-fixture.sample.json   # rebuild the data
python3 validate_fixture.py budget-fixture.sample.json      # prove it's valid
python3 generate_seed.py    > seed.sql                      # rebuild the loader
```

---

## 8. Suggested repo layout

```
/contracts   fixture.schema.json, supabase-mvp-schema.sql, fixture-to-supabase-mapping.md
/fixtures    budget-fixture.sample.json, seed.sql,
             generate_fixture.py, validate_fixture.py, generate_seed.py,
             README-fixtures.md, TESTING-in-supabase.md
```

(Filenames above use the names from the mapping doc; if the team named the
schema files differently in the repo, keep those names.)
