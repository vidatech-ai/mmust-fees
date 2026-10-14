-- MMUST fee portal schema (run in the Supabase SQL editor)

create table if not exists admins (
  id uuid primary key default gen_random_uuid(),
  username text unique not null,
  password_hash text not null,
  created_at timestamptz default now()
);

-- One row only: fixed details used on every statement
create table if not exists settings (
  id int primary key default 1 check (id = 1),
  school_name text,
  po_box text,
  logo_url text,
  department text,
  school text,
  programme_type text,
  current_academic_year text,
  current_semester int
);
insert into settings (id) values (1) on conflict do nothing;

create table if not exists students (
  id uuid primary key default gen_random_uuid(),
  reg_number text unique not null,
  name text not null,
  password_hash text not null,
  year_of_study int not null default 1,
  semester int not null default 1,
  photo_url text,
  active boolean default true,
  created_at timestamptz default now()
);

-- The fee you type once per semester; applied to every student
create table if not exists fee_terms (
  id uuid primary key default gen_random_uuid(),
  academic_year text not null,
  semester int not null,
  fee_amount numeric(12,2) not null,
  created_at timestamptz default now(),
  unique (academic_year, semester)
);

-- What each student owes (one row per student per term)
create table if not exists fee_charges (
  id uuid primary key default gen_random_uuid(),
  student_id uuid references students(id) on delete cascade,
  term_id uuid references fee_terms(id) on delete cascade,
  amount numeric(12,2) not null,
  description text,
  created_at timestamptz default now()
);

create table if not exists payments (
  id uuid primary key default gen_random_uuid(),
  student_id uuid references students(id) on delete cascade,
  term_id uuid references fee_terms(id),
  amount numeric(12,2) not null check (amount > 0),
  source text not null default 'paystack',   -- 'paystack' or 'manual'
  paystack_reference text unique,
  status text not null default 'pending',    -- pending / success / failed
  paid_at timestamptz,
  created_at timestamptz default now()
);

-- Every manual edit is recorded here
create table if not exists audit_log (
  id uuid primary key default gen_random_uuid(),
  admin_id uuid references admins(id),
  action text not null,
  table_name text not null,
  record_id uuid,
  old_value jsonb,
  new_value jsonb,
  created_at timestamptz default now()
);

-- Chat is between one student and the admin only
create table if not exists messages (
  id uuid primary key default gen_random_uuid(),
  student_id uuid references students(id) on delete cascade,
  sender text not null check (sender in ('student','admin')),
  body text not null,
  read_at timestamptz,
  created_at timestamptz default now()
);

create table if not exists timetable_entries (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  details text,
  starts_at timestamptz,
  ends_at timestamptz,
  created_at timestamptz default now()
);

create or replace view student_balances as
select s.id as student_id,
       coalesce((select sum(amount) from fee_charges c where c.student_id = s.id), 0) as total_charged,
       coalesce((select sum(amount) from payments p where p.student_id = s.id and p.status = 'success'), 0) as total_paid,
       coalesce((select sum(amount) from fee_charges c where c.student_id = s.id), 0)
       - coalesce((select sum(amount) from payments p where p.student_id = s.id and p.status = 'success'), 0) as balance
from students s;

-- Lock tables from direct browser access; only the backend (service key) reads/writes
alter table admins enable row level security;
alter table settings enable row level security;
alter table students enable row level security;
alter table fee_terms enable row level security;
alter table fee_charges enable row level security;
alter table payments enable row level security;
alter table audit_log enable row level security;
alter table messages enable row level security;
alter table timetable_entries enable row level security;

-- Timetable (added Oct 2026)
create table if not exists timetable_classes (
  id uuid primary key default gen_random_uuid(),
  academic_year text not null,
  semester int not null,
  day_of_week int not null check (day_of_week between 1 and 7),
  start_time time not null,
  end_time time not null,
  unit_code text,
  unit_name text not null,
  lecturer text,
  venue text,
  class_type text not null default 'lecture',
  year_of_study int,
  created_at timestamptz default now(),
  check (end_time > start_time)
);
alter table timetable_classes enable row level security;

alter table timetable_entries add column if not exists kind text default 'event';
alter table timetable_entries add column if not exists event_date date;
alter table timetable_entries add column if not exists end_date date;
alter table timetable_entries add column if not exists year_of_study int;
