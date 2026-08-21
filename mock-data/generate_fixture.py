#!/usr/bin/env python3
"""
Generate the Budget Negotiator MVP fixture (mock data) that conforms to
fixture.schema.json contract_version 1.0.0.

- All money is stored as integer cents (USD minor unit). No floats in output.
- Every id is a deterministic UUIDv4-shaped value, so re-running produces the
  exact same file (clean Git diffs) while satisfying the architect's UUID rule.
- One household, one goal, per-member category ownership.

Run:  python3 generate_fixture.py > budget-fixture.sample.json
"""

import json
import hashlib
import calendar

# --- deterministic UUIDv4-shaped ids ----------------------------------------
NS = "outskill-c13-group-2::budget-fixture::v1::"

def uid(slug: str) -> str:
    """Stable UUIDv4-shaped id derived from a readable slug."""
    b = bytearray(hashlib.md5((NS + slug).encode()).digest())  # 16 bytes
    b[6] = (b[6] & 0x0F) | 0x40   # set version nibble to 4
    b[8] = (b[8] & 0x3F) | 0x80   # set variant bits to 10xx
    h = b.hex()
    return f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"

# --- household model --------------------------------------------------------
CURRENCY = "USD"

# member: key(role), display_name, short_name, can_propose
MEMBERS = [
    ("parent_1", "Parent 1", "P1", True),
    ("parent_2", "Parent 2", "P2", True),
    ("teen_1",   "Teen 1",   "Teen", True),
]

# category: key, name, sort_order, is_hard_floor, floor_ratio
CATEGORIES = [
    ("groceries",     "Groceries",                     1, True,  0.85),
    ("dining",        "Dining out & takeout",          2, False, 0.40),
    ("liquor",        "Liquor store",                  3, False, 0.40),
    ("bars",          "Bars & nightlife",              4, False, 0.40),
    ("entertainment", "Entertainment & subscriptions", 5, False, 0.50),
    ("shopping",      "Shopping & apparel",            6, False, 0.40),
    ("travel",        "Travel & outings",              7, False, 0.40),
    ("savings",       "Savings",                       8, True,  0.75),
]

# category -> list of (member_key, share fraction). Shares sum to 1.0.
OWNERSHIP = {
    "groceries":     [("parent_1", 1.00)],
    "dining":        [("parent_1", 0.40), ("parent_2", 0.40), ("teen_1", 0.20)],
    "liquor":        [("parent_1", 0.30), ("parent_2", 0.70)],
    "bars":          [("parent_2", 1.00)],
    "entertainment": [("parent_1", 0.30), ("parent_2", 0.30), ("teen_1", 0.40)],
    "shopping":      [("parent_1", 0.35), ("parent_2", 0.35), ("teen_1", 0.30)],
    "travel":        [("parent_1", 0.50), ("parent_2", 0.50)],
    "savings":       [("parent_1", 0.50), ("parent_2", 0.50)],
}

# Historical actuals (household $ per category per month). Spending only.
# Story a year ago: looser -- more dining/bars, less groceries/liquor.
HIST_MONTHS = ["2025-09", "2025-10", "2025-11", "2025-12", "2026-01"]
HIST = {  # no "savings": you don't "spend" savings, so it has no actual-spend row
    "groceries":     [780, 740, 820, 800, 720],
    "dining":        [720, 680, 700, 820, 600],
    "liquor":        [120, 120, 150, 200, 110],
    "bars":          [300, 300, 320, 420, 240],
    "entertainment": [280, 280, 290, 340, 270],
    "shopping":      [560, 360, 420, 840, 320],
    "travel":        [400, 420, 480, 640, 320],
}

# Future active budget (household $ per category per month).
# Disciplined plan: dining/bars down, groceries/liquor up (the two offset pairs),
# a real savings line, Sep bumped for school and Dec bumped for holidays.
FUT_MONTHS = ["2026-09", "2026-10", "2026-11", "2026-12", "2027-01"]
FUT = {
    "groceries":     [900, 850, 950, 920, 830],
    "dining":        [560, 520, 540, 620, 440],
    "liquor":        [160, 170, 200, 260, 140],
    "bars":          [180, 180, 190, 260, 120],
    "entertainment": [240, 240, 250, 300, 230],
    "shopping":      [480, 300, 340, 720, 260],
    "travel":        [320, 360, 420, 560, 260],
    "savings":       [620, 820, 700, 480, 880],   # sums to 3500; inverse of spend
}

GOAL_TARGET = 500000          # $5,000
GOAL_SAVED_START = 150000     # $1,500 starting balance
GOAL_TARGET_DATE = "2027-02-01"

# --- helpers ----------------------------------------------------------------
def split_cents(total_dollars, shares):
    """Split a household $ total into integer-cent shares that sum exactly.
    Any rounding remainder goes to the first (largest) owner."""
    total_cents = total_dollars * 100
    out = []
    allocated = 0
    for m, f in shares:
        c = int(total_cents * f)   # floor
        out.append([m, c])
        allocated += c
    out[0][1] += total_cents - allocated
    return out

def month_bounds(ym):
    y, m = int(ym[:4]), int(ym[5:7])
    last = calendar.monthrange(y, m)[1]
    return f"{ym}-01", f"{ym}-{last:02d}"

