create extension if not exists pgcrypto;

create table if not exists letters (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null unique,
  title text not null,
  body_html text not null,
  created_at timestamptz not null default now()
);

create table if not exists reminders (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null unique,
  title text not null,
  description text not null default '',
  tags text[] not null default '{}',
  start_at timestamptz not null,
  end_at timestamptz not null,
  recurrence text not null default 'none' check (recurrence in ('none', 'daily', 'weekly', 'monthly')),
  created_at timestamptz not null default now(),
  check (end_at > start_at)
);

create table if not exists wallets (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null unique,
  name text not null,
  target numeric(14,2),
  created_at timestamptz not null default now()
);

create table if not exists transactions (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null unique,
  wallet_id uuid references wallets(id) on delete cascade,
  type text not null check (type in ('deposit', 'withdraw')),
  amount numeric(14,2) not null check (amount > 0),
  merchant text not null default '',
  note text not null default '',
  occurred_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);

alter table letters add column if not exists client_id uuid;
alter table reminders add column if not exists client_id uuid;
alter table wallets add column if not exists client_id uuid;
alter table transactions add column if not exists client_id uuid;

create unique index if not exists letters_client_id_idx on letters(client_id);
create unique index if not exists reminders_client_id_idx on reminders(client_id);
create unique index if not exists wallets_client_id_idx on wallets(client_id);
create unique index if not exists transactions_client_id_idx on transactions(client_id);

create index if not exists reminders_start_at_idx on reminders(start_at);
create index if not exists transactions_occurred_at_idx on transactions(occurred_at);
create index if not exists transactions_wallet_id_idx on transactions(wallet_id);
