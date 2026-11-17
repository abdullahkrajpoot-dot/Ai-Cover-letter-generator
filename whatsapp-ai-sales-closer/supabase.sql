-- Run in Supabase Dashboard > SQL Editor.
create table if not exists public.leads (
  phone_number text primary key,
  last_message text not null,
  ai_reply text not null,
  lead_status text not null default 'New',
  updated_at timestamptz not null default now()
);

create table if not exists public.conversation_messages (
  id bigint generated always as identity primary key,
  phone_number text not null references public.leads(phone_number) on delete cascade,
  role text not null check (role in ('user', 'model')),
  content text not null,
  created_at timestamptz not null default now()
);

create index if not exists conversation_messages_phone_created_idx
  on public.conversation_messages (phone_number, created_at desc);

create table if not exists public.processed_messages (
  message_id text primary key,
  phone_number text not null,
  processed_at timestamptz not null default now()
);

-- This server uses the service-role key, which bypasses RLS. Keep that key server-side.
alter table public.leads enable row level security;
alter table public.conversation_messages enable row level security;
alter table public.processed_messages enable row level security;
