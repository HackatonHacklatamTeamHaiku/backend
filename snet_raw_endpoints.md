# SNET / MARN Raw-Value Endpoints

Verified on 2026-05-15.

This file only includes endpoints that return machine-readable values directly, mainly JSON from ArcGIS REST services.

## Base Notes

Most queryable services use ArcGIS REST.

### Parameters you almost always need

- `f=pjson` returns JSON
- `where=1%3D1` means "all records"
- `outFields=*` returns all fields
- `returnGeometry=false` skips geometry and makes responses smaller
- `returnCountOnly=true` returns only the record count

### How to think about querying

There are 4 common query styles in these services:

1. all records
2. by id
3. by text filter like municipality or crop
4. by point location

### Point location queries

When a layer supports spatial lookup, the usual parameters are:

- `geometry=<lon>,<lat>`
- `geometryType=esriGeometryPoint`
- `inSR=4326`
- `spatialRel=esriSpatialRelIntersects`
- `outFields=...`
- `f=pjson`

Example:

```bash
curl "https://geoportal.snet.gob.sv/server/rest/services/clima/perspectivas_clima_servicio/MapServer/12/query?geometry=-89.2182,13.6929&geometryType=esriGeometryPoint&inSR=4326&spatialRel=esriSpatialRelIntersects&outFields=gridcode,Escenario&returnGeometry=false&f=pjson"
```

### Important caveat

Not every service needs a location parameter.

- wind and temperature are easiest to query as full station lists or by `estacionid`
- climate outlook supports point-in-polygon lookup well
- producer vulnerability is easier to query by `municipio`, `canton`, or crop text than by point geometry
- soil summary tables are easiest to query by municipality code

## 1. Wind Observations

Service:

- `https://geoportal.snet.gob.sv/server/rest/services/viento_promedio_2horas/FeatureServer`

Layer:

- `0`

What it returns:

- station id
- latitude
- longitude
- average wind direction
- average wind speed

Observed fields:

- `estacionid`
- `latitud`
- `longitud`
- `dir_promedio`
- `vel_promedio`

### What you need to query

Required minimum:

- `where`
- `outFields`
- `f=pjson`

Optional:

- `returnGeometry=false`

Does it need location?

- No

Best filters:

- `estacionid`

Best practice for location-based use:

- fetch all stations once
- use `latitud` and `longitud` in your app to find the nearest station to the user

### Query examples

Count records:

```bash
curl "https://geoportal.snet.gob.sv/server/rest/services/viento_promedio_2horas/FeatureServer/0/query?where=1%3D1&returnCountOnly=true&f=pjson"
```

Get all raw values without geometry:

```bash
curl "https://geoportal.snet.gob.sv/server/rest/services/viento_promedio_2horas/FeatureServer/0/query?where=1%3D1&outFields=*&returnGeometry=false&f=pjson"
```

Get only the main weather fields:

```bash
curl "https://geoportal.snet.gob.sv/server/rest/services/viento_promedio_2horas/FeatureServer/0/query?where=1%3D1&outFields=estacionid,latitud,longitud,dir_promedio,vel_promedio&returnGeometry=false&f=pjson"
```

Get one station by id:

```bash
curl "https://geoportal.snet.gob.sv/server/rest/services/viento_promedio_2horas/FeatureServer/0/query?where=estacionid%20%3D%204&outFields=estacionid,latitud,longitud,dir_promedio,vel_promedio&returnGeometry=false&f=pjson"
```

## 2. Temperature Observations

Service:

- `https://geoportal.snet.gob.sv/server/rest/services/TemperaturaActualMaxMin/MapServer`

Layer:

- `0`

What it returns:

- station id
- latitude
- longitude
- observation timestamp
- current temperature
- max temperature
- min temperature

Observed fields:

- `estacionid`
- `latitud`
- `longitud`
- `horafecha`
- `actual`
- `maxima`
- `minima`

### What you need to query

Required minimum:

- `where`
- `outFields`
- `f=pjson`

Optional:

- `returnGeometry=false`

Does it need location?

- No

Best filters:

- `estacionid`

Best practice for location-based use:

- fetch all stations
- pick nearest using `latitud` and `longitud`

### Query examples

Get all raw values without geometry:

```bash
curl "https://geoportal.snet.gob.sv/server/rest/services/TemperaturaActualMaxMin/MapServer/0/query?where=1%3D1&outFields=*&returnGeometry=false&f=pjson"
```

Get only the core temperature fields:

```bash
curl "https://geoportal.snet.gob.sv/server/rest/services/TemperaturaActualMaxMin/MapServer/0/query?where=1%3D1&outFields=estacionid,latitud,longitud,horafecha,actual,maxima,minima&returnGeometry=false&f=pjson"
```

Count records:

```bash
curl "https://geoportal.snet.gob.sv/server/rest/services/TemperaturaActualMaxMin/MapServer/0/query?where=1%3D1&returnCountOnly=true&f=pjson"
```

Get one station by id:

```bash
curl "https://geoportal.snet.gob.sv/server/rest/services/TemperaturaActualMaxMin/MapServer/0/query?where=estacionid%20%3D%204&outFields=estacionid,horafecha,actual,maxima,minima&returnGeometry=false&f=pjson"
```

## 3. Climate Outlook Scenarios

Service:

- `https://geoportal.snet.gob.sv/server/rest/services/clima/perspectivas_clima_servicio/MapServer`

Useful layers:

- `12` = `Escenario esperado en agosto`
- `13` = `Escenario esperado en septiembre`
- `14` = `Escenario esperado en octubre`
- `15` = `Escenario esperado en noviembre`

What it returns:

- scenario code
- scenario label
- polygon geometry if requested

Observed fields:

- `gridcode`
- `Escenario`

Observed labels:

- `Bajo lo normal`
- `Normal`
- `Arriba lo normal`

### What you need to query

If you want a whole month layer:

- `where`
- `outFields`
- `f=pjson`

If you want the scenario for one location:

- month layer id like `12`, `13`, `14`, or `15`
- `geometry=<lon>,<lat>`
- `geometryType=esriGeometryPoint`
- `inSR=4326`
- `spatialRel=esriSpatialRelIntersects`
- `outFields=gridcode,Escenario`
- `f=pjson`

Does it need location?

- Only if you want a result for one point

Best filters:

- month layer id
- point geometry

### Query examples

Get layer metadata:

```bash
curl "https://geoportal.snet.gob.sv/server/rest/services/clima/perspectivas_clima_servicio/MapServer/12?f=pjson"
```

Get raw scenario values for August:

```bash
curl "https://geoportal.snet.gob.sv/server/rest/services/clima/perspectivas_clima_servicio/MapServer/12/query?where=1%3D1&outFields=gridcode,Escenario&returnGeometry=false&f=pjson"
```

Get raw scenario values for September:

```bash
curl "https://geoportal.snet.gob.sv/server/rest/services/clima/perspectivas_clima_servicio/MapServer/13/query?where=1%3D1&outFields=gridcode,Escenario&returnGeometry=false&f=pjson"
```

Get features with geometry in GeoJSON-compatible JSON mode:

```bash
curl "https://geoportal.snet.gob.sv/server/rest/services/clima/perspectivas_clima_servicio/MapServer/12/query?where=1%3D1&outFields=gridcode,Escenario&returnGeometry=true&f=pjson"
```

Get the August scenario for a specific location:

```bash
curl "https://geoportal.snet.gob.sv/server/rest/services/clima/perspectivas_clima_servicio/MapServer/12/query?geometry=-89.2182,13.6929&geometryType=esriGeometryPoint&inSR=4326&spatialRel=esriSpatialRelIntersects&outFields=gridcode,Escenario&returnGeometry=false&f=pjson"
```

## 4. Drought Exposure and Producer Vulnerability

Service:

- `https://geoportal.snet.gob.sv/server/rest/services/ExposicionASequia/MapServer`

Most useful layers:

- `0` = municipal boundaries
- `1` = departmental boundaries
- `2` = producers
- `4` = livestock municipalities

Best MVP layer:

- `2` = `Productores`

What it returns:

- producer identifiers
- municipality and canton
- crop activity
- irrigation flag
- vulnerability classes

Important observed fields from layer `2`:

- `id_productor`
- `municipio`
- `canton`
- `CIIU`
- `CATEGORIA`
- `DESCRIPCION`
- `RIEGO`
- `VULNERABILIDAD`
- `Vulne_final`

### What you need to query

Required minimum:

- layer id, usually `2`
- `where`
- `outFields`
- `f=pjson`

Optional:

- `returnGeometry=false`

Does it need location?

- No

Best filters:

- `municipio LIKE '%...%'`
- `canton LIKE '%...%'`
- `CIIU LIKE '%MAIZ%'`
- `CIIU LIKE '%FRIJOL%'`
- `RIEGO = 'NO'`

Recommended for MVP:

- query by municipality text or crop text

Not recommended for MVP:

- point geometry lookup on this layer, because the service projection and source geometry make text filters easier and more reliable for quick development

### Query examples

Get producers with raw attributes:

```bash
curl "https://geoportal.snet.gob.sv/server/rest/services/ExposicionASequia/MapServer/2/query?where=1%3D1&outFields=*&returnGeometry=false&f=pjson"
```

Get only the most useful producer risk fields:

```bash
curl "https://geoportal.snet.gob.sv/server/rest/services/ExposicionASequia/MapServer/2/query?where=1%3D1&outFields=id_productor,municipio,canton,CIIU,CATEGORIA,DESCRIPCION,RIEGO,VULNERABILIDAD,Vulne_final&returnGeometry=false&f=pjson"
```

Get only maize-related producer records:

```bash
curl "https://geoportal.snet.gob.sv/server/rest/services/ExposicionASequia/MapServer/2/query?where=CIIU%20LIKE%20'%25MAIZ%25'&outFields=id_productor,municipio,canton,CIIU,CATEGORIA,RIEGO,VULNERABILIDAD,Vulne_final&returnGeometry=false&f=pjson"
```

Get only bean-related producer records:

```bash
curl "https://geoportal.snet.gob.sv/server/rest/services/ExposicionASequia/MapServer/2/query?where=CIIU%20LIKE%20'%25FRIJOL%25'&outFields=id_productor,municipio,canton,CIIU,CATEGORIA,RIEGO,VULNERABILIDAD,Vulne_final&returnGeometry=false&f=pjson"
```

Get all producers in Ahuachapan:

```bash
curl "https://geoportal.snet.gob.sv/server/rest/services/ExposicionASequia/MapServer/2/query?where=municipio%20LIKE%20'%25AHUACHAPAN%25'&outFields=id_productor,municipio,canton,CIIU,RIEGO,VULNERABILIDAD,Vulne_final&returnGeometry=false&f=pjson"
```

Get all non-irrigated maize producers in Ahuachapan:

```bash
curl "https://geoportal.snet.gob.sv/server/rest/services/ExposicionASequia/MapServer/2/query?where=municipio%20LIKE%20'%25AHUACHAPAN%25'%20AND%20CIIU%20LIKE%20'%25MAIZ%25'%20AND%20RIEGO%20%3D%20'NO'&outFields=id_productor,municipio,canton,CIIU,RIEGO,VULNERABILIDAD,Vulne_final&returnGeometry=false&f=pjson"
```

Get municipal polygons:

```bash
curl "https://geoportal.snet.gob.sv/server/rest/services/ExposicionASequia/MapServer/0/query?where=1%3D1&outFields=*&returnGeometry=true&f=pjson"
```

## 5. Soil Properties

Service:

- `https://geoportal.snet.gob.sv/server/rest/services/clima/servicio_suelos_pais/MapServer`

Layers:

- `0` = `Materia Ogánica`
- `1` = `pH`
- `2` = `Textura`

Tables:

- `3` = `textura_summ`
- `4` = `ph_summ`
- `5` = `Sum_Output`

Most useful fast-start table:

- `5`

Observed fields from table `5`:

- `First_COD_MUN4`
- `First_mo_txt_descrip`
- `Sum_porc_`

### What you need to query

Required minimum:

- table id like `5`
- `where`
- `outFields`
- `f=pjson`

Does it need location?

- No direct lat/lon parameter is needed for the summary tables

Best filters:

- municipality code fields like `First_COD_MUN4`

Recommended for MVP:

- map municipality name to municipality code once
- query the summary table by code

### Query examples

Get soil summary table:

```bash
curl "https://geoportal.snet.gob.sv/server/rest/services/clima/servicio_suelos_pais/MapServer/5/query?where=1%3D1&outFields=*&returnGeometry=false&f=pjson"
```

Get municipality organic matter summary fields only:

```bash
curl "https://geoportal.snet.gob.sv/server/rest/services/clima/servicio_suelos_pais/MapServer/5/query?where=1%3D1&outFields=First_COD_MUN4,First_mo_txt_descrip,Sum_porc_&returnGeometry=false&f=pjson"
```

Get organic matter summary for municipality code `0101`:

```bash
curl "https://geoportal.snet.gob.sv/server/rest/services/clima/servicio_suelos_pais/MapServer/5/query?where=First_COD_MUN4%20%3D%20%270101%27&outFields=First_COD_MUN4,First_mo_txt_descrip,Sum_porc_&returnGeometry=false&f=pjson"
```

Get texture summary table:

```bash
curl "https://geoportal.snet.gob.sv/server/rest/services/clima/servicio_suelos_pais/MapServer/3/query?where=1%3D1&outFields=*&returnGeometry=false&f=pjson"
```

Get pH summary table:

```bash
curl "https://geoportal.snet.gob.sv/server/rest/services/clima/servicio_suelos_pais/MapServer/4/query?where=1%3D1&outFields=*&returnGeometry=false&f=pjson"
```

## 6. Legacy HTML Weather Snapshot

Endpoint:

- `https://www.snet.gob.sv/meteorologia/metar/index3.php`

Format:

- HTML, not JSON

Why it is listed:

- it does return raw values in the page markup
- useful only as a fallback scraper, not as your main ingestion endpoint

What you need to query:

- no parameters required

Does it need location?

- No

### Query example

```bash
curl "https://www.snet.gob.sv/meteorologia/metar/index3.php"
```

## Not Included As Recommended Raw Endpoints

### `lluvia_temperatura`

Listed service:

- `https://geoportal.snet.gob.sv/server/rest/services/lluvia_temperatura/FeatureServer`

Reason not recommended:

- it exists publicly in the service directory
- repeated verification attempts timed out

### Token-protected folders

Examples:

- `https://geoportal.snet.gob.sv/server/rest/services/RISK?f=pjson`
- `https://geoportal.snet.gob.sv/server/rest/services/DGOA?f=pjson`

Reason not recommended:

- returned `499 Token Required`

## Fastest Endpoints To Use First

If you only wire 4 sources tonight, use these:

1. temperature
2. wind
3. climate outlook scenarios
4. producer vulnerability

That gives you:

- current meteorological stress
- near-term climate context
- targeting by municipality or producer
- explainable alert generation
