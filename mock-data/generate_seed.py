#!/usr/bin/env python3
"""
Emit seed.sql from budget-fixture.sample.json.

Generating the SQL from the JSON (instead of hand-writing it) guarantees the
seed can never drift out of sync with the validated fixture. Re-run whenever the
fixture changes.

Key behaviours:
- Inserts every id EXPLICITLY, so Supabase keeps the fixture's UUIDs instead of
  generating new ones (foreign keys already match).
- Adds household_id / goal_id to child rows the flat fixture doesn't carry
  (there is exactly one household and one goal).
- Converts "YYYY-MM" months to first-of-month dates for the SQL date columns.
- Does NOT apply the pending proposal's changes to budget_item. Those live in
  proposal_change only; budget_item is updated solely by agree_to_proposal().

Run:  python3 generate_seed.py > seed.sql
"""
import json, sys

# Input fixture defaults to the testing set; pass a filename to build another
# (e.g. python3 generate_seed.py budget-fixture.demo.json > seed.demo.sql).
_src = sys.argv[1] if len(sys.argv) > 1 else "budget-fixture.sample.json"
d = json.load(open(_src, encoding="utf-8"))

def q(s):            # quote + escape a SQL string literal
    return "'" + str(s).replace("'", "''") + "'"
def b(v):            # boolean
    return "true" if v else "false"
def mdate(ym):       # "2026-09" -> '2026-09-01'
    return f"'{ym}-01'"

hh = d["household"]["id"]
goal = d["goal"]["id"]
out = []
w = out.append

w("-- seed.sql  |  Budget Negotiator MVP mock data (contract_version 1.0.0)")
w("-- Generated from budget-fixture.sample.json by generate_seed.py -- do not hand-edit.")
w("-- Run supabase-mvp-schema.sql first, then load this into an EMPTY set of tables.")
w("")
w("-- Optional reset (destructive) -- uncomment to reload from scratch:")
w("-- truncate proposal_change, proposal_decision, proposal, budget_item,")
w("--   spend_summary, goal_plan_month, goal, category, member, household restart identity cascade;")
w("")
w("begin;")
w("")

# household
w("insert into household (id, name, currency_code, ai_context_text) values")
w(f"  ({q(hh)}, {q(d['household']['name'])}, {q(d['household']['currency_code'])}, {q(d['household']['ai_context_text'])});")
w("")

# member
w("insert into member (id, household_id, role, display_name, short_name, can_propose) values")
rows = [f"  ({q(m['id'])}, {q(hh)}, {q(m['role'])}, {q(m['display_name'])}, "
        f"{q(m.get('short_name')) if m.get('short_name') else 'null'}, {b(m['can_propose'])})"
        for m in d["members"]]
w(",\n".join(rows) + ";")
w("")

# category
w("insert into category (id, household_id, name, sort_order, is_hard_floor) values")
rows = [f"  ({q(c['id'])}, {q(hh)}, {q(c['name'])}, {c['sort_order']}, {b(c.get('is_hard_floor', False))})"
        for c in d["categories"]]
w(",\n".join(rows) + ";")
w("")

# goal
g = d["goal"]
w("insert into goal (id, household_id, name, target_amount_minor, target_date, saved_amount_minor) values")
w(f"  ({q(g['id'])}, {q(hh)}, {q(g['name'])}, {g['target_amount_minor']}, "
  f"{q(g['target_date'])}, {g['saved_amount_minor']});")
w("")

# goal_plan_month
w("insert into goal_plan_month (goal_id, month) values")
rows = [f"  ({q(goal)}, {mdate(m)})" for m in g["plan_months"]]
w(",\n".join(rows) + ";")
w("")

# spend_summary
w("insert into spend_summary (id, household_id, member_id, category_id, source, granularity, "
  "period_start, period_end, actual_amount_minor) values")
rows = [f"  ({q(s['id'])}, {q(hh)}, {q(s['member_id'])}, {q(s['category_id'])}, "
        f"{q(s['source'])}, {q(s['granularity'])}, {q(s['period_start'])}, {q(s['period_end'])}, "
        f"{s['actual_amount_minor']})" for s in d["spend_summaries"]]
w(",\n".join(rows) + ";")
w("")

# budget_item
w("insert into budget_item (id, household_id, goal_id, member_id, category_id, month, "
  "planned_amount_minor, floor_amount_minor, is_locked) values")
rows = [f"  ({q(bi['id'])}, {q(hh)}, {q(goal)}, {q(bi['member_id'])}, {q(bi['category_id'])}, "
        f"{mdate(bi['month'])}, {bi['planned_amount_minor']}, {bi['floor_amount_minor']}, "
        f"{b(bi.get('is_locked', False))})" for bi in d["budget_items"]]
w(",\n".join(rows) + ";")
w("")

# proposal + children
for p in d["proposals"]:
    arr = "array[" + ", ".join(q(r) for r in p["required_responder_member_ids"]) + "]::uuid[]"
    desc = q(p["description"]) if p.get("description") else "null"
    rat = q(p["ai_rationale"]) if p.get("ai_rationale") else "null"
    resolved = q(p["resolved_at"]) if p.get("resolved_at") else "null"
    w("insert into proposal (id, household_id, goal_id, month, proposer_member_id, "
      "required_responder_member_ids, status, description, ai_rationale, created_at, resolved_at) values")
    w(f"  ({q(p['id'])}, {q(hh)}, {q(goal)}, {mdate(p['month'])}, {q(p['proposer_member_id'])}, "
      f"{arr}, {q(p['status'])}, {desc}, {rat}, {q(p['created_at'])}, {resolved});")
    w("")
    for dec in p.get("decisions", []):
        w("insert into proposal_decision (proposal_id, member_id, decision, decided_at) values")
        w(f"  ({q(p['id'])}, {q(dec['member_id'])}, {q(dec['decision'])}, {q(dec['decided_at'])});")
        w("")
    w("insert into proposal_change (proposal_id, budget_item_id, delta_amount_minor, "
      "amount_before_minor, amount_after_minor) values")
    rows = [f"  ({q(p['id'])}, {q(ch['budget_item_id'])}, {ch['delta_amount_minor']}, "
            f"{ch['amount_before_minor']}, {ch['amount_after_minor']})" for ch in p["changes"]]
    w(",\n".join(rows) + ";")
    w("")

w("commit;")
w("")
sys.stdout.write("\n".join(out))
