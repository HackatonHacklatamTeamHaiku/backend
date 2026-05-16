# Guía de Integración Frontend — SATO-Agro API

> Base URL: `http://127.0.0.1:5000`
> Esta guía está alineada con el backend activo y con la superficie pública vigente.

---

## 1. Superficie recomendada

Para UI nueva, usa estas rutas:

- `GET /health`
- `GET /api/weather/observed`
- `GET /api/weather/forecast`
- `GET /api/geo/context`
- `GET /api/risk/assessment`
- `GET /api/llm/context`
- `POST /api/llm/explain`

Rutas de compatibilidad que todavía existen:

- `GET /api/v1/documents/latest`
- `GET /api/v1/ai/tools/manifest`
- `POST /api/v1/ai/tools/call`

No construyas UI nueva sobre rutas `/api/v1/observations/*`, `/api/v1/forecast/*`, `/api/v1/agro/*`, `/api/v1/dashboard/*`, `/api/v1/stations`, `/api/v1/features/current` o `/api/v1/context/location`, porque ya fueron retiradas.

---

## 2. Health Check

```http
GET /health
```

No requiere parámetros.

Respuesta esperada:

```json
{
  "status": "ok",
  "service": "sato-agro-backend",
  "database": "connected",
  "timestamp": "2026-05-16T18:39:28.726913+00:00"
}
```

Uso frontend:

- verificar disponibilidad de backend
- si `database !== "connected"`, mostrar servicio degradado para flujos que dependan de persistencia

---

## 3. Clima observado

```http
GET /api/weather/observed?lat=13.69&lon=-89.21
```

Parámetros:

| Parámetro | Tipo | Requerido |
|---|---|---|
| `lat` | number | sí |
| `lon` | number | sí |

Shape estable:

```json
{
  "data": {
    "source_type": "observado",
    "location": { "lat": 13.69, "lon": -89.21 },
    "nearest_rain_station": {
      "station_id": 267,
      "station_name": "LaBermeja",
      "distance_km": 0.06,
      "confidence": "alta"
    },
    "nearest_temperature_station": {
      "station_id": 61,
      "station_name": "UES",
      "distance_km": 3.27,
      "confidence": "alta"
    },
    "nearest_wind_station": {
      "station_id": 61,
      "station_name": "UES",
      "distance_km": 3.27,
      "confidence": "alta"
    },
    "rain_recent_mm": 0.0,
    "temperature_current_c": 32,
    "temperature_max_c": 32,
    "temperature_min_c": 23,
    "wind_speed_kmh": 0.575,
    "wind_direction_deg": 229.75,
    "is_raining": false,
    "observed_at": "2026-05-16T05:50:00-06:00",
    "rain_observed_at": "11:50",
    "warnings": [],
    "sources_used": [
      "snet_lluvia_data_24h",
      "snet_temperatura_actual_max_min",
      "snet_viento_promedio_2horas"
    ]
  },
  "meta": {
    "cached": true,
    "stale": false,
    "upstream_status": "ok",
    "fetched_at": "2026-05-16T18:39:34.102588+00:00"
  }
}
```

Uso frontend:

- card principal con `temperature_current_c`, `rain_recent_mm`, `is_raining`
- indicador de calidad con `confidence` y `distance_km`
- banner si `warnings.length > 0`
- badge de frescura usando `observed_at`

---

## 4. Pronóstico

```http
GET /api/weather/forecast?lat=13.69&lon=-89.21&target_date=2026-08-15
```

Parámetros:

| Parámetro | Tipo | Requerido |
|---|---|---|
| `lat` | number | sí |
| `lon` | number | sí |
| `target_date` | string `YYYY-MM-DD` | no, pero recomendado |

Horizontes que puede devolver el backend:

- `present`
- `1_3_days`
- `4_7_days`
- `8_16_days`
- `gt_16_days`

Shape estable:

```json
{
  "data": {
    "source_type": "pronosticado",
    "location": { "lat": 13.69, "lon": -89.21 },
    "target_date": "2026-05-16",
    "horizon": "gt_16_days",
    "rain_sum_mm": null,
    "rain_probability_max": null,
    "temp_max_c": null,
    "temp_min_c": null,
    "wind_max_kmh": null,
    "et0_sum_mm": null,
    "soil_moisture_model": "baja",
    "sources_used": ["open_meteo_forecast"],
    "warnings": [
      "Open-Meteo solo cubre 1-16 dias; para esta fecha el backend debe tratar el resultado como escenario."
    ]
  },
  "meta": {
    "cached": true,
    "stale": false,
    "upstream_status": "ok"
  }
}
```

Uso frontend:

- `present`, `1_3_days`, `4_7_days`: mostrar como forecast usable
- `8_16_days`: mostrar con disclaimer de menor precisión
- `gt_16_days`: no presentar como forecast puntual; presentar como escenario
- si vienen `null`, no inventar fallback visual tipo “0”
- `soil_moisture_model` es modelado, no medición directa de parcela

---

## 5. Contexto geográfico

```http
GET /api/geo/context?lat=13.69&lon=-89.21&target_date=2026-08-15
```

Parámetros:

| Parámetro | Tipo | Requerido |
|---|---|---|
| `lat` | number | sí |
| `lon` | number | sí |
| `target_date` | string `YYYY-MM-DD` | no |
| `municipality` | string | no |
| `municipality_code` | string | no |
| `canton` | string | no |

Shape estable:

```json
{
  "data": {
    "location": { "lat": 13.69, "lon": -89.21 },
    "municipality": "San Salvador",
    "municipality_code": "0614",
    "canton": null,
    "basin_id": null,
    "nearest_rain_station": {
      "station_name": "LaBermeja",
      "station_id": 267,
      "distance_km": 0.06,
      "confidence": "alta"
    },
    "nearest_temperature_station": {
      "station_name": "UES",
      "station_id": 61,
      "distance_km": 3.27,
      "confidence": "alta"
    },
    "nearest_wind_station": {
      "station_name": "UES",
      "station_id": 61,
      "distance_km": 3.27,
      "confidence": "alta"
    },
    "soil_context": {
      "municipality_code": "0614",
      "soil_property": "organic_matter",
      "class_label": "alto (3.0 - 4.0)",
      "coverage_percent": 39.97,
      "water_retention_modifier": "favorable",
      "source": "snet_servicio_suelos_pais"
    },
    "climate_outlook_context": {
      "layer_id": 12,
      "month": "agosto",
      "scenario_code": 2,
      "scenario_label": "Normal",
      "dryness_prior": "normal",
      "current_for_alerting": true,
      "temporal_role": "seasonal",
      "source": "snet_perspectivas_clima_servicio",
      "lat": 13.69,
      "lon": -89.21
    },
    "producer_vulnerability_context": null,
    "warnings": [],
    "sources_used": [
      "snet_lluvia_data_24h",
      "snet_temperatura_actual_max_min",
      "snet_viento_promedio_2horas",
      "snet_municipal_boundaries",
      "snet_servicio_suelos_pais",
      "snet_perspectivas_clima_servicio"
    ]
  },
  "meta": {
    "cached": true,
    "stale": false,
    "upstream_status": "ok"
  }
}
```

Uso frontend:

- onboarding de parcela
- badge de `soil_context.water_retention_modifier`
- outlook estacional con `climate_outlook_context.scenario_label`
- alertar si `dryness_prior !== "normal"`

---

## 6. Evaluación de riesgo

```http
GET /api/risk/assessment?crop=maiz&sowing_date=2026-05-20&lat=13.69&lon=-89.21&target_date=2026-08-15
```

Parámetros:

| Parámetro | Tipo | Requerido |
|---|---|---|
| `crop` | string | sí |
| `sowing_date` | string `YYYY-MM-DD` | sí |
| `lat` | number | sí |
| `lon` | number | sí |
| `target_date` | string `YYYY-MM-DD` | no, pero recomendado |

Notas:

- `crop` admite `maiz` y `frijol`
- la respuesta real contiene bastante detalle; la UI debería usar solo las partes visibles que necesite

Shape estable:

