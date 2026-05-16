-- =============================================================
-- SATO-Agro — Full database migration for Supabase (PostgreSQL)
-- Generated from: docs/database/database-schema.dbml
-- =============================================================
--
-- Run this file once against your Supabase project to create
-- all application tables.  Supabase Auth handles auth.users;
-- profiles.id references auth.users.id.
--
-- IMPORTANT: Run in the Supabase SQL Editor or via psql.
-- =============================================================

-- ── Extensions ──────────────────────────────────────────────

-- uuid-ossp is already enabled on Supabase, but just in case:
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ── Enum types ──────────────────────────────────────────────

DO $$ BEGIN
    CREATE TYPE user_role AS ENUM ('producer', 'technician', 'admin');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE crop_code AS ENUM ('maize', 'bean');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE cycle_status AS ENUM ('planned', 'active', 'harvested', 'failed', 'archived');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE phase_source AS ENUM ('manual', 'rule_engine', 'advisor');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE risk_level AS ENUM ('low', 'medium', 'high', 'critical');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE advisory_status AS ENUM ('draft', 'sent', 'read', 'dismissed', 'expired');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE preferred_channel AS ENUM ('whatsapp', 'sms', 'extensionista', 'app');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE production_purpose AS ENUM ('autoconsumo', 'venta', 'mixto');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE planting_season AS ENUM ('primera', 'postrera', 'apante', 'relevo_milpa');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE soil_observation AS ENUM ('seco', 'humedo', 'encharcado', 'desconocido');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE water_source_type AS ENUM ('pozo', 'rio', 'reservorio', 'ninguna', 'desconocida');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE crop_condition_reported AS ENUM ('normal', 'marchitez', 'amarillamiento', 'floracion', 'vainas', 'desconocido');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;


-- ── Tables ──────────────────────────────────────────────────

