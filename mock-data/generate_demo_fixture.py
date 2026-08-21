#!/usr/bin/env python3
"""
Generate the CLEAN DEMO fixture (contract_version 1.0.0).

Differences from the testing fixture (generate_fixture.py):
- 7 categories only. Savings is NOT a grid category; the goal is tracked as a
  single number elsewhere.
- goal.saved_amount_minor = 0. The available savings is entered by a member at
  setup (the first user interaction), not seeded.
- proposals = []. September starts at baseline allowances with NO negotiation
  activity, so the whole propose-then-agree flow can be demonstrated live.
- Shopping & apparel floors are lower, so the live clothing rebalance
  (Teen 1 +$200, each parent -$100) clears the floor with comfortable headroom.
- No locked budget items.

Money is integer cents. IDs are deterministic UUIDv4-shaped values (distinct
from the testing fixture via the 'demo' namespace).

Run:  python3 generate_demo_fixture.py > budget-fixture.demo.json
"""
import json, hashlib, calendar

NS = "outskill-c13-group-2::budget-fixture::demo::v1::"

def uid(slug: str) -> str:
    b = bytearray(hashlib.md5((NS + slug).encode()).digest())
    b[6] = (b[6] & 0x0F) | 0x40
    b[8] = (b[8] & 0x3F) | 0x80
    h = b.hex()
    return f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"

CURRENCY = "USD"

MEMBERS = [  # key(role), display_name, short_name, can_propose
    ("parent_1", "Parent 1", "P1", True),
    ("parent_2", "Parent 2", "P2", True),
    ("teen_1",   "Teen 1",   "Teen", True),
]

# key, name, sort_order, is_hard_floor, floor_ratio  (7 categories, no Savings)
CATEGORIES = [
    ("groceries",     "Groceries",                     1, True,  0.85),
    ("dining",        "Dining out & takeout",          2, False, 0.40),
    ("liquor",        "Liquor store",                  3, False, 0.40),
    ("bars",          "Bars & nightlife",              4, False, 0.40),
    ("entertainment", "Entertainment & subscriptions", 5, False, 0.50),
    ("shopping",      "Shopping & apparel",            6, False, 0.30),  # widened floor
    ("travel",        "Travel & outings",              7, False, 0.40),
]

OWNERSHIP = {
    "groceries":     [("parent_1", 1.00)],
    "dining":        [("parent_1", 0.40), ("parent_2", 0.40), ("teen_1", 0.20)],
    "liquor":        [("parent_1", 0.30), ("parent_2", 0.70)],
    "bars":          [("parent_2", 1.00)],
    "entertainment": [("parent_1", 0.30), ("parent_2", 0.30), ("teen_1", 0.40)],
    "shopping":      [("parent_1", 0.35), ("parent_2", 0.35), ("teen_1", 0.30)],
    "travel":        [("parent_1", 0.50), ("parent_2", 0.50)],
}

HIST_MONTHS = ["2025-09", "2025-10", "2025-11", "2025-12", "2026-01"]
HIST = {
    "groceries":     [780, 740, 820, 800, 720],
    "dining":        [720, 680, 700, 820, 600],
    "liquor":        [120, 120, 150, 200, 110],
    "bars":          [300, 300, 320, 420, 240],
    "entertainment": [280, 280, 290, 340, 270],
    "shopping":      [560, 360, 420, 840, 320],
    "travel":        [400, 420, 480, 640, 320],
}

FUT_MONTHS = ["2026-09", "2026-10", "2026-11", "2026-12", "2027-01"]
FUT = {  # baseline allowances; no Savings line
    "groceries":     [900, 850, 950, 920, 830],
    "dining":        [560, 520, 540, 620, 440],
    "liquor":        [160, 170, 200, 260, 140],
    "bars":          [180, 180, 190, 260, 120],
    "entertainment": [240, 240, 250, 300, 230],
    "shopping":      [480, 300, 340, 720, 260],
    "travel":        [320, 360, 420, 560, 260],
}

