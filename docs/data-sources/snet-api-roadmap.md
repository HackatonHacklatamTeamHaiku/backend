# SNET / MARN Data Roadmap for SATO-Agro

Verified on 2026-05-15.

## Goal

Use public SNET/MARN data surfaces that are good enough for a hackathon MVP focused on:

- drought and canicula early warning
- municipality or producer-level risk scoring
- prescriptive guidance for maize and bean growers

This document separates:

- stable, queryable endpoints
- scrape-only legacy pages
- restricted or unreliable services

## Executive Summary

Best public machine-readable sources found:

1. `viento_promedio_2horas`
2. `TemperaturaActualMaxMin`
3. `clima/perspectivas_clima_servicio`
4. `ExposicionASequia`
5. `clima/servicio_suelos_pais`
6. agrometeorological bulletin PDFs

Useful but weaker legacy sources:

1. `metar/index3.php` weather page
2. rainfall graph images from `grafico_lluvia_ac.php`

Not recommended for MVP as primary dependencies:

1. `lluvia_temperatura` ArcGIS service, because it timed out repeatedly during verification
2. token-protected folders like `RISK` and `DGOA`

## Source Inventory

### 1. Current weather wrapper page

Page:

- `https://www.snet.gob.sv/ver/meteorologia/monitoreo/condiciones+del+tiempo/`

Real content:

- `https://www.snet.gob.sv/meteorologia/metar/index3.php`

What it provides:

- city-level temperature
- humidity
- dew point
- pressure
- wind speed
- local timestamp

Format:

- server-rendered HTML

Notes:

- useful as a fallback snapshot
- not ideal as your main API because it is presentation HTML, not a structured feed

### 2. Agro bulletin viewer

Page:

- `https://www.snet.gob.sv/ver/meteorologia/clima/agrometeorologico/`

Embedded app:

- `https://srt.snet.gob.sv/apps/public/viewboletinagro`

Verified direct PDF links:

- `https://srt.snet.gob.sv/apps/public/boletin_agrometeorologico/Boletin_13.pdf`
- `https://srt.snet.gob.sv/apps/public/boletin_agrometeorologico/Boletin_12.pdf`
- `https://srt.snet.gob.sv/apps/public/boletin_agrometeorologico/Boletin_11.pdf`

What it provides:

- high-value expert interpretation
- narrative outlooks
- crop-relevant agrometeorological context

Format:

- HTML page that embeds a PDF and lists previous PDFs

Why it matters:

- this is the easiest way to inject institution-grade guidance into your recommendations layer

### 3. Legacy rainfall accumulated page

Page:

- `https://www.snet.gob.sv/ver/meteorologia/monitoreo/lluvia+acumulada/`

Observed image endpoint pattern:

- `http://www.snet.gob.sv/cpm/grafico_lluvia_ac.php?estacionid=C3`

What it provides:

- rainfall accumulation graphs by station

Format:

- PNG image generated per station

Notes:

- useful for visualization
- not good as a primary numeric source unless you are willing to do image extraction

### 4. Public ArcGIS REST root

Directory:

- `https://geoportal.snet.gob.sv/server/rest/services`

This is the most important discovery. It exposes actual queryable services.

## Best Public APIs for the MVP

### A. Wind observations

Service:

- `https://geoportal.snet.gob.sv/server/rest/services/viento_promedio_2horas/FeatureServer`

Verified query example:

- `https://geoportal.snet.gob.sv/server/rest/services/viento_promedio_2horas/FeatureServer/0/query?where=1%3D1&outFields=*&returnGeometry=false&f=pjson`

Verified facts:

- public
- returns JSON
- count query returned `49`

Fields observed:

- `estacionid`
- `latitud`
- `longitud`
- `dir_promedio`
- `vel_promedio`

Use in SATO-Agro:

- station-level meteorological nowcast context
- detecting dry windy conditions that can worsen crop stress

