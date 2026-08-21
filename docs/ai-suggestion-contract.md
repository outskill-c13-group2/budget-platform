# AI negotiation assistant — output contract, prompt, and one-click write

The AI produces a **structured suggestion**; a player accepts it with one click;
the app turns it into a proposal and applies it through `agree_to_proposal`. The
AI never writes to the database — it only proposes numbers the function then
validates.

This is independent of *where* the AI call runs (n8n node or the edge function) —
the contract and prompt are the same either way.

---

## 1. End-to-end flow

```
user text  ->  backend injects current allowances + rules  ->  OpenAI
           ->  { reply, suggestion } JSON  ->  Lovable shows reply + Accept button
Accept click  ->  app creates proposal from suggestion  ->  agree_to_proposal(...)
              ->  budget updates; UI refreshes
```

## 2. What the AI returns (the contract)

A single JSON object, nothing else — no markdown, no code fences:

```json
{
  "reply": "One or two friendly, spoken-style sentences explaining the move.",
  "suggestion": {
    "month": "2026-09",
    "changes": [
      { "member": "teen_1",   "category": "Shopping & apparel", "delta_dollars": 200 },
      { "member": "parent_1", "category": "Shopping & apparel", "delta_dollars": -100 },
      { "member": "parent_2", "category": "Shopping & apparel", "delta_dollars": -100 }
    ]
  },
  "needs_clarification": false
}
```

- `changes` has **at least two** entries and the `delta_dollars` **sum to zero**.
- `member` is a role that exists in the context; `category` is an exact category
  name from the context; `month` is the context month.
- If no valid move fits, `suggestion` is `null` and `needs_clarification` is
  `true`, with the ask explained in `reply`.

The example nets to zero (200 − 100 − 100 = 0) and stays above floors (parents
$168 → $68, floor ~$50; teen $144 → $344). ✓

## 3. System prompt (paste into the OpenAI node / edge function)

```
You are a family budget negotiation assistant. Each family member has a monthly
allowance per spending category, in whole dollars. A negotiation moves allowance
between people and MUST net to zero — category and household totals never change.
You help the family decide who gives up allowance so someone else can spend more.

You will be given the current month, the members, and each member's current
allowance and floor for that month. Use ONLY the members and categories that
appear in the context. Never let any allowance fall below its floor.

Respond with a SINGLE JSON object and nothing else (no prose outside it, no code
fences), in this exact shape:
{
  "reply": "<1-2 friendly, spoken-style sentences>",
  "suggestion": {           // null if you cannot make a valid move
    "month": "<the context month>",
    "changes": [            // at least 2 entries; delta_dollars MUST sum to 0
      { "member": "<role from context>", "category": "<exact category name>", "delta_dollars": <integer> }
    ]
  },
  "needs_clarification": <true|false>
}

Hard rules:
- The delta_dollars across all changes MUST total exactly 0.
- After applying, no allowance may drop below that line's floor (given in context).
- Whole-dollar amounts only.
- Reference only member+category lines present in the context.
- If the request can't be met within these rules, set "suggestion" to null,
  "needs_clarification" to true, and say what you need in "reply".
```

## 4. Context the backend must inject (before the user's text)

Build this from the current month's budget lines (which you already have in
Supabase / the fixture):

```
Month: 2026-09
Members: parent_1 (Parent 1), parent_2 (Parent 2), teen_1 (Teen 1)
Allowances (member | category | allowance $ | floor $):
parent_1 | Groceries | 900 | 765
parent_1 | Dining out & takeout | 224 | 89
... (every line for the month) ...
teen_1 | Shopping & apparel | 144 | 43

User said: "<the dictated text>"
```

Passing the floors is what lets the AI avoid illegal cuts. Passing only the
current month keeps it focused.

## 5. The one-click Accept → write path

When the player taps Accept, the app (Supabase client) does:

1. For each change, resolve `(member, category, month)` to its `budget_item` and
   read the current `planned_amount_minor` (= `amount_before`). Compute
   `amount_after = before + delta_dollars * 100`.
2. Insert a `proposal` (status `pending`) and its `proposal_change` rows
   (with before/after in minor units).
3. Call the guarded function for the required responder(s):
   ```sql
   select agree_to_proposal('<proposal_id>', '<responder_member_id>');
   ```

`agree_to_proposal` re-checks everything (net-zero, floors, not stale) and only
then updates the budget — so even if the AI ever suggested something invalid, the
database refuses it. The AI's numbers are a proposal, never a direct write.

## 6. One open decision — who proposes, who agrees (a UX call for the team)

A proposal has a proposer and required responders, and the function needs each
required responder to agree before it applies. For the demo, pick one:

- **Truest to the model:** the members who *give up* allowance are the required
  responders; each taps Accept. (Two parents giving up = two accepts.)
- **Single-click shortcut:** treat the one Accept as agreement from all required
  responders and apply immediately. Simpler to demo; less true to a real
  multi-party negotiation.

Either way the write is the same function. This is the Lovable builder's +
architect's call, not a data question.
```
