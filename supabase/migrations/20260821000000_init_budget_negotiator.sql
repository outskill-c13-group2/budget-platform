-- Budget Negotiator MVP: Supabase schema
-- Contract companion: fixture.schema.json (contract_version 1.0.0)
-- DEV/demo only. The MVP has no authentication; do not expose this schema to a
-- public production environment without RLS, authenticated identities, and a
-- reviewed authorization model.

create extension if not exists pgcrypto;

create table if not exists household (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  currency_code char(3) not null check (currency_code ~ '^[A-Z]{3}$'),
  ai_context_text text not null check (char_length(ai_context_text) between 1 and 2000),
  created_at timestamptz not null default now()
);

create table if not exists member (
  id uuid primary key default gen_random_uuid(),
  household_id uuid not null references household(id) on delete cascade,
  role text not null check (role in ('parent_1', 'parent_2', 'teen_1')),
  display_name text not null,
  short_name text,
  can_propose boolean not null,
  created_at timestamptz not null default now(),
  unique (household_id, role)
);

create table if not exists category (
  id uuid primary key default gen_random_uuid(),
  household_id uuid not null references household(id) on delete cascade,
  name text not null,
  sort_order integer not null check (sort_order > 0),
  is_hard_floor boolean not null default false,
  created_at timestamptz not null default now(),
  unique (household_id, name),
  unique (household_id, sort_order)
);

create table if not exists goal (
  id uuid primary key default gen_random_uuid(),
  household_id uuid not null references household(id) on delete cascade,
  name text not null,
  target_amount_minor bigint not null check (target_amount_minor >= 0),
  target_date date not null,
  saved_amount_minor bigint not null check (saved_amount_minor >= 0),
  created_at timestamptz not null default now()
);

create table if not exists goal_plan_month (
  goal_id uuid not null references goal(id) on delete cascade,
  month date not null check (month = date_trunc('month', month)::date),
  primary key (goal_id, month)
);

create table if not exists spend_summary (
  id uuid primary key default gen_random_uuid(),
  household_id uuid not null references household(id) on delete cascade,
  member_id uuid not null references member(id),
  category_id uuid not null references category(id),
  source text not null check (source in ('historical_reference', 'weekly_import')),
  granularity text not null check (granularity in ('month', 'week')),
  period_start date not null,
  period_end date not null check (period_end >= period_start),
  actual_amount_minor bigint not null check (actual_amount_minor >= 0),
  created_at timestamptz not null default now(),
  unique (household_id, member_id, category_id, source, granularity, period_start, period_end)
);

create table if not exists budget_item (
  id uuid primary key default gen_random_uuid(),
  household_id uuid not null references household(id) on delete cascade,
  goal_id uuid not null references goal(id) on delete cascade,
  member_id uuid not null references member(id),
  category_id uuid not null references category(id),
  month date not null check (month = date_trunc('month', month)::date),
  planned_amount_minor bigint not null check (planned_amount_minor >= 0),
  floor_amount_minor bigint not null check (floor_amount_minor >= 0),
  is_locked boolean not null default false,
  updated_at timestamptz not null default now(),
  check (planned_amount_minor >= floor_amount_minor),
  unique (goal_id, member_id, category_id, month)
);

create table if not exists proposal (
  id uuid primary key default gen_random_uuid(),
  household_id uuid not null references household(id) on delete cascade,
  goal_id uuid not null references goal(id) on delete cascade,
  month date not null check (month = date_trunc('month', month)::date),
  proposer_member_id uuid not null references member(id),
  required_responder_member_ids uuid[] not null check (cardinality(required_responder_member_ids) > 0),
  status text not null check (status in ('draft', 'pending', 'agreed', 'declined')),
  description text,
  ai_rationale text,
  created_at timestamptz not null default now(),
  resolved_at timestamptz
);

create table if not exists proposal_decision (
  proposal_id uuid not null references proposal(id) on delete cascade,
  member_id uuid not null references member(id),
  decision text not null check (decision in ('agreed', 'declined')),
  decided_at timestamptz not null default now(),
  primary key (proposal_id, member_id)
);

create table if not exists proposal_change (
  proposal_id uuid not null references proposal(id) on delete cascade,
  budget_item_id uuid not null references budget_item(id),
  delta_amount_minor bigint not null,
  amount_before_minor bigint not null check (amount_before_minor >= 0),
  amount_after_minor bigint not null check (amount_after_minor >= 0),
  primary key (proposal_id, budget_item_id),
  check (amount_after_minor = amount_before_minor + delta_amount_minor)
);

create index if not exists spend_summary_reporting_idx
  on spend_summary (household_id, member_id, category_id, period_start);

create index if not exists budget_item_month_idx
  on budget_item (goal_id, month, category_id, member_id);

create index if not exists proposal_inbox_idx
  on proposal (household_id, status, month, created_at desc);

-- The only state-changing path for a pending proposal. It creates a decision,
-- rejects invalid rebalance arithmetic, and updates the live budget atomically.
create or replace function agree_to_proposal(
  p_proposal_id uuid,
  p_responder_member_id uuid
)
returns proposal
language plpgsql
as $$
declare
  v_proposal proposal;
  v_change_count integer;
  v_delta_total bigint;
  v_pending_responder_count integer;
begin
  select * into v_proposal
  from proposal
  where id = p_proposal_id
  for update;

  if not found then
    raise exception 'Proposal % does not exist', p_proposal_id;
  end if;

  if v_proposal.status <> 'pending' then
    raise exception 'Proposal % is not pending', p_proposal_id;
  end if;

  if not (p_responder_member_id = any(v_proposal.required_responder_member_ids)) then
    raise exception 'Member % is not a required responder for proposal %', p_responder_member_id, p_proposal_id;
  end if;

  insert into proposal_decision (proposal_id, member_id, decision)
  values (p_proposal_id, p_responder_member_id, 'agreed');

  select count(*), coalesce(sum(delta_amount_minor), 0)
    into v_change_count, v_delta_total
  from proposal_change
  where proposal_id = p_proposal_id;

  if v_change_count < 2 or v_delta_total <> 0 then
    raise exception 'Proposal % must contain at least two changes that net to zero', p_proposal_id;
  end if;

  perform 1
  from proposal_change pc
  join budget_item bi on bi.id = pc.budget_item_id
  where pc.proposal_id = p_proposal_id
    and (bi.planned_amount_minor <> pc.amount_before_minor
      or pc.amount_after_minor < bi.floor_amount_minor);

  if found then
    raise exception 'Proposal % is stale or would breach a budget floor', p_proposal_id;
  end if;

  select count(*) into v_pending_responder_count
  from unnest(v_proposal.required_responder_member_ids) responder_id
  where not exists (
    select 1
    from proposal_decision pd
    where pd.proposal_id = p_proposal_id
      and pd.member_id = responder_id
      and pd.decision = 'agreed'
  );

  if v_pending_responder_count > 0 then
    return v_proposal;
  end if;

  update budget_item bi
  set planned_amount_minor = pc.amount_after_minor,
      updated_at = now()
  from proposal_change pc
  where pc.proposal_id = p_proposal_id
    and pc.budget_item_id = bi.id;

  update proposal
  set status = 'agreed', resolved_at = now()
  where id = p_proposal_id
  returning * into v_proposal;

  return v_proposal;
end;
$$;

comment on function agree_to_proposal(uuid, uuid) is
  'DEV/demo atomic proposal agreement. App and n8n must call this function instead of updating budget_item directly for a proposal agreement.';
