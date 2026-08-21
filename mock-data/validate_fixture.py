#!/usr/bin/env python3
"""
Validate a Budget Negotiator fixture (contract_version 1.0.0) with no external
dependencies. Checks three layers:

  1. Shape   - types, required fields, id/month/date/currency patterns, enums,
               no unexpected keys, minItems / uniqueness rules.
  2. Cross-record - every id reference resolves; budget items unique per
               member+category+month; proposals net to zero; no change drops a
               budget below its floor; proposal "before" matches current budget.
  3. Intent  - starting balance + all future savings budgets == the $5,000 goal.

Usage:  python3 validate_fixture.py budget-fixture.sample.json
Exit code 0 = pass, 1 = fail.
"""
import json, re, sys, calendar

ID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
MONTH = re.compile(r"^[0-9]{4}-(0[1-9]|1[0-2])$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATETIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(Z|[+-]\d{2}:\d{2})$")
CUR = re.compile(r"^[A-Z]{3}$")

errors, warnings = [], []
def err(m): errors.append(m)
def warn(m): warnings.append(m)

def keys_ok(obj, name, required, optional):
    allowed = set(required) | set(optional)
    for r in required:
        if r not in obj: err(f"{name}: missing required field '{r}'")
    for k in obj:
        if k not in allowed: err(f"{name}: unexpected field '{k}'")

def is_int(v): return isinstance(v, int) and not isinstance(v, bool)
def nonneg(v): return is_int(v) and v >= 0

