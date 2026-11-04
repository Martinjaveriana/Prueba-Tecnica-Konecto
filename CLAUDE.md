# Contexto del proyecto: Konecto AI Engineer Assessment — Series 76 Technical Assistant

## Quién soy y qué está en juego
- Soy Martín Sanmiguel, estudiante de 5.º semestre de Ingeniería de Sistemas (Colombia).
- Estoy en proceso con **Konecto** (agentes de IA por voz/chat para empresas en Norteamérica). Ya pasé la entrevista inicial y la del CEO/cofundador.
- Este es el **desafío técnico**. Si sale bien, sigue una última charla donde debo **explicar y defender mi arquitectura y trade-offs**, y luego la propuesta económica.
- **Plazo:** 7 días desde el 4 de noviembre de 2026 → entregar a más tardar el **11 de noviembre de 2026** respondiendo el correo con el link al repo de GitHub.

## Cómo quiero que me ayudes (instrucciones para el asistente)
- Konecto **espera** que use IA para escribir el código. Lo que evalúan es que **yo entienda lo construido y las decisiones**. Por eso:
  - Explícame cada decisión importante y su alternativa descartada, en español y de forma sencilla.
  - Antes de escribir mucho código, propón el enfoque y espera mi visto bueno.
  - Al terminar cada parte, dame 3–5 preguntas que podrían hacerme en la entrevista sobre esa parte, con la respuesta.
- Avanza por fases pequeñas y verificables. Prioriza lo **obligatorio** antes que lo opcional.
- Nunca escribas claves reales en el código ni en commits. La clave va en `.env` (ignorado por git); en el repo solo `.env.example`.

## El enunciado (resumen fiel)
Un equipo de ingeniería de planta busca a mano en tablas del fabricante para elegir **actuadores eléctricos Series 76**. Hay que construir:
1. **Backend en Python** con un agente de IA que:
   - **Specific Data Retrieval:** responde con precisión sobre un actuador dado su **Base Part Number**.
   - **Product Recommendation:** recomienda uno o más actuadores según requisitos técnicos del usuario.
2. **App móvil nativa** donde el usuario habla con el agente y retoma conversaciones.

### Recursos
- `series_76_electric_data.pdf`: tablas eléctricas de un subconjunto de actuadores, separadas por **enclosure, power supply y service type**. **Única fuente de verdad para los números.**
- `series_76_summary.pdf`: contexto de negocio para entender los datos.
- **Clave de OpenRouter con tope de USD 10** (no se recarga). Modelos configurables por variables de entorno y elección justificada en el README.
- Pista: usar **Google AI Studio (API gratuita)** para experimentar (p. ej., extracción de tablas) sin gastar la clave.

### Parte A — Backend (obligatorio)
- REST con **FastAPI**.
- Agente orquestado con **LangChain**, con **al menos una Tool custom de LangChain** que consulte los datos de las tablas.
- **Script de ingesta** (`ingest.py`) que procesa el PDF y lo deja en el formato que usa la tool.
- **Multi-turno** por `session_id`: un seguimiento como "¿y cuánta potencia consume?" se resuelve sin repetir el part number.
- **Historial persistido**: sobrevive a reiniciar el backend.
- **Edge cases**: part numbers inválidos, datos faltantes, consultas ambiguas, requisitos que ningún modelo cumple.
- Base de datos: **PostgreSQL local** (Docker Compose). Si hay búsqueda semántica: **pgvector**.
- **Los números que ve el usuario deben coincidir con las tablas. El LLM no puede inventar ni "recordar" números.**

Contrato fijo:
```
POST /api/conversation
Request:  { "session_id": "<opcional>", "query": "<pregunta>" }
Response: { "session_id": "...", "answer": "...", ... }   // el resto lo diseño yo
```
Sin `session_id` → crea conversación nueva y la devuelve.