```json
{
  "data": {
    "crop": "maiz",
    "horizon": "gt_16_days",
    "risk_score": 0.82,
    "risk_level": "critico",
    "confidence": "baja",
    "recommendations": [
      "Aplicar mulch o cobertura vegetal para reducir evaporacion directa.",
      "Si dispone de riego suplementario, priorizar esta fase critica.",
      "Monitorear signos de estres hidrico (enrollamiento foliar, marchitez)."
    ],
    "assumptions": [
      "rain_sum_mm no estaba disponible; se asumio 0.0 mm.",
      "et0_sum_mm no estaba disponible; se estimo con demanda base de 4.0 mm/dia."
    ],
    "sources_used": [
      "snet_lluvia_data_24h",
      "snet_temperatura_actual_max_min",
      "snet_viento_promedio_2horas",
      "open_meteo_forecast",
      "snet_municipal_boundaries",
      "snet_servicio_suelos_pais",
      "snet_perspectivas_clima_servicio",
      "ambiente_canicula_2026"
    ],
    "plant_state": {
      "crop": "maiz",
      "days_after_sowing": 87,
      "phase": "Llenado de grano",
      "phase_code": "R2_R4",
      "susceptibility": {
        "water": 0.8,
        "heat": 0.8,
        "evaporation": 0.6,
        "soil": 0.6,
        "seasonal": 0.7
      }
    },
    "climate_state": {
      "canicula_watch": true,
      "days_window": 20,
      "dry_days": 20,
      "et0_mm_day": 4.0,
      "et0_sum_mm": 80.0,
      "rain": "sin lluvia",
      "rain_sum_mm": 0.0,
      "seasonal": "vigilancia_canicula",
      "soil": "favorable",
      "temp_max_c": 32.0,
      "temperature": "estable",
      "wind_evaporation": "moderado",
      "wind_max_kmh": 0.58
    },
    "risk_factors": [
      {
        "id": "water_deficit",
        "label": "Deficit hidrico",
        "state": "critico",
        "contribution": 0.4,
        "evidence": "Sin lluvia registrada en la ventana de evaluacion."
      }
    ],
    "risk_overrides": [],
    "secondary_alerts": [],
    "observed_weather": {},
    "forecast_weather": {
      "horizon": "gt_16_days",
      "soil_moisture_model": "baja"
    },
    "geo_context": {
      "municipality": "San Salvador",
      "municipality_code": "0614",
      "soil_context": {
        "water_retention_modifier": "favorable"
      },
      "climate_outlook_context": {
        "scenario_label": "Normal",
        "dryness_prior": "normal",
        "month": "agosto"
      }
    },
    "official_context": {
      "canicula_2026_watch": true,
      "summary": "Existe vigilancia oficial por canicula/periodos secos durante la epoca lluviosa 2026."
    }
  },
  "meta": {
    "cached": true,
    "stale": false,
    "upstream_status": "ok"
  }
}
```

Uso frontend:

- card principal con `risk_level` y `risk_score`
- timeline con `plant_state.phase`
- lista de `risk_factors` por `label`, `state` y `evidence`
- checklist con `recommendations`
- badge con `confidence`
- banner si `climate_state.canicula_watch === true`
- bloque de transparencia si `assumptions.length > 0`

No asumas que existe un campo top-level llamado `phenology`; el backend usa `plant_state`.

---

## 7. Contexto LLM

```http
GET /api/llm/context?crop=maiz&sowing_date=2026-05-20&lat=13.69&lon=-89.21&target_date=2026-08-15
```

Parámetros:

| Parámetro | Tipo | Requerido |
|---|---|---|
| `crop` | string | sí para contexto completo |
| `sowing_date` | string | sí para contexto completo |
| `lat` | number | sí para contexto completo |
| `lon` | number | sí para contexto completo |
| `target_date` | string | no |

Fallback soportado:

```http
GET /api/llm/context?target_date=2026-08-15
```

Eso devuelve solo `official_context`.

Shape estable del contexto completo:

```json
{
  "data": {
    "current_datetime": "2026-05-16T12:40:41-06:00",
    "timezone": "America/El_Salvador",
    "user_inputs": {
      "crop": "maiz",
      "sowing_date": "2026-05-20",
      "lat": 13.69,
      "lon": -89.21
    },
    "ui_state": {
      "selected_target_date": "2026-08-15",
      "selected_horizon": "gt_16_days",
      "visible_panel": "risk_summary"
    },
    "missing_required_user_data": [],
    "plant_state": {
      "phase": "Llenado de grano",
      "days_after_sowing": 87
    },
    "observed_weather": {},
    "forecast_weather": {},
    "risk_assessment": {
      "risk_score": 0.82,
      "risk_level": "critico",
      "confidence": "baja",
      "risk_factors": [],
      "risk_overrides": [],
      "secondary_alerts": []
    },
    "recommendations": [],
    "official_context": {},
    "sources_used": [],
    "source_policy": {
      "observed": "SNET/MARN observado local",
      "forecast": "Open-Meteo 1-16 dias",
      "scenario": ">16 dias o perspectiva mensual/canicula",
      "historical": "solo contexto, no alerta actual"
    }
  },
  "meta": {
    "cached": true,
    "stale": false,
    "upstream_status": "ok"
  }
}
```

Uso frontend:

- este endpoint es para asistentes, no para render directo como dashboard principal
- pasar `data` al agente como `runtime_context`
- no dependas de campos viejos como `phenology` o `geo_context` top-level dentro de `/api/llm/context`

---

## 8. Explicación LLM

```http
POST /api/llm/explain
Content-Type: application/json
```

Body mínimo:

```json
{
  "risk_assessment": {
    "risk_level": "alto",
    "risk_score": 0.82,
    "risk_factors": [
      {
        "label": "Deficit hidrico",
        "state": "severo"
      }
    ]
  }
}
```

Body recomendado para una explicación mejor:

```json
{
  "risk_assessment": {
    "risk_level": "alto",
    "risk_score": 0.82,
    "confidence": "media_alta",
    "risk_factors": [
      {
        "label": "Deficit hidrico",
        "state": "severo"
      }
    ]
  },
  "plant_state": {
    "phase": "Llenado de grano"
  },
  "official_context": {
    "canicula_2026_watch": true
  },
  "recommendations": [
    "Aplicar mulch para conservar humedad",
    "Monitorear signos de estres hidrico"
  ],
  "audience": "productor"
}
```

Importante:

- no asumas que basta con enviar entero `data` de `/api/risk/assessment` como único `risk_assessment`
- si quieres la mejor narración, mappea al menos:
  - `data.risk_level`, `data.risk_score`, `data.confidence`, `data.risk_factors`
  - `data.plant_state`
  - `data.official_context`
  - `data.recommendations`

Uso frontend:

- botón “Explicar en simple”
- modal, card o bloque narrativo

---

## 9. AI Tools — manifest

```http
GET /api/v1/ai/tools/manifest
```

No requiere parámetros.

El backend anuncia 4 tools:

- `getRiskAssessment`
- `getOfficialContext`
- `getPhenologyContext`
- `explainRecommendation`

Uso frontend:

- registrar estas tools en un agente con function calling
- no codificar una lista antigua de 10 tools

---

## 10. AI Tools — dispatcher

```http
POST /api/v1/ai/tools/call
Content-Type: application/json
```

Siempre envía:

```json
{
  "tool_name": "getRiskAssessment",
  "arguments": {}
}
```

Ejemplos vigentes:

### `getRiskAssessment`

```json
{
  "tool_name": "getRiskAssessment",
  "arguments": {
    "crop": "maiz",
    "sowing_date": "2026-05-20",
    "lat": 13.69,
    "lon": -89.21,
    "target_date": "2026-08-15"
  }
}
```

### `getOfficialContext`

```json
{
  "tool_name": "getOfficialContext",
  "arguments": {
    "target_date": "2026-08-15"
  }
}
```

### `getPhenologyContext`

```json
{
  "tool_name": "getPhenologyContext",
  "arguments": {
    "crop": "maiz",
    "sowing_date": "2026-05-20",
    "target_date": "2026-08-15"
  }
}
```

### `explainRecommendation`

```json
{
  "tool_name": "explainRecommendation",
  "arguments": {
    "risk_assessment": {
      "risk_level": "alto",
      "risk_score": 0.82
    },
    "official_context": {
      "canicula_2026_watch": true
    },
    "audience": "productor"
  }
}
```

No bases un agente nuevo en tools viejas como:

- `get_current_features`
- `get_location_context`
- `get_agro_advisory`
- `buildRuntimeContext`

---

## 11. Flujo recomendado para frontend

```text
1. App init
   GET /health

2. Onboarding / parcela
   GET /api/geo/context?lat=X&lon=Y

3. Dashboard principal
   GET /api/weather/observed?lat=X&lon=Y
   GET /api/risk/assessment?crop=X&sowing_date=X&lat=X&lon=X&target_date=X

4. Vista de planificación
   GET /api/weather/forecast?lat=X&lon=Y&target_date=X

5. Chat / asistente
   GET /api/v1/ai/tools/manifest
   POST /api/v1/ai/tools/call

6. Explicación simple
   GET /api/risk/assessment
   POST /api/llm/explain
```

---

## 12. Política de `meta`

Todas las respuestas incluyen `meta`.

| Campo | Significado | Acción frontend |
|---|---|---|
| `cached: true` | respuesta servida desde caché válida | normal |
| `stale: true` | upstream falló y se devolvió caché vieja | mostrar “datos desactualizados” |
| `upstream_status: "failed"` | no se pudo resolver la fuente principal | mostrar error degradado |
| `upstream_status: "degraded"` | algunas fuentes fallaron | mostrar advertencia parcial |
| `fetched_at` | timestamp de refresco | mostrar “actualizado hace...” si aporta valor |

---

## 13. Resumen para el agente de frontend

Si el agente va a construir UI y wiring de datos, estas son las reglas:

- usar la superficie `/api/weather`, `/api/geo`, `/api/risk`, `/api/llm`
- usar `/api/v1/ai/tools/*` solo para el agente conversacional
- usar `/api/v1/documents/latest` solo para documentos/RAG
- no apoyarse en rutas v1 retiradas
- tratar `gt_16_days` como escenario, no forecast puntual
- tratar `soil_moisture_model` como modelo, no medición real
- para riesgo usar `plant_state`, no `phenology`
- para runtime context usar `plant_state`, `risk_assessment`, `sources_used`, `source_policy`, `missing_required_user_data`
