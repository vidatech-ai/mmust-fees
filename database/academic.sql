-- Academic section (added Oct 2026)
create table if not exists academic_units (
  id uuid primary key default gen_random_uuid(),
  academic_year text not null,
  semester int not null,
  year_of_study int not null check (year_of_study between 1 and 8),
  unit_code text,
  unit_name text not null,
  credit_hours numeric(5,1),
  created_at timestamptz default now()
);
alter table academic_units enable row level security;

create table if not exists transcript_records (
  id uuid primary key default gen_random_uuid(),
  student_id uuid references students(id) on delete cascade,
  academic_year text not null,
  semester int not null,
  year_of_study int not null check (year_of_study between 1 and 8),
  unit_code text,
  unit_name text not null,
  marks numeric(5,2),
  grade text,
  created_at timestamptz default now()
);
alter table transcript_records enable row level security;
create index if not exists transcript_student_idx on transcript_records (student_id);
