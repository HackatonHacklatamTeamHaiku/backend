-- MVP persistence for user crop registrations and notification schedule.

ALTER TABLE user_preferences
    ADD COLUMN IF NOT EXISTS notification_time TIME NOT NULL DEFAULT '08:00',
    ADD COLUMN IF NOT EXISTS notification_timezone TEXT NOT NULL DEFAULT 'America/El_Salvador';

CREATE TABLE IF NOT EXISTS user_crops (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    crop_type_id SMALLINT NOT NULL REFERENCES crop_types(id),
    sowing_date DATE NOT NULL,
    lat DECIMAL(9,6) NOT NULL,
    lon DECIMAL(9,6) NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT user_crops_status_check
        CHECK (status IN ('active', 'archived'))
);

CREATE INDEX IF NOT EXISTS idx_user_crops_profile
    ON user_crops(profile_id);

CREATE INDEX IF NOT EXISTS idx_user_crops_status
    ON user_crops(status);

CREATE INDEX IF NOT EXISTS idx_user_crops_due_lookup
    ON user_crops(profile_id, status, sowing_date);

ALTER TABLE user_crops ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    CREATE TRIGGER set_updated_at BEFORE UPDATE ON user_crops
        FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
