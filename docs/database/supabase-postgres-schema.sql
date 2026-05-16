-- SATO-Agro
-- PostgreSQL / Supabase schema
-- Generated from the current DBML design.
--
-- Notes:
-- 1. Authentication is handled by Supabase Auth.
-- 2. public.profiles.id references auth.users.id.
-- 3. Passwords must never be stored in application tables.
-- 4. Minimum mandatory product data for personalized recommendation:
--    crop, sowing_date, lat, lon.
-- 5. Farmer observations are stored separately from fixed crop-cycle data.

begin;

create extension if not exists pgcrypto;

-- Enums
do $$
begin
  if not exists (select 1 from pg_type where typname = 'user_role') then
    create type public.user_role as enum ('producer', 'technician', 'admin');
  end if;

  if not exists (select 1 from pg_type where typname = 'crop_code') then
    create type public.crop_code as enum ('maize', 'bean');
  end if;

  if not exists (select 1 from pg_type where typname = 'cycle_status') then
    create type public.cycle_status as enum ('planned', 'active', 'harvested', 'failed', 'archived');
  end if;

  if not exists (select 1 from pg_type where typname = 'phase_source') then
    create type public.phase_source as enum ('manual', 'rule_engine', 'advisor');
  end if;

  if not exists (select 1 from pg_type where typname = 'risk_level') then
    create type public.risk_level as enum ('low', 'medium', 'high', 'critical');
  end if;

  if not exists (select 1 from pg_type where typname = 'advisory_status') then
    create type public.advisory_status as enum ('draft', 'sent', 'read', 'dismissed', 'expired');
  end if;

  if not exists (select 1 from pg_type where typname = 'preferred_channel') then
    create type public.preferred_channel as enum ('whatsapp', 'sms', 'extensionista', 'app');
  end if;

  if not exists (select 1 from pg_type where typname = 'production_purpose') then
    create type public.production_purpose as enum ('autoconsumo', 'venta', 'mixto');
  end if;

  if not exists (select 1 from pg_type where typname = 'planting_season') then
    create type public.planting_season as enum ('primera', 'postrera', 'apante', 'relevo_milpa');
  end if;

  if not exists (select 1 from pg_type where typname = 'soil_observation') then
    create type public.soil_observation as enum ('seco', 'humedo', 'encharcado', 'desconocido');
  end if;

  if not exists (select 1 from pg_type where typname = 'water_source_type') then
    create type public.water_source_type as enum ('pozo', 'rio', 'reservorio', 'ninguna', 'desconocida');
  end if;

  if not exists (select 1 from pg_type where typname = 'crop_condition_reported') then
    create type public.crop_condition_reported as enum ('normal', 'marchitez', 'amarillamiento', 'floracion', 'vainas', 'desconocido');
  end if;
end
$$;

