# Database Capture Plan

## Stack

- `PostgreSQL`
- `Supabase`
- `Supabase Auth` for login

Important:

- users authenticate through `auth.users`
- app-specific profile data lives in `profiles`
- do not store passwords in your own tables
- the product must work with a very short onboarding flow

## Product Question To Support

The database should be enough to answer:

```text
Para mi cultivo de maiz o frijol, en mi ubicacion y etapa de desarrollo, que riesgo tengo y que debo hacer?
```

## Design Principle

The updated product brief is intentionally lightweight:

- ask only what is needed to personalize risk
- keep personal data optional when anonymous flow is enough
- store user observations separately from fixed parcel data
- derive as much as possible in the backend instead of asking the user

## Canonical Data Groups

The input should be split into 4 groups:

1. `user_profile`
2. `plot`
3. `crop_cycle`
4. `farmer_observation`

This matters because not every field changes at the same speed.

Examples:

- `phone` belongs to `profiles`
- `preferred_channel` belongs to `user_preferences`
- `lat/lon` for the working parcel belong to `plots`
- `crop` and `sowing_date` belong to `crop_cycles`
- `soil_observation` and `crop_condition_reported` belong to `farmer_observations`

## Minimal Mandatory Data For Personalized Recommendation

These are the minimum required fields from the updated product logic:

| Product field | Type | Table | Column |
|---|---|---|---|
| `crop` | enum | `crop_cycles` | `crop_type_id` |
| `sowing_date` | date | `crop_cycles` | `sowing_date` |
| `lat` | number | `plots` | `centroid_lat` |
| `lon` | number | `plots` | `centroid_lon` |

Without these fields, the app can only provide general guidance, not personalized advice.

## Recommended Data

| Product field | Type | Table | Column |
|---|---|---|---|
| `municipality` | string | `farms` or `profiles` | `municipality` |
| `canton` | string | `farms` | `canton` |
| `variety_cycle_days` | integer | `crop_cycles` | `variety_cycle_days` |
| `soil_observation` | enum | `farmer_observations` | `soil_observation` |
| `last_rain_observed_by_farmer` | date/null | `farmer_observations` | `last_rain_observed_by_farmer` |
| `has_irrigation` | boolean | `plots` | `irrigation_available` |

`has_irrigation` is useful for recommendations, but it is no longer part of the minimum mandatory capture set.

## Optional High-Value Data

| Product field | Type | Table | Column |
|---|---|---|---|
| `farmer_name_or_alias` | string | `profiles` | `full_name` or `display_name` |
| `phone` | string | `profiles` | `phone` |
| `preferred_channel` | enum | `user_preferences` | `preferred_channel` |
| `uses_fertilizer` | boolean | `crop_cycles` | `uses_fertilizer` |
| `crop_condition_reported` | enum | `farmer_observations` | `crop_condition_reported` |
| `photo_available` | boolean | `farmer_observations` | `photo_available` |
| `water_source` | enum | `plots` | `water_source` |

## Derived Data The App Should Compute

These values should not be asked directly from the user when they can be computed:

| Derived field | Source |
|---|---|
| `days_after_sowing` | `sowing_date` + current date |
| `estimated_phase` | phenology rules + `days_after_sowing` |
| `planting_season` | `sowing_date` |
| `nearest_rain_station` | plot coordinates + weather stations |
| `nearest_temperature_station` | plot coordinates + weather stations |
| `basin_id` | plot coordinates + hydrologic layers |
| `soil_context` | plot / municipality + soil sources |
| `risk_level` | advisory engine |
| `recommended_actions` | advisory engine |

## Mapping To Tables

### 1. User Profile

Store identity and communication in:

- `profiles`
- `user_preferences`

Suggested fields:

- `profiles.full_name`
- `profiles.display_name`
- `profiles.phone`
- `profiles.whatsapp_phone`
- `profiles.preferred_language`
- `user_preferences.preferred_channel`

All of these can be nullable except what your auth or UX flow requires.

### 2. Plot / Parcel

Store working location and semi-fixed parcel context in:

- `farms`
- `plots`

Main fields:

- `farms.farm_name`
- `farms.department`
- `farms.municipality`
- `farms.canton`
- `plots.plot_name`
- `plots.centroid_lat`
- `plots.centroid_lon`
- `plots.irrigation_available`
- `plots.water_source`
- `plots.area_mz`

If there is no precise coordinate yet, you can temporarily use municipality/canton and mark lower confidence in the application layer.

### 3. Active Crop Cycle

Store stable crop-cycle data in:

- `crop_cycles`

Main fields:

- `crop_cycles.crop_type_id`
- `crop_cycles.sowing_date`
- `crop_cycles.seed_variety`
- `crop_cycles.variety_cycle_days`
- `crop_cycles.planting_season`
- `crop_cycles.production_purpose`
- `crop_cycles.uses_fertilizer`

This table should describe the cycle itself, not ephemeral field observations.

### 4. Farmer Observation

Store user-reported field observations in:

- `farmer_observations`

Main fields:

- `farmer_observations.soil_observation`
- `farmer_observations.last_rain_observed_by_farmer`
- `farmer_observations.crop_condition_reported`
- `farmer_observations.photo_available`
- `farmer_observations.reported_at`

This separation is useful because these values can change often during the cycle.

## Capture Rules

- If there is no coordinate, ask for municipality/canton and mark lower confidence.
- If there is no sowing date, do not estimate phase yet.
- If the farmer reports a condition that conflicts with estimated phase, store both and lower confidence in the advisory layer.
- Do not require personal data if the product can work anonymously.

## Recommended MVP Onboarding

For the shortest possible onboarding, ask only:

1. crop
2. sowing date
3. parcel coordinates

That is enough to power:

- nearest station lookup
- estimated phase
- basic risk logic
- climate-aware advisory generation

## Recommended Better Onboarding

If you want stronger agronomic context, add:

1. municipality
2. canton
3. irrigation available
4. variety cycle days
5. soil observation
6. last rain observed by farmer
7. crop condition reported
8. preferred channel

## Suggested Human Capture Prompts

Short producer version:

1. Que cultivo tiene sembrado: maiz o frijol?
2. Cuando lo sembro?
3. Donde esta la parcela?
4. El suelo se ve seco, humedo o encharcado?

Extensionista version:

1. Municipio y canton del productor?
2. Cultivo y fecha de siembra?
3. Se observan sintomas de marchitez, amarillamiento o aborto floral?

## Main Relationships

- one `profile` can have many `farms`
- one `farm` can have many `plots`
- one `plot` can have many `crop_cycles`
- one `crop_cycle` can have many `farmer_observations`
- one `crop_type` has many `phenological_phases`
- one `crop_cycle` has many `cycle_phase_history` rows
- one `crop_cycle` can have many `advisory_runs`
- one `advisory_run` can have many `advisory_messages`

## Recommended Build Order

Phase 1:

- `profiles`
- `user_preferences`
- `farms`
- `plots`
- `crop_types`
- `crop_cycles`

Phase 2:

- `farmer_observations`
- `phenological_phases`
- `cycle_phase_history`

Phase 3:

- `advisory_runs`
- `advisory_messages`
- `user_crop_interests`

## Notes For Supabase

- use `uuid` primary keys
- use `auth.users.id` as `profiles.id`
- add RLS later so users only see their own farms, plots, cycles, and observations
- use Supabase Storage later if you decide to store field photos