Endpoints sugeridos (puedo cambiarlos si lo justifico en el README):
```
GET  /api/sessions                 -> id, title, date
GET  /api/sessions/{id}/messages   -> historial para retomar
POST /api/auth/login               -> opcional { email, password } -> { token }
```

### Parte B — App móvil (obligatorio)
Nativa: **Kotlin + Jetpack Compose** o **Swift + SwiftUI**. Tres pantallas:
1. **Conversaciones**: lista de conversaciones guardadas; abrir una (carga historial y sigue con el mismo contexto) o crear nueva.
2. **Chat**: multi-turno con `session_id`. Datos de producto **claros y comparables** (no un párrafo). **No mostrar nombres de tools ni detalles internos.**
3. **Debug** (solo desarrolladores): por cada respuesta, tools llamadas, parámetros y datos devueltos. Oculta al usuario final; documentar cómo se abre.
Todas manejan **estados de carga y errores** (p. ej., backend caído).

### Parte C — Opcional (solo si sobra tiempo)
- **Login** email/contraseña → token; contraseñas hasheadas; usuarios de prueba precargados y documentados; `Authorization: Bearer <token>`; cada usuario ve solo sus conversaciones.
- **Mensajes de voz**: transcripción en el dispositivo, con modelo open source o con la clave de OpenRouter (gasta del mismo presupuesto).

### Entregables (un solo repo de GitHub)
- Código del backend y la app.
- `ingest.py` + datos procesados (o instrucciones para generarlos).
- `Dockerfile` del backend + `docker-compose.yml` (backend + base de datos).
- `.env.example` sin claves reales.
- **README** que permita correr todo sin preguntarme nada: setup y variables, backend con Docker y cómo acceder a la API, ingesta (cómo correrla y dónde quedan los datos), app (emulador/dispositivo, cómo apuntarla al backend, cómo abrir debug), **diseño y arquitectura con trade-offs**, opcionales si los hay.
- **Directorio de configuración del asistente de IA** (`.claude/`, `.cursor/`, etc.) para que vean mi setup real. → Este archivo puede vivir ahí.

### Criterios críticos de evaluación
- **Reproducibilidad**: si no lo pueden correr siguiendo el README, no avanzo.
- **Robustez**: lo probarán con **sus propios casos de prueba**, más allá de los ejemplos. Debe ser general.
- Evalúan: diseño agéntico, creación de tools, **manejo de datos tabulares** (punto clave) y pensamiento arquitectónico.

## Enfoque propuesto (punto de partida, a validar cuando veamos los PDFs)

### Idea central
Los datos son **tablas estructuradas con números exactos** → guardarlos como **filas SQL normalizadas** y consultarlos con **filtros deterministas**, no con RAG por similitud. El LLM solo **interpreta la pregunta, elige la tool y redacta**; los números salen de la base de datos.
- pgvector es opcional: podría usarse para el `summary.pdf` (contexto de negocio) o para mapear términos ambiguos, pero no para los números.

### Ingesta (`ingest.py`)
1. Extraer tablas del PDF de forma determinista (pdfplumber / camelot). Si el layout es difícil, usar un LLM gratuito (Google AI Studio) **solo en desarrollo** para apoyar la extracción, y guardar el resultado procesado en el repo para que sea reproducible.
2. Normalizar: cada fila hereda el contexto de su tabla (**enclosure, power supply, service type**). Unidades consistentes, tipos numéricos, nulos explícitos para datos faltantes.
3. Validar: conteo de filas por tabla, part numbers únicos por combinación, rangos razonables; tests que comparen algunos valores contra el PDF.
4. Cargar en PostgreSQL (idempotente: se puede correr varias veces).

