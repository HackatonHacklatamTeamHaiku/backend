-- Canonical crop persistence for the simplified product model.
-- user_crops becomes the runtime source of truth; legacy crop_cycles data is
-- backfilled without deleting farms, plots, or crop_cycles.

ALTER TABLE user_crops
    ADD COLUMN IF NOT EXISTS display_name VARCHAR(80);

WITH source_crops AS (
    SELECT
        cc.id,
        cc.owner_profile_id AS profile_id,
        cc.crop_type_id,
        cc.sowing_date,
        COALESCE(pl.centroid_lat, f.centroid_lat, p.default_lat)::DECIMAL(9,6) AS lat,
        COALESCE(pl.centroid_lon, f.centroid_lon, p.default_lon)::DECIMAL(9,6) AS lon,
        NULLIF(BTRIM(cc.season_label), '') AS display_name,
        CASE WHEN cc.status = 'active' THEN 'active' ELSE 'archived' END AS source_status,
        cc.created_at,
        cc.updated_at
    FROM crop_cycles cc
    LEFT JOIN plots pl ON pl.id = cc.plot_id
    LEFT JOIN farms f ON f.id = pl.farm_id
    LEFT JOIN profiles p ON p.id = cc.owner_profile_id
), ranked_source AS (
    SELECT
        source_crops.*,
        ROW_NUMBER() OVER (
            PARTITION BY profile_id, crop_type_id, sowing_date, lat, lon
            ORDER BY
                CASE WHEN source_status = 'active' THEN 0 ELSE 1 END,
                updated_at DESC,
                created_at DESC,
                id DESC
        ) AS active_rank
    FROM source_crops
    WHERE lat IS NOT NULL
      AND lon IS NOT NULL
)
INSERT INTO user_crops (
    id,
    profile_id,
    crop_type_id,
    sowing_date,
    lat,
    lon,
    status,
    display_name,
    created_at,
    updated_at
)
SELECT
    id,
    profile_id,
    crop_type_id,
    sowing_date,
    lat,
    lon,
    CASE WHEN source_status = 'active' AND active_rank = 1 THEN 'active' ELSE 'archived' END,
    display_name,
    created_at,
    updated_at
FROM ranked_source
ON CONFLICT (id) DO NOTHING;

WITH ranked_existing AS (
    SELECT
        id,
        ROW_NUMBER() OVER (
            PARTITION BY profile_id, crop_type_id, sowing_date, lat, lon
            ORDER BY updated_at DESC, created_at DESC, id DESC
        ) AS active_rank
    FROM user_crops
    WHERE status = 'active'
)
UPDATE user_crops
SET status = 'archived', updated_at = now()
WHERE id IN (
    SELECT id
    FROM ranked_existing
    WHERE active_rank > 1
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_user_crops_one_active_per_signature
    ON user_crops (profile_id, crop_type_id, sowing_date, lat, lon)
    WHERE status = 'active';