# --- id lookups -------------------------------------------------------------
mem_id = {k: uid(f"member:{k}") for k, *_ in MEMBERS}
cat_id = {k: uid(f"category:{k}") for k, *_ in CATEGORIES}
floor_ratio = {k: r for k, _, _, _, r in CATEGORIES}

def budget_id(mk, ck, ym):  return uid(f"budget:{mk}:{ck}:{ym}")
def summary_id(mk, ck, ym): return uid(f"summary:{mk}:{ck}:{ym}")

# --- build sections ---------------------------------------------------------
household = {
    "id": uid("household:main"),
    "name": "Rivera Household",
    "currency_code": CURRENCY,
    "ai_context_text": (
        "Two-parent US household with one teenager. Fixed costs (housing, "
        "utilities, insurance, loan payments) are handled outside this budget; "
        "this plan covers discretionary spending and savings only. Approximate "
        "monthly amount available for discretionary spending plus savings is "
        "$3,200-$4,200, higher in September (back-to-school) and December "
        "(holidays). The family had almost no structured savings until recently, "
        "so the starting balance is modest. They want a $5,000 cushion by "
        "February 1, 2027 and prefer trading dining out for home cooking and bar "
        "nights for drinks at home rather than deep cuts. Groceries and savings "
        "have hard floors and should not be cut to zero. Both parents share the "
        "savings contribution."
    ),
}

members = []
for k, name, short, can in MEMBERS:
    members.append({
        "id": mem_id[k], "role": k, "display_name": name,
        "short_name": short, "can_propose": can,
    })

categories = []
for k, name, order, hard, _ in CATEGORIES:
    categories.append({
        "id": cat_id[k], "name": name, "sort_order": order,
        "is_hard_floor": hard,
    })

goal = {
    "id": uid("goal:main"),
    "name": "Family savings cushion",
    "target_amount_minor": GOAL_TARGET,
    "target_date": GOAL_TARGET_DATE,
    "saved_amount_minor": GOAL_SAVED_START,
    "plan_months": list(FUT_MONTHS),
}

spend_summaries = []
for ck in [c[0] for c in CATEGORIES if c[0] in HIST]:
    for i, ym in enumerate(HIST_MONTHS):
        start, end = month_bounds(ym)
        for mk, cents in split_cents(HIST[ck][i], OWNERSHIP[ck]):
            spend_summaries.append({
                "id": summary_id(mk, ck, ym),
                "source": "historical_reference",
                "granularity": "month",
                "period_start": start,
                "period_end": end,
                "member_id": mem_id[mk],
                "category_id": cat_id[ck],
                "actual_amount_minor": cents,
            })

# budget_items, and remember planned amounts so the proposal can reference them
planned = {}   # (mk, ck, ym) -> cents
budget_items = []
LOCKED = {("teen_1", "entertainment", "2026-09")}   # one locked item for testing
for ck, _, _, _, _ in CATEGORIES:
    for i, ym in enumerate(FUT_MONTHS):
        for mk, cents in split_cents(FUT[ck][i], OWNERSHIP[ck]):
            planned[(mk, ck, ym)] = cents
            item = {
                "id": budget_id(mk, ck, ym),
                "member_id": mem_id[mk],
                "category_id": cat_id[ck],
                "month": ym,
                "planned_amount_minor": cents,
                "floor_amount_minor": int(cents * floor_ratio[ck]),
            }
            if (mk, ck, ym) in LOCKED:
                item["is_locked"] = True
            budget_items.append(item)

# One pending proposal: Parent 1 asks Parent 2 to eat out $120 less in Sep,
# moving $40 to groceries (cook more) and $80 to savings. Nets to zero.
def change(mk, ck, ym, delta):
    before = planned[(mk, ck, ym)]
    return {
        "budget_item_id": budget_id(mk, ck, ym),
        "delta_amount_minor": delta,
        "amount_before_minor": before,
        "amount_after_minor": before + delta,
    }

proposals = [{
    "id": uid("proposal:prop_001"),
    "month": "2026-09",
    "proposer_member_id": mem_id["parent_1"],
    "required_responder_member_ids": [mem_id["parent_2"]],
    "status": "pending",
    "description": ("Eat out a little less this month: move $120 out of Parent 2's "
                    "dining -- $40 into groceries for home cooking and $80 into savings."),
    "ai_rationale": ("September runs high on back-to-school costs, so savings is "
                     "budgeted low. Trimming $120 of dining and cooking more at home "
                     "recovers $80 toward the $5,000 goal while keeping every affected "
                     "category above its floor."),
    "created_at": "2026-08-28T15:30:00Z",
    "changes": [
        change("parent_2", "dining",    "2026-09", -12000),
        change("parent_1", "groceries", "2026-09",  +4000),
        change("parent_2", "savings",   "2026-09",  +8000),
    ],
}]

fixture = {
    "contract_version": "1.0.0",
    "demo_clock": {"today": "2026-09-01", "current_month": "2026-09"},
    "household": household,
    "members": members,
    "categories": categories,
    "goal": goal,
    "spend_summaries": spend_summaries,
    "budget_items": budget_items,
    "proposals": proposals,
}

print(json.dumps(fixture, indent=2, ensure_ascii=False))
