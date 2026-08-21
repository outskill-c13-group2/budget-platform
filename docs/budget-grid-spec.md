# Budget Grid — data mapping for the Lovable builder

How to turn the fixture JSON into the main screen: a 7-category grid with a
Family column and a month selector. **Read the fixture JSON directly**
(`mock-data/budget-fixture.demo.json`) — do not call Supabase, so this never
blocks on Track B.

All money in the fixture is integer **minor units** (cents). Divide by 100 only
for display; never store as a float.

**Model in one line:** each cell is a person's *allowance* for a category that
month. A negotiation redistributes allowance between people and always nets to
zero, so the category total and household total never change — only the split
does. The demo fixture starts September at baseline allowances with **no
negotiations yet**, so the propose-and-agree flow is demonstrated live.

---

## 1. The grid

**Rows:** the 7 categories in `budget-fixture.demo.json`, ordered by
`category.sort_order` (Groceries, Dining out & takeout, Liquor store, Bars &
nightlife, Entertainment & subscriptions, Shopping & apparel, Travel & outings).
There is **no Savings category** — savings progress toward the $5,000 goal is a
single number shown elsewhere on the page, entered by a member at setup, not a
grid row.

**Columns:** Parent 1, Parent 2, Teen 1, **Family**.

**A cell** (member × category, for the selected month) = the matching
`budget_items` record's `planned_amount_minor`:

```
budget_items[] where member_id = <member>
                 and category_id = <category>
                 and month = <selected month>
              → planned_amount_minor
```

Resolve the readable labels via `members[]` (role → column) and `categories[]`
(id → row name).

### Two fill rules — easy to get wrong, and they make totals look broken if missed

1. **Family = P1 + P2 + Teen** for that category, computed on the fly. It is
   **never** read from a stored field (there is no family row in the data).
2. **A member with no record for a category is `$0.00`, not blank.** Many
   categories are owned by only one or two members (Groceries is Parent 1 only;
   Bars is Parent 2 only), so most rows have empty member cells that must render
   as zero.

Optional per-cell extra on each `budget_items` record: `floor_amount_minor` —
the lowest that person's allowance may be pushed to in a negotiation. This is a
**per-person, per-category** floor, not one number for the whole category.
Category-level `is_hard_floor` marks Groceries (a category that shouldn't be cut
to nothing). No budget items are locked in the demo fixture.

---

## 2. Month selector

Options = the months present in `budget_items` (`"2026-09"` … `"2027-01"`).
Default to `demo_clock.current_month` (`"2026-09"`). Values are `"YYYY-MM"`
strings.

---

## 3. Worked example — verify your render against these exact numbers (month `2026-09`)

| Category | Parent 1 | Parent 2 | Teen 1 | Family |
|---|---:|---:|---:|---:|
| Groceries | $900 | $0 | $0 | $900 |
| Dining out & takeout | $224 | $224 | $112 | $560 |
| Liquor store | $48 | $112 | $0 | $160 |
| Bars & nightlife | $0 | $180 | $0 | $180 |
| Entertainment & subscriptions | $72 | $72 | $96 | $240 |
| Shopping & apparel | $168 | $168 | $144 | $480 |
| Travel & outings | $160 | $160 | $0 | $320 |

(Note the `$0` cells — that's the missing-cell rule, not missing data.)

---

## 4. Activity / transaction log

This model has **no separate expense records** — the schema tracks allowance
allocation, not money spent. The only "transactions" are the net-zero
adjustments an agreed negotiation makes to people's allowances.

So the log starts **empty** at the September baseline and **fills as
negotiations are agreed during the session.** Each agreed proposal contributes
one entry per change line: who, which category, and the signed delta (e.g.
`Teen 1 · Shopping & apparel · +$200`). Read these from a proposal's `changes[]`
once its `status` is `agreed`.

(There is no seeded activity in the demo fixture, by design. "Load the September
transactions" was dropped from the rubric — verbally agreed with the architect —
because a clean baseline and pre-seeded activity are mutually exclusive here.)

---

## 5. The scripted demo move (for reference)

The first negotiation demonstrated live is the **clothing rebalance**: Teen 1
**+$200** on Shopping & apparel, funded by **−$100** from each parent, netting to
zero. From the September baseline (Teen $144, each parent $168) it lands at Teen
$344 / parents $68 each — every result stays above its per-person floor. This is
also the exact case used to test `agree_to_proposal` in the testing fixture; it
is *not* seeded in the demo fixture.

---

## 6. Source of truth

Read `mock-data/budget-fixture.demo.json`. Ignore Supabase for this screen.
Contract reference: `contract/fixture.schema.json`.