GOAL_TARGET = 500000     # $5,000
GOAL_SAVED_START = 0     # entered by a member at setup, not seeded
GOAL_TARGET_DATE = "2027-02-01"

def split_cents(total_dollars, shares):
    total_cents = total_dollars * 100
    out, allocated = [], 0
    for m, f in shares:
        c = int(total_cents * f)
        out.append([m, c]); allocated += c
    out[0][1] += total_cents - allocated
    return out

def month_bounds(ym):
    y, m = int(ym[:4]), int(ym[5:7])
    return f"{ym}-01", f"{ym}-{calendar.monthrange(y, m)[1]:02d}"

mem_id = {k: uid(f"member:{k}") for k, *_ in MEMBERS}
cat_id = {k: uid(f"category:{k}") for k, *_ in CATEGORIES}
floor_ratio = {k: r for k, _, _, _, r in CATEGORIES}

household = {
    "id": uid("household:main"),
    "name": "Rivera Household",
    "currency_code": CURRENCY,
    "ai_context_text": (
        "Two-parent US household with one teenager, discretionary spending only "
        "(fixed costs are handled outside this budget). The grid tracks each "
        "person's monthly allowance per category as whole amounts; a negotiation "
        "redistributes allowance between people and always nets to zero, leaving "
        "the category and household totals unchanged. Available savings and "
        "progress toward a $5,000 goal (target February 1, 2027) are entered by a "
        "member at setup and shown as a single number, separate from this grid. "
        "September starts at baseline allowances with no negotiations yet, so the "
        "propose-and-agree flow can be demonstrated from a clean slate."
    ),
}

members = [{"id": mem_id[k], "role": k, "display_name": name,
            "short_name": short, "can_propose": can}
           for k, name, short, can in MEMBERS]

categories = [{"id": cat_id[k], "name": name, "sort_order": order,
               "is_hard_floor": hard}
              for k, name, order, hard, _ in CATEGORIES]

goal = {
    "id": uid("goal:main"),
    "name": "Family savings cushion",
    "target_amount_minor": GOAL_TARGET,
    "target_date": GOAL_TARGET_DATE,
    "saved_amount_minor": GOAL_SAVED_START,
    "plan_months": list(FUT_MONTHS),
}

spend_summaries = []
for ck in [c[0] for c in CATEGORIES]:
    for i, ym in enumerate(HIST_MONTHS):
        start, end = month_bounds(ym)
        for mk, cents in split_cents(HIST[ck][i], OWNERSHIP[ck]):
            spend_summaries.append({
                "id": uid(f"summary:{mk}:{ck}:{ym}"),
                "source": "historical_reference", "granularity": "month",
                "period_start": start, "period_end": end,
                "member_id": mem_id[mk], "category_id": cat_id[ck],
                "actual_amount_minor": cents,
            })

budget_items = []
for ck, _, _, _, _ in CATEGORIES:
    for i, ym in enumerate(FUT_MONTHS):
        for mk, cents in split_cents(FUT[ck][i], OWNERSHIP[ck]):
            budget_items.append({
                "id": uid(f"budget:{mk}:{ck}:{ym}"),
                "member_id": mem_id[mk], "category_id": cat_id[ck],
                "month": ym,
                "planned_amount_minor": cents,
                "floor_amount_minor": int(cents * floor_ratio[ck]),
            })

fixture = {
    "contract_version": "1.0.0",
    "demo_clock": {"today": "2026-09-01", "current_month": "2026-09"},
    "household": household,
    "members": members,
    "categories": categories,
    "goal": goal,
    "spend_summaries": spend_summaries,
    "budget_items": budget_items,
    "proposals": [],   # clean slate: no negotiation activity
}

print(json.dumps(fixture, indent=2, ensure_ascii=False))
