# SNET / MARN Latest 2026 Endpoints

Verified on 2026-05-15.

This file only includes the best SNET/MARN sources that appear current for 2026, especially for May 2026.

It mixes:

- live raw JSON endpoints
- current HTML forecast pages
- latest 2026 PDF documents

## Best Sources Right Now

If you only connect 3 sources for the hackathon, use these first:

1. `TemperaturaActualMaxMin`
2. `viento_promedio_2horas`
3. `48+horas` page or latest agrometeorological bulletin PDF

## 1. Latest Temperature Observations

Type:

- live raw JSON

Endpoint:

- `https://geoportal.snet.gob.sv/server/rest/services/TemperaturaActualMaxMin/MapServer/0/query`

Why it is good:

- current 2026 observations
- station-level temperatures
- includes observation timestamp

Observed useful fields:

- `estacionid`
- `latitud`
- `longitud`
- `horafecha`
- `actual`
- `maxima`
- `minima`

Verified time sample:

- `horafecha = 1778872200000`
- converts to `2026-05-15T19:10:00Z`

### Query examples

Get latest temperature values for all stations:

```bash
curl "https://geoportal.snet.gob.sv/server/rest/services/TemperaturaActualMaxMin/MapServer/0/query?where=1%3D1&outFields=estacionid,latitud,longitud,horafecha,actual,maxima,minima&returnGeometry=false&f=pjson"
```

Get one station by id:

```bash
curl "https://geoportal.snet.gob.sv/server/rest/services/TemperaturaActualMaxMin/MapServer/0/query?where=estacionid%20%3D%204&outFields=estacionid,horafecha,actual,maxima,minima&returnGeometry=false&f=pjson"
```

Count records:

```bash
curl "https://geoportal.snet.gob.sv/server/rest/services/TemperaturaActualMaxMin/MapServer/0/query?where=1%3D1&returnCountOnly=true&f=pjson"
```

## 2. Latest Wind Observations

Type:

- live raw JSON

Endpoint:

- `https://geoportal.snet.gob.sv/server/rest/services/viento_promedio_2horas/FeatureServer/0/query`

Why it is good:

- current 2026 observations
- average wind from the last 2 hours

Observed useful fields:

- `estacionid`
- `latitud`
- `longitud`
- `dir_promedio`
- `vel_promedio`

### Query examples

Get latest wind values for all stations:

```bash
curl "https://geoportal.snet.gob.sv/server/rest/services/viento_promedio_2horas/FeatureServer/0/query?where=1%3D1&outFields=estacionid,latitud,longitud,dir_promedio,vel_promedio&returnGeometry=false&f=pjson"
```

Get one station by id:

```bash
curl "https://geoportal.snet.gob.sv/server/rest/services/viento_promedio_2horas/FeatureServer/0/query?where=estacionid%20%3D%204&outFields=estacionid,latitud,longitud,dir_promedio,vel_promedio&returnGeometry=false&f=pjson"
```

Count records:

```bash
curl "https://geoportal.snet.gob.sv/server/rest/services/viento_promedio_2horas/FeatureServer/0/query?where=1%3D1&returnCountOnly=true&f=pjson"
```

## 3. Latest 48-Hour Forecast

Type:

- current HTML page

Page:

- `https://www.snet.gob.sv/ver/meteorologia/pronostico/48+horas/`

Why it is good:

- clearly current for May 15 to May 16, 2026
- contains forecast narrative
- contains temperature tables by city
- contains next update notice

Observed current content on verification date:

- `Viernes, 15 de Mayo de 2026`
- `Sabado, 16 de Mayo de 2026`
- `Próxima actualización: Sabado, 16 de Mayo de 2026, 5:00 am`

### Query examples

Fetch the full page:

```bash
curl "https://www.snet.gob.sv/ver/meteorologia/pronostico/48+horas/"
```

Save the page locally:

```bash
curl "https://www.snet.gob.sv/ver/meteorologia/pronostico/48+horas/" -o pronostico_48h.html
```

## 4. Latest Meteorological Bulletin PDF

Type:

- PDF document

Page:

- `https://www.snet.gob.sv/ver/meteorologia/pronostico/boletin+meteorologico/`

Direct PDF:

- `https://srt.snet.gob.sv/videopronostico/BoletinMeteorologico/Boletin.pdf`

Why it is useful:

- stable direct file URL
- good for narrative and document extraction

Important caveat:

- when verified on `2026-05-15`, the PDF `Last-Modified` header was `Sun, 03 May 2026 13:30:39 GMT`
- this means it may not be the freshest May 15 source
- prefer the `48+horas` page if you need the most current day-by-day weather text

### Query examples

Fetch the PDF:

```bash
curl "https://srt.snet.gob.sv/videopronostico/BoletinMeteorologico/Boletin.pdf" -o BoletinMeteorologico.pdf
```

Check file metadata:

```bash
curl -I "https://srt.snet.gob.sv/videopronostico/BoletinMeteorologico/Boletin.pdf"
```

## 5. Latest Weekly Forecast PDF

Type:

- PDF document

Page:

- `https://www.snet.gob.sv/ver/meteorologia/clima/pronostico+semanal/`

Direct PDF found in page:

- `https://www.snet.gob.sv/UserFiles/meteorologia/pronosticoestacional/pronostico_estacional_11mayo26.pdf`

Why it is useful:

- clearly a May 2026 weekly forecast artifact
- better for short-term weekly context than the 2022 static climate layer

Verified metadata:

- `Last-Modified: Tue, 12 May 2026 13:53:41 GMT`

### Query examples

Fetch the weekly forecast PDF:

```bash
curl "https://www.snet.gob.sv/UserFiles/meteorologia/pronosticoestacional/pronostico_estacional_11mayo26.pdf" -o pronostico_estacional_11mayo26.pdf
```

Check file metadata:

```bash
curl -I "https://www.snet.gob.sv/UserFiles/meteorologia/pronosticoestacional/pronostico_estacional_11mayo26.pdf"
```

## 6. Latest Agrometeorological Bulletin PDF

Type:

- PDF document

Viewer page:

- `https://srt.snet.gob.sv/apps/public/viewboletinagro`

Latest PDF found in viewer:

- `https://srt.snet.gob.sv/apps/public/boletin_agrometeorologico/Boletin_13.pdf`

Older visible PDFs:

- `Boletin_12.pdf` = `21 al 30 abril de 2026`
- `Boletin_11.pdf` = `11 al 20 abril de 2026`
- `Boletin_10.pdf` = `1 al 10 abril de 2026`

Why it is useful:

- best agro-focused latest source
- directly relevant to crop guidance

Verified metadata:

- `Last-Modified: Tue, 12 May 2026 19:33:51 GMT`

### Query examples

Open viewer:

```bash
curl "https://srt.snet.gob.sv/apps/public/viewboletinagro"
```

Fetch latest agro bulletin PDF:

```bash
curl "https://srt.snet.gob.sv/apps/public/boletin_agrometeorologico/Boletin_13.pdf" -o Boletin_13.pdf
```

Check PDF metadata:

```bash
curl -I "https://srt.snet.gob.sv/apps/public/boletin_agrometeorologico/Boletin_13.pdf"
```

## 7. Latest Current Conditions Snapshot

Type:

- HTML page

Endpoint:

- `https://www.snet.gob.sv/meteorologia/metar/index3.php`

Why it is useful:

- latest displayed weather snapshot
- city-level conditions
- updates frequently

Why it is weaker:

- HTML only
- not a clean structured API

### Query examples

Fetch current conditions page:

```bash
curl "https://www.snet.gob.sv/meteorologia/metar/index3.php"
```

Save it locally:

```bash
curl "https://www.snet.gob.sv/meteorologia/metar/index3.php" -o condiciones_actuales.html
```

## Not Recommended for Latest 2026

### Static climate outlook layers

Example:

- `https://geoportal.snet.gob.sv/server/rest/services/clima/perspectivas_clima_servicio/MapServer/12?f=pjson`

Reason:

- description references `MARN 2022`
- this is a static scenario map service, not a rolling 2026 monthly API

### Timed-out rainfall temperature service

Example:

- `https://geoportal.snet.gob.sv/server/rest/services/lluvia_temperatura/FeatureServer`

Reason:

- public directory entry exists
- repeated live queries timed out during verification

### Token-protected folders

Examples:

- `https://geoportal.snet.gob.sv/server/rest/services/RISK?f=pjson`
- `https://geoportal.snet.gob.sv/server/rest/services/DGOA?f=pjson`

Reason:

- returned `499 Token Required`

## Recommended Usage for Your Hackathon

### For live app cards

Use:

- temperature endpoint
- wind endpoint

### For latest official weather guidance

Use:

- 48-hour forecast page
- weekly forecast PDF

### For agro recommendations

Use:

- latest agro bulletin PDF

### For fallback display

Use:

- `metar/index3.php`