def main(path):
    d = json.load(open(path, encoding="utf-8"))

    if d.get("contract_version") != "1.0.0":
        err(f"contract_version must be '1.0.0', got {d.get('contract_version')!r}")

    top_req = ["contract_version","demo_clock","household","members","categories",
               "goal","spend_summaries","budget_items","proposals"]
    keys_ok(d, "root", top_req, [])

    # demo_clock
    dc = d.get("demo_clock", {})
    keys_ok(dc, "demo_clock", ["today","current_month"], [])
    if not DATE.match(dc.get("today","")): err("demo_clock.today not a date")
    if not MONTH.match(dc.get("current_month","")): err("demo_clock.current_month not YYYY-MM")

    # household
    h = d.get("household", {})
    keys_ok(h, "household", ["id","name","currency_code","ai_context_text"], [])
    if not ID.match(h.get("id","")): err("household.id not a UUID")
    if not CUR.match(h.get("currency_code","")): err("household.currency_code invalid")
    if not (1 <= len(h.get("ai_context_text","")) <= 2000): err("ai_context_text length out of range")
    currency = h.get("currency_code")

    # members
    member_ids, roles = set(), set()
    for m in d.get("members", []):
        keys_ok(m, "member", ["id","role","display_name","can_propose"], ["short_name"])
        if not ID.match(m.get("id","")): err(f"member id not UUID: {m.get('id')}")
        if m.get("role") not in ("parent_1","parent_2","teen_1"): err(f"member role invalid: {m.get('role')}")
        if m.get("role") in roles: err(f"duplicate member role: {m.get('role')}")
        roles.add(m.get("role"))
        if not isinstance(m.get("can_propose"), bool): err("can_propose must be bool")
        member_ids.add(m["id"])
    if not d.get("members"): err("members must have at least 1 item")

    # categories
    category_ids, cat_names, cat_orders = set(), set(), set()
    savings_cat = None
    for c in d.get("categories", []):
        keys_ok(c, "category", ["id","name","sort_order"], ["is_hard_floor"])
        if not ID.match(c.get("id","")): err(f"category id not UUID: {c.get('id')}")
        if not is_int(c.get("sort_order")) or c.get("sort_order") < 1: err("sort_order must be int >=1")
        if c.get("name") in cat_names: err(f"duplicate category name: {c.get('name')}")
        if c.get("sort_order") in cat_orders: err(f"duplicate sort_order: {c.get('sort_order')}")
        cat_names.add(c.get("name")); cat_orders.add(c.get("sort_order"))
        category_ids.add(c["id"])
        if c.get("name","").lower() == "savings": savings_cat = c["id"]

    # goal
    g = d.get("goal", {})
    keys_ok(g, "goal", ["id","name","target_amount_minor","target_date","saved_amount_minor","plan_months"], [])
    if not ID.match(g.get("id","")): err("goal.id not UUID")
    if not nonneg(g.get("target_amount_minor")): err("target_amount_minor must be non-negative int")
    if not nonneg(g.get("saved_amount_minor")): err("saved_amount_minor must be non-negative int")
    if not DATE.match(g.get("target_date","")): err("goal.target_date not a date")
    pm = g.get("plan_months", [])
    if not pm: err("goal.plan_months must have >=1")
    if len(pm) != len(set(pm)): err("goal.plan_months must be unique")
    for x in pm:
        if not MONTH.match(x): err(f"plan_month not YYYY-MM: {x}")

    # spend_summaries
    for s in d.get("spend_summaries", []):
        keys_ok(s, "spend_summary",
                ["id","source","granularity","period_start","period_end","member_id","category_id","actual_amount_minor"], [])
        if not ID.match(s.get("id","")): err(f"summary id not UUID: {s.get('id')}")
        if s.get("source") not in ("historical_reference","weekly_import"): err(f"bad source: {s.get('source')}")
        if s.get("granularity") not in ("month","week"): err(f"bad granularity: {s.get('granularity')}")
        if not DATE.match(s.get("period_start","")): err("summary period_start not a date")
        if not DATE.match(s.get("period_end","")): err("summary period_end not a date")
        if s.get("period_end","") < s.get("period_start",""): err("summary period_end before period_start")
        if s.get("member_id") not in member_ids: err(f"summary references unknown member {s.get('member_id')}")
        if s.get("category_id") not in category_ids: err(f"summary references unknown category {s.get('category_id')}")
        if not nonneg(s.get("actual_amount_minor")): err("actual_amount_minor must be non-negative int")
    if not d.get("spend_summaries"): err("spend_summaries must have >=1")

    # budget_items
    bi_by_id, planned, floor, seen_mcm = {}, {}, {}, set()
    for b in d.get("budget_items", []):
        keys_ok(b, "budget_item",
                ["id","member_id","category_id","month","planned_amount_minor","floor_amount_minor"], ["is_locked"])
        if not ID.match(b.get("id","")): err(f"budget_item id not UUID: {b.get('id')}")
        if b.get("member_id") not in member_ids: err(f"budget_item unknown member {b.get('member_id')}")
        if b.get("category_id") not in category_ids: err(f"budget_item unknown category {b.get('category_id')}")
        if not MONTH.match(b.get("month","")): err(f"budget_item month not YYYY-MM: {b.get('month')}")
        if not nonneg(b.get("planned_amount_minor")): err("planned_amount_minor must be non-negative int")
        if not nonneg(b.get("floor_amount_minor")): err("floor_amount_minor must be non-negative int")
        if is_int(b.get("planned_amount_minor")) and is_int(b.get("floor_amount_minor")):
            if b["planned_amount_minor"] < b["floor_amount_minor"]:
                err(f"budget_item {b['id']}: planned below floor")
        key = (b.get("member_id"), b.get("category_id"), b.get("month"))
        if key in seen_mcm: err(f"duplicate budget_item for member/category/month {key}")
        seen_mcm.add(key)
        bi_by_id[b["id"]] = b
        planned[b["id"]] = b.get("planned_amount_minor")
        floor[b["id"]] = b.get("floor_amount_minor")
    if not d.get("budget_items"): err("budget_items must have >=1")

    # proposals
    for p in d.get("proposals", []):
        keys_ok(p, "proposal",
                ["id","month","proposer_member_id","required_responder_member_ids","status","changes","created_at"],
                ["description","ai_rationale","resolved_at","decisions"])
        if not ID.match(p.get("id","")): err(f"proposal id not UUID: {p.get('id')}")
        if not MONTH.match(p.get("month","")): err("proposal month not YYYY-MM")
        if p.get("proposer_member_id") not in member_ids: err("proposal proposer unknown")
        rr = p.get("required_responder_member_ids", [])
        if not rr: err("required_responder_member_ids must have >=1")
        if len(rr) != len(set(rr)): err("required_responder_member_ids must be unique")
        for r in rr:
            if r not in member_ids: err(f"proposal responder unknown: {r}")
        if p.get("status") not in ("draft","pending","agreed","declined"): err(f"bad status: {p.get('status')}")
        if not DATETIME.match(p.get("created_at","")): err(f"proposal created_at not date-time: {p.get('created_at')}")
        changes = p.get("changes", [])
        if len(changes) < 2: err(f"proposal {p.get('id')} needs >=2 changes")
        net = 0
        for ch in changes:
            keys_ok(ch, "proposal_change",
                    ["budget_item_id","delta_amount_minor","amount_before_minor","amount_after_minor"], [])
            bid = ch.get("budget_item_id")
            if bid not in bi_by_id: err(f"change references unknown budget_item {bid}"); continue
            if not is_int(ch.get("delta_amount_minor")): err("delta_amount_minor must be int")
            if not nonneg(ch.get("amount_before_minor")): err("amount_before_minor must be non-negative int")
            if not nonneg(ch.get("amount_after_minor")): err("amount_after_minor must be non-negative int")
            if ch["amount_after_minor"] != ch["amount_before_minor"] + ch["delta_amount_minor"]:
                err(f"change arithmetic wrong for {bid}: after != before + delta")
            # staleness: recorded before must match the live budget item
            if ch["amount_before_minor"] != planned.get(bid):
                err(f"change stale: before {ch['amount_before_minor']} != current planned {planned.get(bid)} ({bid})")
            # floor: resulting amount must stay at/above the member floor
            if ch["amount_after_minor"] < floor.get(bid, 0):
                err(f"change would breach floor for {bid}")
            net += ch["delta_amount_minor"]
        if net != 0:
            err(f"proposal {p.get('id')} changes do not net to zero (net={net})")

    # intent: starting balance + all future savings budgets == the goal target
    if savings_cat:
        saved_future = sum(b["planned_amount_minor"] for b in d["budget_items"]
                           if b["category_id"] == savings_cat and b["month"] in pm)
        total = g.get("saved_amount_minor", 0) + saved_future
        if total != g.get("target_amount_minor"):
            err(f"goal math off: start {g.get('saved_amount_minor')} + future savings "
                f"{saved_future} = {total}, target {g.get('target_amount_minor')}")
        else:
            print(f"  goal math ok: ${g['saved_amount_minor']/100:,.0f} start + "
                  f"${saved_future/100:,.0f} future savings = ${total/100:,.0f} target")
    else:
        warn("no 'Savings' category found; skipped goal-math check")

    # report
    print(f"\nChecked: {len(d['members'])} members, {len(d['categories'])} categories, "
          f"{len(d['spend_summaries'])} summaries, {len(d['budget_items'])} budget items, "
          f"{len(d['proposals'])} proposal(s).")
    for w in warnings: print("  WARNING:", w)
    if errors:
        print(f"\nFAIL - {len(errors)} problem(s):")
        for e in errors: print("  -", e)
        return 1
    print("\nPASS - all shape, cross-record, and goal-math checks passed.")
    return 0

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "budget-fixture.sample.json"
    sys.exit(main(path))
