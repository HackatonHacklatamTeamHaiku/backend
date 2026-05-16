# Database Capture Plan

## Stack

- `PostgreSQL`
- `Supabase`
- `Supabase Auth` for login

Important:

- users authenticate through `auth.users`
- app-specific profile data lives in `profiles`
- do not store passwords in your own tables

## What To Ask The User

### 1. Account / Identity

Ask:

- full name
- phone
- WhatsApp number
- preferred language

Store in:

- `profiles`
- `user_preferences`

### 2. Base Location

Ask:

- country
- department
- municipality
- optional exact coordinates

Store in:

- `profiles.default_lat`
- `profiles.default_lon`
- `profiles.department`
- `profiles.municipality`

### 3. Farm Information

Ask:

- farm name
- department
- municipality
- canton / caserío if available
- approximate farm area
- optional coordinates

Store in:

- `farms`

### 4. Plot / Parcel Information

Ask:

- plot name
- plot size
- irrigation available or not
- water source
- soil type
- optional coordinates

Store in:

- `plots`

### 5. Crops Managed

You already know the main crops are:

- `maize`
- `bean`

Ask:

- which crops the user manages
- which one is primary

Store in:

- `user_crop_interests`

### 6. Active Crop Cycle

Ask:

- crop type
- sowing date
- variety
- planting method
- expected harvest date if known

Store in:

- `crop_cycles`

### 7. Plant Phase

You have two options:

1. ask the user directly for current phase
2. estimate phase from `sowing_date` with your advisory engine

Best practical approach:

- ask for `sowing_date`
- optionally ask current visible phase
- keep official/current estimated phase in `crop_cycles.current_phase_id`
- store changes over time in `cycle_phase_history`

## What The System Should Store Automatically

Without asking the user again, the backend can later store:

- detected or estimated phenological phase
- advisory history
- risk level history
- message delivery history
- station used for advisory context

Store in:

- `cycle_phase_history`
- `advisory_runs`
- `advisory_messages`

## Recommended Minimal MVP Onboarding

If you want the shortest onboarding possible, ask only:

1. full name
2. WhatsApp or phone
3. municipality
4. crop type
5. sowing date
6. approximate plot location

That is enough to power:

- nearest station lookup
- estimated phase
- risk logic
- advisory messages

## Recommended Better Onboarding

If you want stronger agronomic context, ask:

1. full name
2. phone / WhatsApp
3. municipality
4. farm name
5. plot name
6. plot size
7. irrigation available
8. crop type
9. variety
10. sowing date

This gives you a much better base for future recommendations.

## Main Relationships

- one `profile` can have many `farms`
- one `farm` can have many `plots`
- one `plot` can have many `crop_cycles`
- one `crop_type` has many `phenological_phases`
- one `crop_cycle` has many `cycle_phase_history` rows
- one `crop_cycle` can have many `advisory_runs`
- one `advisory_run` can have many `advisory_messages`

## Recommended First Tables To Actually Build

If you want to implement in phases, do:

Phase 1:

- `profiles`
- `user_preferences`
- `farms`
- `plots`
- `crop_types`
- `crop_cycles`

Phase 2:

- `phenological_phases`
- `cycle_phase_history`

Phase 3:

- `advisory_runs`
- `advisory_messages`
- `user_crop_interests`

## Notes For Supabase

- use `uuid` primary keys
- use `auth.users.id` as `profiles.id`
- add RLS later so users only see their own farms, plots, and cycles
- consider using Supabase Storage later for uploaded plot files or images