### B. Temperature observations

Service:

- `https://geoportal.snet.gob.sv/server/rest/services/TemperaturaActualMaxMin/MapServer`

Verified query example:

- `https://geoportal.snet.gob.sv/server/rest/services/TemperaturaActualMaxMin/MapServer/0/query?where=1%3D1&outFields=*&returnGeometry=false&f=pjson`

Fields observed:

- `estacionid`
- `latitud`
- `longitud`
- `horafecha`
- `actual`
- `maxima`
- `minima`

Use in SATO-Agro:

- heat stress signal
- combine with rainfall deficit and dry spell logic
- estimate evapotranspiration pressure proxy for simple rules

### C. Climate outlook scenarios

Service:

- `https://geoportal.snet.gob.sv/server/rest/services/clima/perspectivas_clima_servicio/MapServer`

Useful layer metadata:

- layer `12`: `Escenario esperado en agosto`
- layer `13`: `Escenario esperado en septiembre`
- layer `14`: `Escenario esperado en octubre`
- layer `15`: `Escenario esperado en noviembre`

Verified layer metadata example:

- `https://geoportal.snet.gob.sv/server/rest/services/clima/perspectivas_clima_servicio/MapServer/12?f=pjson`

Verified query example:

- `https://geoportal.snet.gob.sv/server/rest/services/clima/perspectivas_clima_servicio/MapServer/12/query?where=1%3D1&outFields=gridcode,Escenario&returnGeometry=false&f=pjson`

Observed scenario classes:

- `Bajo lo normal`
- `Normal`
- `Arriba lo normal`

Use in SATO-Agro:

- monthly prior for drought or rain expectations
- municipality-level scenario overlay
- helps produce forward-looking alerts instead of pure nowcasting

### D. Drought exposure layers

Service:

- `https://geoportal.snet.gob.sv/server/rest/services/ExposicionASequia/MapServer`

Verified service metadata:

- includes municipal boundaries
- producer points
- non-perennial crop raster
- livestock municipalities
- exposed population raster

High-value producer layer:

- layer `2`: `Productores`

Verified query example:

- `https://geoportal.snet.gob.sv/server/rest/services/ExposicionASequia/MapServer/2/query?where=1%3D1&outFields=*&returnGeometry=false&f=pjson`

Important fields observed:

- `municipio`
- `canton`
- `CIIU`
- `CATEGORIA`
- `DESCRIPCION`
- `RIEGO`
- `VULNERABILIDAD`
- `Vulne_final`

Examples observed:

- maize grain production
- orange production
- coffee production

Use in SATO-Agro:

- prebuilt vulnerability prior
- target extensionists and prioritize outreach
- map crop type and irrigation vulnerability

### E. Soil properties

Service:

- `https://geoportal.snet.gob.sv/server/rest/services/clima/servicio_suelos_pais/MapServer`

Available layers:

- `Materia Ogánica`
- `pH`
- `Textura`

Available tables:

- `textura_summ`
- `ph_summ`
- `Sum_Output`

Verified table query example:

- `https://geoportal.snet.gob.sv/server/rest/services/clima/servicio_suelos_pais/MapServer/5/query?where=1%3D1&outFields=*&returnGeometry=false&f=pjson`

Useful fields observed:

- `First_COD_MUN4`
- `First_mo_txt_descrip`
- `Sum_porc_`

Use in SATO-Agro:

- add simple water retention proxy
- stronger recommendations by municipality
- explain why two places with similar rainfall may have different crop risk

## Public but Weak or Brittle Sources

### F. METAR weather HTML

Endpoint:

- `https://www.snet.gob.sv/meteorologia/metar/index3.php`

Why weak:

- HTML only
- city blocks are hardcoded and not normalized
- some stations were blank during verification

Best use:

- fallback dashboard widget
- not a core backend feed

### G. Rainfall graph PNGs

Pattern:

- `http://www.snet.gob.sv/cpm/grafico_lluvia_ac.php?estacionid=<station>`

Why weak:

- image output, not raw values
- requires OCR or visual extraction if you need numeric data

Best use:

- analyst dashboard
- visual proof for judges

## Restricted or Unreliable Sources

### H. Token-protected GIS folders

Observed:

- `https://geoportal.snet.gob.sv/server/rest/services/RISK?f=pjson`
- `https://geoportal.snet.gob.sv/server/rest/services/DGOA?f=pjson`

Result:

- public request returned `499 Token Required`

Implication:

- do not plan your MVP around these unless you get credentials

### I. `lluvia_temperatura`

Listed at:

- `https://geoportal.snet.gob.sv/server/rest/services`

Observed:

- service exists in the directory
- repeated attempts to query it timed out on 2026-05-15

Implication:

- treat it as optional
- do not depend on it for the demo path

## Recommended MVP Architecture

### Layer 1. Ingestion

Use these as first-class sources:

1. `TemperaturaActualMaxMin`
2. `viento_promedio_2horas`
3. `clima/perspectivas_clima_servicio`
4. `ExposicionASequia`
5. `clima/servicio_suelos_pais`
6. agrometeorological bulletin PDFs

Optional fallback:

1. `metar/index3.php`
2. rainfall graph PNGs

### Layer 2. Normalized tables

Create these internal tables:

1. `weather_station_observations`
2. `municipality_climate_outlook`
3. `producer_vulnerability`
4. `municipality_soil_profile`
5. `bulletin_insights`

Suggested minimum schema:

```sql
create table weather_station_observations (
  source text,
  observed_at timestamptz,
  station_id text,
  lat double precision,
  lon double precision,
  temp_actual_c double precision,
  temp_max_c double precision,
  temp_min_c double precision,
  wind_dir_deg double precision,
  wind_speed double precision,
  raw jsonb
);
```

```sql
create table municipality_climate_outlook (
  month_name text,
  scenario_code integer,
  scenario_label text,
  geom jsonb,
  raw jsonb
);
```

```sql
create table producer_vulnerability (
  producer_id text,
  municipality text,
  canton text,
  crop_activity text,
  crop_category text,
  irrigation text,
  vulnerability_label text,
  vulnerability_score integer,
  raw jsonb
);
```

### Layer 3. Risk engine

For the hackathon, keep the rules simple and explainable.

Suggested scoring:

1. start with vulnerability prior from `ExposicionASequia`
2. add heat stress if `actual` or `maxima` exceeds threshold
3. add dryness prior if climate outlook is `Bajo lo normal`
4. reduce risk where irrigation exists
5. modify recommendations using soil organic matter or texture summaries

Example rule set:

```text
if crop_category == "CULTIVO NO PERENNE" and
   outlook in ("Bajo lo normal") and
   temp_max_c >= 35 and
   irrigation == "NO"
then risk = "ALTO"
```

```text
if vulnerability_score is high and
   current heat is elevated
then action window = "3-5 dias"
```

### Layer 4. Recommendation engine

Map the risk to crop-stage advice.

For maize:

- avoid fertilization during acute dry stress
- prioritize watering if available
- delay planting if pre-planting and outlook is below normal

For beans:

- protect flowering and pod fill periods
- avoid top-dressing under severe moisture deficit

### Layer 5. Delivery

Outputs for demo day:

1. municipality dashboard
2. prioritized producer list
3. WhatsApp-style alert text
4. simple map with climate outlook plus vulnerable producers

## What To Build First

### Phase 1. Fastest demo path

Build only with:

1. `TemperaturaActualMaxMin`
2. `viento_promedio_2horas`
3. `ExposicionASequia`
4. agro bulletin PDFs

Why:

- all verified public
- enough to show live data plus domain context

### Phase 2. Better forecasting

Add:

1. `clima/perspectivas_clima_servicio`
2. `clima/servicio_suelos_pais`

