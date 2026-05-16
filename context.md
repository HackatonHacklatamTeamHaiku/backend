# 🌽 SATO-Agro
## Sistema de Alerta Temprana y Prescripción para Mitigación de la Canícula

---

## 🧭 Contexto del Track
**Environment & Climate Risk**
> Rastrea, predice y mitiga el daño ambiental.

El objetivo es construir soluciones que:
- Detecten riesgo ambiental antes de que ocurra el daño
- Permitan actuar a tiempo
- Ayuden a comunidades, técnicos o instituciones a responder

---

## 🚨 Problema

Los pequeños agricultores de maíz y frijol en El Salvador enfrentan pérdidas severas durante la canícula.

Aunque existen datos climáticos y monitoreo institucional:
- La información es **técnica y dispersa**
- No se traduce en **acciones concretas**
- No llega de forma útil al agricultor

👉 Resultado: decisiones tardías → pérdidas de cosecha

---

## 🎯 Problem Statement

> Pequeños productores de maíz y frijol necesitan alertas prescriptivas con suficiente anticipación para tomar decisiones agrícolas clave, pero hoy la información climática no se traduce en acciones concretas adaptadas a su cultivo, etapa y contexto.

---

## 💡 Solución: SATO-Agro

Sistema que convierte datos climáticos y satelitales en **acciones agrícolas concretas** para prevenir pérdidas por canícula.

---

## 🔁 Flujo del Sistema

### 🟢 Entradas

**Automáticas:**
- Precipitación (CHIRPS)
- Días secos consecutivos
- Anomalía de lluvia
- (Opcional) NDVI / estrés vegetal

**Usuario:**
- Cultivo (maíz / frijol)
- Fecha de siembra
- Ubicación (municipio o coordenada)

---

### ⚙️ Procesamiento

Reglas simples basadas en:
- Déficit de lluvia
- Racha seca
- Etapa fenológica (estimada)

Ejemplo:
Si:

lluvia < promedio

días secos consecutivos

cultivo en etapa crítica

→ riesgo alto


---

### 🔴 Salidas (Core del MVP)

#### 1. Nivel de riesgo
- Bajo / Medio / Alto / Crítico

#### 2. Explicación
> “Lluvia 40% por debajo del promedio + 10 días secos”

#### 3. Acción prescriptiva
> “Priorizar riego en los próximos 5 días y evitar fertilización”

#### 4. Ventana de acción
> “Actuar en 5 días”

#### 5. Mensaje listo (WhatsApp/SMS)
ALERTA SATO 🌽

Municipio: X
Cultivo: Maíz
Riesgo: ALTO

Se esperan condiciones de canícula en los próximos días.

👉 Acción:

Priorizar riego

Evitar fertilización

⏱️ Actuar en 5 días


#### 6. Vista para extensionistas
- Lista priorizada de productores por riesgo

---

## 🧱 Pilares del MVP

1. **Acción prescriptiva**
   - No solo informa → recomienda qué hacer

2. **Timing**
   - Alertas antes del daño

3. **Contexto agrícola**
   - Cultivo + fecha de siembra + etapa

4. **Accesibilidad operativa**
   - WhatsApp / SMS / lenguaje simple

5. **Priorización de riesgo**
   - A quién atender primero

---

## 👥 Usuario

**Primario:**
- Extensionistas
- Cooperativas
- Técnicos agrícolas

**Beneficiario:**
- Agricultor (maíz / frijol)

---

## 📊 Diferenciación

| Sistema tradicional | SATO-Agro |
|--|--|
| Muestra datos | Indica acciones |
| Mapas generales | Recomendaciones personalizadas |
| Monitoreo | Prescripción |
| Información | Decisión |

---

## 🚀 MVP (Hackathon)

### Lo mínimo a construir:

1. Input:
   - ubicación + cultivo + fecha

2. Procesamiento:
   - riesgo basado en lluvia (CHIRPS)

3. Output:
   - riesgo
   - explicación
   - acción
   - mensaje listo

---

## 🧪 Hipótesis a validar

1. Es posible detectar riesgo con datos abiertos
2. El riesgo puede convertirse en acción concreta
3. El formato es usable para el usuario final

---

## 🧠 Insight clave

> El problema no es la falta de datos.
> Es la falta de decisiones accionables a tiempo.

---

## 🎤 Pitch corto

> SATO-Agro convierte datos climáticos y satelitales en instrucciones accionables para que agricultores de maíz y frijol reduzcan pérdidas por canícula antes de que el daño sea irreversible.

---