-- 1. profiles  (references Supabase auth.users.id)
CREATE TABLE IF NOT EXISTS profiles (
    id              UUID PRIMARY KEY,  -- matches auth.users.id
    full_name       VARCHAR(150),
    display_name    VARCHAR(80),
    phone           VARCHAR(30),
    whatsapp_phone  VARCHAR(30),
    role            user_role NOT NULL DEFAULT 'producer',
    preferred_language VARCHAR(10) NOT NULL DEFAULT 'es',
    country         VARCHAR(80) NOT NULL DEFAULT 'El Salvador',
    department      VARCHAR(120),
    municipality    VARCHAR(120),
    default_lat     DECIMAL(9,6),
    default_lon     DECIMAL(9,6),
    onboarding_completed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_profiles_phone ON profiles (phone);
CREATE INDEX IF NOT EXISTS idx_profiles_whatsapp ON profiles (whatsapp_phone);
CREATE INDEX IF NOT EXISTS idx_profiles_location ON profiles (department, municipality);


-- 2. user_preferences
CREATE TABLE IF NOT EXISTS user_preferences (
    profile_id            UUID PRIMARY KEY REFERENCES profiles(id) ON DELETE CASCADE,
    preferred_channel     preferred_channel NOT NULL DEFAULT 'app',
    alert_whatsapp_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    alert_sms_enabled     BOOLEAN NOT NULL DEFAULT FALSE,
    alert_push_enabled    BOOLEAN NOT NULL DEFAULT FALSE,
    alert_email_enabled   BOOLEAN NOT NULL DEFAULT FALSE,
    daily_summary_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    severe_only           BOOLEAN NOT NULL DEFAULT FALSE,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- 3. farms
CREATE TABLE IF NOT EXISTS farms (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_profile_id  UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    farm_name         VARCHAR(150) NOT NULL,
    country           VARCHAR(80) NOT NULL DEFAULT 'El Salvador',
    department        VARCHAR(120),
    municipality      VARCHAR(120),
    canton            VARCHAR(120),
    caserio           VARCHAR(120),
    address_text      TEXT,
    centroid_lat      DECIMAL(9,6),
    centroid_lon      DECIMAL(9,6),
    total_area_ha     DECIMAL(10,2),
    notes             TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_farms_owner ON farms (owner_profile_id);
CREATE INDEX IF NOT EXISTS idx_farms_location ON farms (department, municipality);


-- 4. plots
CREATE TABLE IF NOT EXISTS plots (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    farm_id              UUID NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
    plot_name            VARCHAR(150) NOT NULL,
    plot_code            VARCHAR(50),
    area_ha              DECIMAL(10,2),
    area_mz              DECIMAL(10,2),  -- manzanas, locally common
    centroid_lat         DECIMAL(9,6),
    centroid_lon         DECIMAL(9,6),
    elevation_m          INTEGER,
    irrigation_available BOOLEAN NOT NULL DEFAULT FALSE,
    water_source         water_source_type,
    soil_type            VARCHAR(120),
    slope_class          VARCHAR(50),
    notes                TEXT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_plots_farm ON plots (farm_id);
CREATE INDEX IF NOT EXISTS idx_plots_code ON plots (plot_code);


-- 5. crop_types  (reference / seed data)
CREATE TABLE IF NOT EXISTS crop_types (
    id              SMALLINT PRIMARY KEY,
    code            crop_code NOT NULL UNIQUE,
    name_es         VARCHAR(80) NOT NULL,
    scientific_name VARCHAR(120),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- 6. phenological_phases
CREATE TABLE IF NOT EXISTS phenological_phases (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    crop_type_id          SMALLINT NOT NULL REFERENCES crop_types(id),
    phase_code            VARCHAR(50) NOT NULL,
    phase_name_es         VARCHAR(120) NOT NULL,
    phase_order           INTEGER NOT NULL,
    start_day_after_sowing INTEGER NOT NULL,
    end_day_after_sowing  INTEGER NOT NULL,
    is_critical           BOOLEAN NOT NULL DEFAULT FALSE,
    description           TEXT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (crop_type_id, phase_code),
    UNIQUE (crop_type_id, phase_order)
);


-- 7. crop_cycles
CREATE TABLE IF NOT EXISTS crop_cycles (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plot_id               UUID NOT NULL REFERENCES plots(id) ON DELETE CASCADE,
    owner_profile_id      UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    crop_type_id          SMALLINT NOT NULL REFERENCES crop_types(id),
    season_label          VARCHAR(80),
    production_purpose    production_purpose,
    planting_season       planting_season,
    sowing_date           DATE NOT NULL,
    expected_harvest_date DATE,
    actual_harvest_date   DATE,
    seed_variety          VARCHAR(120),
    variety_cycle_days    INTEGER,
    seed_source           VARCHAR(120),
    planting_method       VARCHAR(80),
    uses_fertilizer       BOOLEAN,
    current_phase_id      UUID REFERENCES phenological_phases(id),
    current_phase_day     INTEGER,
    status                cycle_status NOT NULL DEFAULT 'active',
    area_ha               DECIMAL(10,2),
    notes                 TEXT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_cycles_plot ON crop_cycles (plot_id);
CREATE INDEX IF NOT EXISTS idx_cycles_owner ON crop_cycles (owner_profile_id);
CREATE INDEX IF NOT EXISTS idx_cycles_crop ON crop_cycles (crop_type_id);
CREATE INDEX IF NOT EXISTS idx_cycles_sowing ON crop_cycles (sowing_date);
CREATE INDEX IF NOT EXISTS idx_cycles_status ON crop_cycles (status);


-- 8. farmer_observations
CREATE TABLE IF NOT EXISTS farmer_observations (
    id                              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    crop_cycle_id                   UUID NOT NULL REFERENCES crop_cycles(id) ON DELETE CASCADE,
    profile_id                      UUID REFERENCES profiles(id),
    soil_observation                soil_observation NOT NULL DEFAULT 'desconocido',
    last_rain_observed_by_farmer    DATE,
    crop_condition_reported         crop_condition_reported NOT NULL DEFAULT 'desconocido',
    photo_available                 BOOLEAN NOT NULL DEFAULT FALSE,
    reported_at                     TIMESTAMPTZ NOT NULL DEFAULT now(),
    notes                           TEXT,
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_observations_cycle ON farmer_observations (crop_cycle_id);
CREATE INDEX IF NOT EXISTS idx_observations_profile ON farmer_observations (profile_id);
CREATE INDEX IF NOT EXISTS idx_observations_reported ON farmer_observations (reported_at);


-- 9. cycle_phase_history
CREATE TABLE IF NOT EXISTS cycle_phase_history (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    crop_cycle_id     UUID NOT NULL REFERENCES crop_cycles(id) ON DELETE CASCADE,
    phase_id          UUID NOT NULL REFERENCES phenological_phases(id),
    source            phase_source NOT NULL DEFAULT 'rule_engine',
    started_on        DATE NOT NULL,
    ended_on          DATE,
    confidence_score  DECIMAL(5,2),
    notes             TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_phase_history_cycle ON cycle_phase_history (crop_cycle_id);
CREATE INDEX IF NOT EXISTS idx_phase_history_composite ON cycle_phase_history (crop_cycle_id, phase_id, started_on);


-- 10. advisory_runs
CREATE TABLE IF NOT EXISTS advisory_runs (
    id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    crop_cycle_id          UUID NOT NULL REFERENCES crop_cycles(id) ON DELETE CASCADE,
    profile_id             UUID NOT NULL REFERENCES profiles(id),
    nearest_station_id     INTEGER,
    station_name           VARCHAR(150),
    risk_level             risk_level NOT NULL,
    trigger_type           VARCHAR(80) NOT NULL,
    reasoning_summary      TEXT NOT NULL,
    recommended_action     TEXT NOT NULL,
    action_window_days     INTEGER,
    based_on_observed_at   TIMESTAMPTZ,
    based_on_document_ids  TEXT,  -- comma-separated or migrate to join table later
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_advisory_runs_cycle ON advisory_runs (crop_cycle_id);
CREATE INDEX IF NOT EXISTS idx_advisory_runs_profile ON advisory_runs (profile_id);
CREATE INDEX IF NOT EXISTS idx_advisory_runs_risk ON advisory_runs (risk_level);
CREATE INDEX IF NOT EXISTS idx_advisory_runs_created ON advisory_runs (created_at);


-- 11. advisory_messages
CREATE TABLE IF NOT EXISTS advisory_messages (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    advisory_run_id  UUID NOT NULL REFERENCES advisory_runs(id) ON DELETE CASCADE,
    profile_id       UUID NOT NULL REFERENCES profiles(id),
    status           advisory_status NOT NULL DEFAULT 'draft',
    title            VARCHAR(160) NOT NULL,
    message_body     TEXT NOT NULL,
    channel          VARCHAR(30) NOT NULL DEFAULT 'in_app',
    sent_at          TIMESTAMPTZ,
    read_at          TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_messages_run ON advisory_messages (advisory_run_id);
CREATE INDEX IF NOT EXISTS idx_messages_profile ON advisory_messages (profile_id);
CREATE INDEX IF NOT EXISTS idx_messages_status ON advisory_messages (status);


-- 12. user_crop_interests
CREATE TABLE IF NOT EXISTS user_crop_interests (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id    UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    crop_type_id  SMALLINT NOT NULL REFERENCES crop_types(id),
    is_primary    BOOLEAN NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (profile_id, crop_type_id)
);


-- ── Seed data ───────────────────────────────────────────────

INSERT INTO crop_types (id, code, name_es, scientific_name)
VALUES
    (1, 'maize', 'Maíz', 'Zea mays'),
    (2, 'bean',  'Frijol', 'Phaseolus vulgaris')
ON CONFLICT (id) DO NOTHING;


-- ── Seed phenological phases (maize) ────────────────────────

INSERT INTO phenological_phases (crop_type_id, phase_code, phase_name_es, phase_order, start_day_after_sowing, end_day_after_sowing, is_critical, description)
VALUES
    (1, 'germination',     'Germinación',            1,   0,   7, FALSE, 'Emergencia de la semilla'),
    (1, 'seedling',        'Plántula',               2,   8,  20, FALSE, 'Crecimiento inicial de hojas'),
    (1, 'vegetative',      'Crecimiento vegetativo', 3,  21,  50, FALSE, 'Desarrollo de hojas y tallo'),
    (1, 'tasseling',       'Espigamiento',           4,  51,  60, TRUE,  'Emergencia de la espiga; alta sensibilidad a estrés hídrico'),
    (1, 'silking',         'Jiloteo',                5,  61,  70, TRUE,  'Emisión de estigmas; polinización; periodo más crítico'),
    (1, 'grain_filling',   'Llenado de grano',       6,  71,  95, TRUE,  'Acumulación de almidón en el grano'),
    (1, 'maturation',      'Maduración',             7,  96, 120, FALSE, 'Secado fisiológico y cosecha')
ON CONFLICT (crop_type_id, phase_code) DO NOTHING;


-- ── Seed phenological phases (bean) ─────────────────────────

INSERT INTO phenological_phases (crop_type_id, phase_code, phase_name_es, phase_order, start_day_after_sowing, end_day_after_sowing, is_critical, description)
VALUES
    (2, 'germination',     'Germinación',            1,   0,   7, FALSE, 'Emergencia y desarrollo radicular'),
    (2, 'seedling',        'Plántula',               2,   8,  15, FALSE, 'Primeras hojas verdaderas'),
    (2, 'vegetative',      'Crecimiento vegetativo', 3,  16,  35, FALSE, 'Desarrollo de ramas y follaje'),
    (2, 'flowering',       'Floración',              4,  36,  45, TRUE,  'Floración; alta sensibilidad a estrés hídrico y térmico'),
    (2, 'pod_formation',   'Formación de vainas',    5,  46,  55, TRUE,  'Desarrollo de vainas'),
    (2, 'grain_filling',   'Llenado de grano',       6,  56,  70, TRUE,  'Acumulación de reservas en el grano'),
    (2, 'maturation',      'Maduración',             7,  71,  90, FALSE, 'Secado y cosecha')
ON CONFLICT (crop_type_id, phase_code) DO NOTHING;


-- ── updated_at trigger helper ───────────────────────────────

CREATE OR REPLACE FUNCTION trigger_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


-- Apply auto-updated_at triggers to tables with updated_at
DO $$ BEGIN
    CREATE TRIGGER set_updated_at BEFORE UPDATE ON profiles
        FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TRIGGER set_updated_at BEFORE UPDATE ON user_preferences
        FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TRIGGER set_updated_at BEFORE UPDATE ON farms
        FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TRIGGER set_updated_at BEFORE UPDATE ON plots
        FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TRIGGER set_updated_at BEFORE UPDATE ON crop_cycles
        FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;


-- ── Row Level Security (RLS) — enable but don't lock down yet ──

ALTER TABLE profiles           ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_preferences   ENABLE ROW LEVEL SECURITY;
ALTER TABLE farms              ENABLE ROW LEVEL SECURITY;
ALTER TABLE plots              ENABLE ROW LEVEL SECURITY;
ALTER TABLE crop_cycles        ENABLE ROW LEVEL SECURITY;
ALTER TABLE farmer_observations ENABLE ROW LEVEL SECURITY;
ALTER TABLE cycle_phase_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE advisory_runs      ENABLE ROW LEVEL SECURITY;
ALTER TABLE advisory_messages  ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_crop_interests ENABLE ROW LEVEL SECURITY;

-- Permissive policies for the backend service role (bypasses RLS)
-- Individual user-scoped policies should be added as the frontend matures.


-- ── Done ────────────────────────────────────────────────────
-- Run verification:
--   SELECT table_name FROM information_schema.tables
--   WHERE table_schema = 'public' ORDER BY table_name;