-- Shared updated_at trigger
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- Tables
create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  full_name varchar(150),
  display_name varchar(80),
  phone varchar(30),
  whatsapp_phone varchar(30),
  role public.user_role not null default 'producer',
  preferred_language varchar(10) not null default 'es',
  country varchar(80) not null default 'El Salvador',
  department varchar(120),
  municipality varchar(120),
  default_lat numeric(9,6),
  default_lon numeric(9,6),
  onboarding_completed boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.user_preferences (
  profile_id uuid primary key references public.profiles(id) on delete cascade,
  preferred_channel public.preferred_channel not null default 'app',
  alert_whatsapp_enabled boolean not null default true,
  alert_sms_enabled boolean not null default false,
  alert_push_enabled boolean not null default false,
  alert_email_enabled boolean not null default false,
  daily_summary_enabled boolean not null default true,
  severe_only boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.farms (
  id uuid primary key default gen_random_uuid(),
  owner_profile_id uuid not null references public.profiles(id) on delete cascade,
  farm_name varchar(150) not null,
  country varchar(80) not null default 'El Salvador',
  department varchar(120),
  municipality varchar(120),
  canton varchar(120),
  caserio varchar(120),
  address_text text,
  centroid_lat numeric(9,6),
  centroid_lon numeric(9,6),
  total_area_ha numeric(10,2),
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.plots (
  id uuid primary key default gen_random_uuid(),
  farm_id uuid not null references public.farms(id) on delete cascade,
  plot_name varchar(150) not null,
  plot_code varchar(50),
  area_ha numeric(10,2),
  area_mz numeric(10,2),
  centroid_lat numeric(9,6),
  centroid_lon numeric(9,6),
  elevation_m integer,
  irrigation_available boolean not null default false,
  water_source public.water_source_type,
  soil_type varchar(120),
  slope_class varchar(50),
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.crop_types (
  id smallint primary key,
  code public.crop_code not null unique,
  name_es varchar(80) not null,
  scientific_name varchar(120),
  created_at timestamptz not null default now()
);

create table if not exists public.phenological_phases (
  id uuid primary key default gen_random_uuid(),
  crop_type_id smallint not null references public.crop_types(id) on delete cascade,
  phase_code varchar(50) not null,
  phase_name_es varchar(120) not null,
  phase_order integer not null,
  start_day_after_sowing integer not null,
  end_day_after_sowing integer not null,
  is_critical boolean not null default false,
  description text,
  created_at timestamptz not null default now(),
  constraint phenological_phases_crop_type_phase_code_key unique (crop_type_id, phase_code),
  constraint phenological_phases_crop_type_phase_order_key unique (crop_type_id, phase_order)
);

create table if not exists public.crop_cycles (
  id uuid primary key default gen_random_uuid(),
  plot_id uuid not null references public.plots(id) on delete cascade,
  owner_profile_id uuid not null references public.profiles(id) on delete cascade,
  crop_type_id smallint not null references public.crop_types(id),
  season_label varchar(80),
  production_purpose public.production_purpose,
  planting_season public.planting_season,
  sowing_date date not null,
  expected_harvest_date date,
  actual_harvest_date date,
  seed_variety varchar(120),
  variety_cycle_days integer,
  seed_source varchar(120),
  planting_method varchar(80),
  uses_fertilizer boolean,
  current_phase_id uuid,
  current_phase_day integer,
  status public.cycle_status not null default 'active',
  area_ha numeric(10,2),
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint crop_cycles_current_phase_id_fkey
    foreign key (current_phase_id) references public.phenological_phases(id)
    on delete set null
);

create table if not exists public.farmer_observations (
  id uuid primary key default gen_random_uuid(),
  crop_cycle_id uuid not null references public.crop_cycles(id) on delete cascade,
  profile_id uuid references public.profiles(id) on delete set null,
  soil_observation public.soil_observation not null default 'desconocido',
  last_rain_observed_by_farmer date,
  crop_condition_reported public.crop_condition_reported not null default 'desconocido',
  photo_available boolean not null default false,
  reported_at timestamptz not null default now(),
  notes text,
  created_at timestamptz not null default now()
);

create table if not exists public.cycle_phase_history (
  id uuid primary key default gen_random_uuid(),
  crop_cycle_id uuid not null references public.crop_cycles(id) on delete cascade,
  phase_id uuid not null references public.phenological_phases(id) on delete cascade,
  source public.phase_source not null default 'rule_engine',
  started_on date not null,
  ended_on date,
  confidence_score numeric(5,2),
  notes text,
  created_at timestamptz not null default now()
);

create table if not exists public.advisory_runs (
  id uuid primary key default gen_random_uuid(),
  crop_cycle_id uuid not null references public.crop_cycles(id) on delete cascade,
  profile_id uuid not null references public.profiles(id) on delete cascade,
  nearest_station_id integer,
  station_name varchar(150),
  risk_level public.risk_level not null,
  trigger_type varchar(80) not null,
  reasoning_summary text not null,
  recommended_action text not null,
  action_window_days integer,
  based_on_observed_at timestamptz,
  based_on_document_ids text,
  created_at timestamptz not null default now()
);

create table if not exists public.advisory_messages (
  id uuid primary key default gen_random_uuid(),
  advisory_run_id uuid not null references public.advisory_runs(id) on delete cascade,
  profile_id uuid not null references public.profiles(id) on delete cascade,
  status public.advisory_status not null default 'draft',
  title varchar(160) not null,
  message_body text not null,
  channel varchar(30) not null default 'in_app',
  sent_at timestamptz,
  read_at timestamptz,
  created_at timestamptz not null default now()
);

create table if not exists public.user_crop_interests (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid not null references public.profiles(id) on delete cascade,
  crop_type_id smallint not null references public.crop_types(id) on delete cascade,
  is_primary boolean not null default false,
  created_at timestamptz not null default now(),
  constraint user_crop_interests_profile_crop_key unique (profile_id, crop_type_id)
);

-- Indexes
create index if not exists profiles_phone_idx on public.profiles (phone);
create index if not exists profiles_whatsapp_phone_idx on public.profiles (whatsapp_phone);
create index if not exists profiles_department_municipality_idx on public.profiles (department, municipality);

create index if not exists farms_owner_profile_id_idx on public.farms (owner_profile_id);
create index if not exists farms_department_municipality_idx on public.farms (department, municipality);

create index if not exists plots_farm_id_idx on public.plots (farm_id);
create index if not exists plots_plot_code_idx on public.plots (plot_code);

create index if not exists crop_cycles_plot_id_idx on public.crop_cycles (plot_id);
create index if not exists crop_cycles_owner_profile_id_idx on public.crop_cycles (owner_profile_id);
create index if not exists crop_cycles_crop_type_id_idx on public.crop_cycles (crop_type_id);
create index if not exists crop_cycles_sowing_date_idx on public.crop_cycles (sowing_date);
create index if not exists crop_cycles_status_idx on public.crop_cycles (status);

create index if not exists farmer_observations_crop_cycle_id_idx on public.farmer_observations (crop_cycle_id);
create index if not exists farmer_observations_profile_id_idx on public.farmer_observations (profile_id);
create index if not exists farmer_observations_reported_at_idx on public.farmer_observations (reported_at);

create index if not exists cycle_phase_history_crop_cycle_id_idx on public.cycle_phase_history (crop_cycle_id);
create index if not exists cycle_phase_history_compound_idx on public.cycle_phase_history (crop_cycle_id, phase_id, started_on);

create index if not exists advisory_runs_crop_cycle_id_idx on public.advisory_runs (crop_cycle_id);
create index if not exists advisory_runs_profile_id_idx on public.advisory_runs (profile_id);
create index if not exists advisory_runs_risk_level_idx on public.advisory_runs (risk_level);
create index if not exists advisory_runs_created_at_idx on public.advisory_runs (created_at);

create index if not exists advisory_messages_advisory_run_id_idx on public.advisory_messages (advisory_run_id);
create index if not exists advisory_messages_profile_id_idx on public.advisory_messages (profile_id);
create index if not exists advisory_messages_status_idx on public.advisory_messages (status);

-- updated_at triggers
drop trigger if exists set_profiles_updated_at on public.profiles;
create trigger set_profiles_updated_at
before update on public.profiles
for each row execute function public.set_updated_at();

drop trigger if exists set_user_preferences_updated_at on public.user_preferences;
create trigger set_user_preferences_updated_at
before update on public.user_preferences
for each row execute function public.set_updated_at();

drop trigger if exists set_farms_updated_at on public.farms;
create trigger set_farms_updated_at
before update on public.farms
for each row execute function public.set_updated_at();

drop trigger if exists set_plots_updated_at on public.plots;
create trigger set_plots_updated_at
before update on public.plots
for each row execute function public.set_updated_at();

drop trigger if exists set_crop_cycles_updated_at on public.crop_cycles;
create trigger set_crop_cycles_updated_at
before update on public.crop_cycles
for each row execute function public.set_updated_at();

-- Seed data
insert into public.crop_types (id, code, name_es, scientific_name)
values
  (1, 'maize', 'Maíz', 'Zea mays'),
  (2, 'bean', 'Frijol', 'Phaseolus vulgaris')
on conflict (id) do update
set
  code = excluded.code,
  name_es = excluded.name_es,
  scientific_name = excluded.scientific_name;

commit;
