-- Review queue storage for parsed statement validation issues.

create extension if not exists pgcrypto;

create table if not exists public.review_queue (
    id uuid primary key default gen_random_uuid(),
    statement_id uuid not null,
    user_id uuid not null references auth.users(id) on delete cascade,
    bank_id text not null,
    account_number text,
    row_number integer,
    flag_code text not null,
    flag_message text not null,
    flag_severity text not null check (flag_severity in ('info', 'warning', 'error')),
    transaction_snapshot jsonb,
    status text not null default 'open' check (status in ('open', 'resolved', 'rejected')),
    assigned_to text,
    notes jsonb not null default '[]'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_review_queue_user_status
on public.review_queue (user_id, status);

create index if not exists idx_review_queue_statement
on public.review_queue (statement_id, row_number);

create index if not exists idx_review_queue_flag_code
on public.review_queue (flag_code);

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists trg_review_queue_updated_at on public.review_queue;

create trigger trg_review_queue_updated_at
before update on public.review_queue
for each row
execute function public.set_updated_at();

alter table public.review_queue enable row level security;

drop policy if exists "Users can read their review queue items" on public.review_queue;
create policy "Users can read their review queue items"
on public.review_queue
for select
to authenticated
using (auth.uid() = user_id);

drop policy if exists "Users can insert their review queue items" on public.review_queue;
create policy "Users can insert their review queue items"
on public.review_queue
for insert
to authenticated
with check (auth.uid() = user_id);

drop policy if exists "Users can update their review queue items" on public.review_queue;
create policy "Users can update their review queue items"
on public.review_queue
for update
to authenticated
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

drop policy if exists "Users can delete their review queue items" on public.review_queue;
create policy "Users can delete their review queue items"
on public.review_queue
for delete
to authenticated
using (auth.uid() = user_id);