Why:

- improves forward-looking and localized guidance

### Phase 3. Nice-to-have polish

Add:

1. legacy `metar/index3.php`
2. rainfall graph image cards

Why:

- good visuals for judges
- not necessary for backend logic

## Query Examples

### Temperature

```bash
curl "https://geoportal.snet.gob.sv/server/rest/services/TemperaturaActualMaxMin/MapServer/0/query?where=1%3D1&outFields=*&returnGeometry=false&f=pjson"
```

### Wind

```bash
curl "https://geoportal.snet.gob.sv/server/rest/services/viento_promedio_2horas/FeatureServer/0/query?where=1%3D1&outFields=*&returnGeometry=false&f=pjson"
```

### Outlook scenario metadata

```bash
curl "https://geoportal.snet.gob.sv/server/rest/services/clima/perspectivas_clima_servicio/MapServer/12?f=pjson"
```

### Outlook scenario features

```bash
curl "https://geoportal.snet.gob.sv/server/rest/services/clima/perspectivas_clima_servicio/MapServer/12/query?where=1%3D1&outFields=gridcode,Escenario&returnGeometry=false&f=pjson"
```

### Vulnerable producers

```bash
curl "https://geoportal.snet.gob.sv/server/rest/services/ExposicionASequia/MapServer/2/query?where=1%3D1&outFields=*&returnGeometry=false&f=pjson"
```

### Soil summary table

```bash
curl "https://geoportal.snet.gob.sv/server/rest/services/clima/servicio_suelos_pais/MapServer/5/query?where=1%3D1&outFields=*&returnGeometry=false&f=pjson"
```

## Practical Warnings

1. These are public web services, not formal product APIs with SLA guarantees.
2. Cache all responses you use for the demo.
3. Store raw payloads so you can replay your demo if a service slows down.
4. Prefer ArcGIS JSON services over scraping HTML or images.
5. Do not build the main logic around OCR of rainfall charts.

## Recommended Implementation Order for Your Hackathon

1. Build a small ingestion job for temperature and wind.
2. Join producer vulnerability by municipality and crop category.
3. Add outlook scenario overlays for August to November.
4. Parse the latest agro bulletin PDF manually first, then automate later.
5. Generate prescriptive alerts using simple explainable rules.
6. Cache the latest successful payloads locally for resilience.

## Best Pitch Framing

Say that SATO-Agro combines:

- live public observations from MARN/SNET
- official climate outlook layers
- official drought exposure and producer vulnerability data
- agrometeorological expert guidance

That framing is stronger than saying you only scraped a website.

## Sources

- [Condiciones del tiempo](https://www.snet.gob.sv/ver/meteorologia/monitoreo/condiciones+del+tiempo/)
- [METAR iframe](https://www.snet.gob.sv/meteorologia/metar/index3.php)
- [Lluvia acumulada](https://www.snet.gob.sv/ver/meteorologia/monitoreo/lluvia+acumulada/)
- [Agrometeorológico](https://www.snet.gob.sv/ver/meteorologia/clima/agrometeorologico/)
- [Boletín viewer](https://srt.snet.gob.sv/apps/public/viewboletinagro)
- [ArcGIS REST root](https://geoportal.snet.gob.sv/server/rest/services)
- [Wind service](https://geoportal.snet.gob.sv/server/rest/services/viento_promedio_2horas/FeatureServer)
- [Temperature service](https://geoportal.snet.gob.sv/server/rest/services/TemperaturaActualMaxMin/MapServer)
- [Climate outlook service](https://geoportal.snet.gob.sv/server/rest/services/clima/perspectivas_clima_servicio/MapServer)
- [Drought exposure service](https://geoportal.snet.gob.sv/server/rest/services/ExposicionASequia/MapServer)
- [Soils service](https://geoportal.snet.gob.sv/server/rest/services/clima/servicio_suelos_pais/MapServer)