### Tools de LangChain (borrador)
- `get_actuator_specs(base_part_number, filtros_opcionales)`: devuelve todas las variantes de ese part number (puede haber varias por enclosure/voltaje). Si no existe → error claro + sugerencias de part numbers parecidos.
- `recommend_actuators(requisitos)`: filtros tipados (torque mínimo, voltaje, fase, enclosure, service type, etc.) → SQL parametrizado. Si nada cumple → decirlo y mostrar los más cercanos indicando qué requisito no cumplen.
- (Posible) `list_available_options()`: valores válidos de enclosure/voltajes/etc., para resolver ambigüedades y preguntar al usuario.
- Las tools devuelven **JSON estructurado**. Nunca SQL libre generado por el LLM (seguridad y exactitud).

### Respuesta de la API (diseño propio)
```json
{
  "session_id": "...",
  "answer": "texto breve del agente",
  "products": [ { "base_part_number": "...", "specs": { ... } } ],
  "clarification_needed": false,
  "debug": { "tool_calls": [ { "name": "...", "args": { ... }, "output": { ... } } ] }
}
```
- `products` se llena **directamente desde la salida de las tools**, no desde el texto del LLM → la app muestra tarjetas/tablas con números garantizados.
- `debug` alimenta la pantalla de debug (se podría ocultar tras un header o flag).

### Conversaciones
- Tablas `sessions` (id, title, created_at) y `messages` (session_id, role, content, tool_calls JSON, products JSON, created_at) en PostgreSQL.
- En cada turno se carga el historial de la sesión al agente → resuelve "¿y cuánta potencia consume?".
- Título de la sesión: derivado de la primera pregunta (sin gastar LLM).

### Modelos y presupuesto (USD 10)
- Modelo principal: uno **barato y bueno en tool calling** en OpenRouter; revisar precios actuales antes de elegir. Configurable por `.env` (`LLM_MODEL`, etc.).
- Desarrollo con Google AI Studio gratis cuando se pueda; `max_tokens` acotado; historial recortado; pocas pruebas end-to-end con la clave real.
- Justificar elección en el README (costo vs. calidad de tool calling).

### App
- Probablemente **Kotlin + Jetpack Compose** (Android Studio funciona en Windows/Mac/Linux; SwiftUI exige Mac + Xcode). Confirmar según mi equipo.
- Pantallas: Conversaciones, Chat (tarjetas/tabla comparativa a partir de `products`), Debug (oculta, p. ej. pulsación larga en un mensaje o toque múltiple en el título).
- URL del backend configurable (emulador Android → `http://10.0.2.2:8000`).
- Estados de carga, error y reintento.

## Plan de trabajo sugerido (4–11 nov)
1. **Día 1:** leer ambos PDFs, entender columnas y estructura; crear repo, `docker-compose` con Postgres (+pgvector), `.env.example`.
2. **Día 2:** `ingest.py` + validación + tests de datos.
3. **Día 3:** tools + agente LangChain + pruebas de edge cases sin LLM (tests unitarios de las tools).
4. **Día 4:** FastAPI, persistencia de sesiones, contrato de respuesta, Dockerfile.
5. **Días 5–6:** app móvil (3 pantallas + manejo de errores).
6. **Día 7:** README completo, probar desde cero en limpio (clonar → seguir README → funciona), revisar que no haya claves en el historial de git, enviar. Opcionales solo si sobra tiempo.

## Edge cases a cubrir y probar
- Part number inexistente, mal escrito, con espacios/minúsculas.
- Part number con varias variantes (distinto voltaje/enclosure) → preguntar o mostrar todas.
- Campo sin dato en la tabla → decir "no disponible", nunca inventar.
- Requisitos imposibles → decirlo + alternativas más cercanas.
- Preguntas fuera de tema → redirigir amablemente.
- Seguimiento sin contexto previo ("¿y la potencia?" en sesión nueva) → pedir el part number.
- Unidades distintas a las de la tabla (p. ej., otra unidad de torque) → convertir con código, no con el LLM.

## Pendiente
- Adjuntar/leer `series_76_summary.pdf` y `series_76_electric_data.pdf` (aún no los he compartido en esta conversación). Lo primero de la siguiente sesión es analizarlos y ajustar el esquema de datos.
