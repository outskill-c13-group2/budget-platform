# Testing the fixture in Supabase (before you hand it off)

This walks you through loading the schema and seed into your own Supabase
project and proving the data is correct — including the "agree to a proposal"
flow that actually changes the budget. It uses only the in-browser **SQL
Editor**, so there's nothing to install. Budget ~20 minutes the first time.

You do **not** need to understand the app to run this. Every step tells you what
to paste and what result to expect. If a result doesn't match, stop and check
the Troubleshooting table at the end.

> Everything you paste is standard SQL. The SQL Editor runs many statements at
> once and shows results (or "Success. No rows returned.") underneath.

---

## Before you start

You need:

- A Supabase account (the free tier is fine).
- Two files from this folder, open in a text editor so you can copy them:
  - the team's schema file, `supabase-mvp-schema.sql`
  - `seed.sql`

**Tip:** use a brand-new throwaway project for this test so you never touch real
data. On the free tier a project pauses after inactivity — that's fine, you can
resume it, or just delete it when you're done.

---

## Step 1 — Create (or pick) a project

1. Go to https://supabase.com/dashboard and sign in.
2. Click **New project**. Give it a name like `budget-negotiator-test`, set a
   database password (save it somewhere; you won't need it for this test), pick
   the nearest region, and create it.
3. Wait ~2 minutes for it to finish provisioning before continuing.

---

## Step 2 — Open the SQL Editor

In the left sidebar click **SQL Editor** (the `</>` icon). Click **New query**.
This is where you'll paste everything below. To run whatever is in the editor,
click **Run**, or press **Cmd/Ctrl + Enter**.

---

## Step 3 — Create the tables (run the schema)

1. Open `supabase-mvp-schema.sql`, select **all** of it, and copy.
2. Paste into a new query and **Run**.
3. Expected result: **Success. No rows returned.**

This created ten tables and the `agree_to_proposal` function. Confirm the tables
exist by running this in a new query:

```sql
select table_name
from information_schema.tables
where table_schema = 'public'
order by table_name;
```

You should see ten rows: `budget_item`, `category`, `goal`, `goal_plan_month`,
`household`, `member`, `proposal`, `proposal_change`, `proposal_decision`,
`spend_summary`.

---

## Step 4 — Load the data (run the seed)

1. Open `seed.sql`, select **all**, copy.
2. Paste into a new query and **Run**.
3. Expected result: **Success. No rows returned.** (Everything inserts inside one
   transaction.)

---

## Step 5 — Verify the data loaded correctly

Run each block below in a new query and compare to the expected result.

**5a. Row counts.**

```sql
select 'household' as t, count(*) from household
union all select 'member',            count(*) from member
union all select 'category',          count(*) from category
union all select 'goal',              count(*) from goal
union all select 'goal_plan_month',   count(*) from goal_plan_month
union all select 'spend_summary',     count(*) from spend_summary
union all select 'budget_item',       count(*) from budget_item
union all select 'proposal',          count(*) from proposal
union all select 'proposal_change',   count(*) from proposal_change
union all select 'proposal_decision', count(*) from proposal_decision
order by t;
```

Expected: budget_item **85**, category **8**, goal **1**, goal_plan_month **5**,
household **1**, member **3**, proposal **1**, proposal_change **3**,
proposal_decision **0**, spend_summary **75**.

**5b. The $5,000 goal math checks out.**

```sql
select g.saved_amount_minor                              as start_cents,
       coalesce(sum(bi.planned_amount_minor), 0)         as future_savings_cents,
       g.saved_amount_minor + coalesce(sum(bi.planned_amount_minor), 0) as total_cents,
       g.target_amount_minor                             as target_cents
from goal g
join category c    on c.household_id = g.household_id and c.name = 'Savings'
join budget_item bi on bi.category_id = c.id and bi.goal_id = g.id
group by g.id, g.saved_amount_minor, g.target_amount_minor;
```

Expected one row: start **150000**, future savings **350000**, total **500000**,
target **500000**. (That's $1,500 + $3,500 = $5,000.)

**5c. No budget is below its floor.**

```sql
select count(*) as floor_violations
from budget_item
where planned_amount_minor < floor_amount_minor;
```

Expected: **0**.

**5d. The pending proposal nets to zero.**

```sql
select p.status,
       count(*)                    as change_count,
       sum(pc.delta_amount_minor)  as net_delta
from proposal p
join proposal_change pc on pc.proposal_id = p.id
group by p.status;
```

Expected: status **pending**, change_count **3**, net_delta **0**.

**5e. September snapshot — the three lines the proposal will touch.**
Run this now and keep the numbers; you'll compare after agreeing.

```sql
select c.name  as category,
       m.role  as member,
       bi.planned_amount_minor as cents
from budget_item bi
join category c on c.id = bi.category_id
join member   m on m.id = bi.member_id
where bi.month = date '2026-09-01'
  and (c.name = 'Groceries'
       or (c.name = 'Dining out & takeout' and m.role = 'parent_2')
       or (c.name = 'Savings'              and m.role = 'parent_2'))
order by c.name, m.role;
```

Expected **before** agreeing:
- Dining out & takeout / parent_2 → **22400**
- Groceries / parent_1 → **90000**
- Savings / parent_2 → **31000**

---

## Step 6 — Test the write path (agree to the proposal)

This is the important one: it proves budgets change **only** through the
function, and the guardrails hold.

**6a. Agree.** There's one pending proposal and its only required responder is
Parent 2, so a single agreement should apply it. This looks the ids up for you:

```sql
select agree_to_proposal(
  (select id from proposal where status = 'pending' order by created_at limit 1),
  (select id from member   where role   = 'parent_2')
);
```

Expected: one row comes back representing the proposal, now with status
`agreed`.

**6b. Confirm the proposal is resolved.**

```sql
select status, resolved_at from proposal;
```

Expected: status **agreed**, and `resolved_at` is a timestamp (no longer null).

**6c. Confirm the budget actually moved.** Re-run the exact query from **5e**.

Expected **after** agreeing:
- Dining out & takeout / parent_2 → **10400**  (was 22400, −$120)
- Groceries / parent_1 → **94000**  (was 90000, +$40)
- Savings / parent_2 → **39000**  (was 31000, +$80)

If those three moved and nothing else did, the write path works end to end.

**6d. Confirm the guardrail: you can't agree twice.** Run **6a** again.

Expected: it **fails** with an error like *"Proposal … is not pending."* That red
error is the **correct, wanted** behavior — the proposal is already agreed, so
the function refuses to touch the budget again.

---

## Step 7 — Reset so you can re-run

To run the whole test again from a clean slate, wipe the data (the tables and
function stay) and re-run `seed.sql`:

```sql
truncate proposal_change, proposal_decision, proposal, budget_item,
         spend_summary, goal_plan_month, goal, category, member, household
         restart identity cascade;
```

Then repeat **Step 4**. (No need to re-run the schema unless you dropped tables.)

---

## Step 8 — You're done

If Steps 5 and 6 matched, the fixture, the seed, and the write path are all
sound, and you can hand the files to the team with confidence. Clean up by
pausing or deleting the test project if you like.

---

## Troubleshooting

| Symptom | Cause & fix |
|---|---|
| `permission denied to create extension "pgcrypto"` when running the schema | Rare on Supabase. `gen_random_uuid()` is built into modern Postgres, so you can safely delete the `create extension … pgcrypto;` line and re-run the schema. |
| `relation "household" already exists` when re-running the schema | Harmless — the schema uses `create table if not exists`. You can ignore it, or skip straight to the seed. |
| `duplicate key value violates unique constraint` when running the seed | The tables weren't empty. Run the `truncate` block in Step 7, then run `seed.sql` again. |
| Seed ran but tables look empty in the Table Editor | Make sure the schema **and** seed ran in the **same** project, schema first. Re-open the Table Editor and refresh. |
| `agree_to_proposal` returns a row but status is still `pending` | That happens only if a proposal has more than one required responder and not all have agreed yet. This fixture's proposal has a single responder, so one agreement flips it to `agreed`. |
| You want to see it in a table view, not query results | Left sidebar → **Table Editor** → pick a table (e.g. `budget_item`). |

> Reminder: this schema is a DEV/demo build with no authentication or row-level
> security. Don't put real personal data in your test project.
