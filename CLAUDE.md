# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Contexto del proyecto: Konecto AI Engineer Assessment — Series 76 Technical Assistant

## Quién soy y qué está en juego
- Soy Martín Sanmiguel, estudiante de 5.º semestre de Ingeniería de Sistemas (Colombia).
- Estoy en proceso con **Konecto** (agentes de IA por voz/chat para empresas en Norteamérica). Ya pasé la entrevista inicial y la del CEO/cofundador.
- Este es el **desafío técnico**. Si sale bien, sigue una última charla donde debo **explicar y defender mi arquitectura y trade-offs**, y luego la propuesta económica.
- **Plazo:** 7 días desde el 4 de noviembre de 2026 → entregar a más tardar el **11 de noviembre de 2026** respondiendo el correo con el link al repo de GitHub.

## Cómo quiero que me ayudes (instrucciones para el asistente)
- Konecto **espera** que use IA para escribir el código. Lo que evalúan es que **yo entienda lo construido y las decisiones**. Por eso:
  - Explícame cada decisión importante y su alternativa descartada, en español y de forma sencilla, con un ejemplo concreto.
  - Antes de escribir mucho código, propón el enfoque y espera mi visto bueno.
  - Al terminar cada parte, dame 3–5 preguntas que podrían hacerme en la entrevista sobre esa parte, con la respuesta.
  - Mantén actualizados `docs/decisiones-de-diseno.md` (cada decisión, su alternativa descartada y cómo funciona lo construido) y `docs/guia-de-comandos.md` (cada comando y el flujo).
- Avanza por fases pequeñas y verificables. Prioriza lo **obligatorio** antes que lo opcional.
- La clave va en `.env` (ignorado por git); en el repo solo `.env.example`.

## Comandos
Todos se ejecutan desde la raíz del repo, salvo que se indique otra cosa. Funcionan con `.env` vacío porque todo menos la clave tiene un valor por defecto.

Levantar y detener la base de datos:
```bash
docker compose up -d --wait db
docker compose down
```

Abrir una consola SQL:
```bash
docker compose exec db psql -U konecto -d series76
```

Correr todos los tests (necesitan la base de datos arriba), o solo uno:
```bash
cd backend && uv run pytest
cd backend && uv run pytest tests/test_build.py::test_values_match_the_pdf
```

Ingesta:
```bash
cd backend && uv run python ingest.py
cd backend && uv run python ingest.py --build
cd backend && uv run --group extract python ingest.py --extract
cd backend && uv run --group extract python ingest.py --audit
```
En orden: cargar el JSON revisado en Postgres, reconstruirlo desde las tablas crudas, volver a leer el PDF con Docling y auditar con Google AI Studio. Docling y el SDK de Google están en el grupo opcional `extract`, que no va en la imagen Docker.

Backend completo con Docker (crea las tablas y carga los datos al arrancar; API en `http://localhost:8000/docs`):
```bash
docker compose up -d --build --wait
```

API sin Docker, y comparación de modelos (gasta de la clave de OpenRouter):
```bash
cd backend && uv run uvicorn app.api:app --reload
cd backend && uv run python eval_agent.py openai/gpt-5-mini anthropic/claude-haiku-5.5 qwen/qwen3.7-flash
```

Los tests usan un LLM falso (`tests/fake_llm.py`) y no gastan presupuesto. No hay linter configurado todavía.

App Android (desde `android/`; `JAVA_HOME` apunta al Java de Android Studio). Los tests no necesitan emulador; `installDebug` necesita el emulador y el backend arriba:
```bash
cd android && JAVA_HOME=~/android-studio/jbr ./gradlew assembleDebug testDebugUnitTest
cd android && JAVA_HOME=~/android-studio/jbr ./gradlew installDebug
~/Android/Sdk/emulator/emulator -avd Medium_Phone_API_37.0 -no-snapshot-save &
```

## Estructura
- `backend/`: Python 3.12 gestionado con `uv`. La configuración está en `app/config.py` y lee el `.env` de la raíz.
- `backend/ingestion/`: la ingesta en etapas. `spec.py` declara la estructura de las 7 tablas, `extract.py` lee con Docling, `build.py` limpia y valida, `load.py` carga y `audit.py` compara con el modelo de visión.
- `backend/app/api.py` (endpoints), `agent.py` (instrucciones, historial, debug), `products.py` (modelo `Product`: los mismos campos para todo producto, completados desde la base), `numbers.py` (verificador de números), `conversations.py` (persistencia). El LLM solo elige tools y redacta: lo demás lo decide el código.
- `backend/app/catalog.py`: las consultas y las reglas de búsqueda, sin LLM. `backend/app/tools.py` las expone como tools de LangChain; la lógica va en `catalog.py`.
- `backend/data/`: `raw/` (lo que leyó Docling), `corrections.json` (correcciones registradas), `processed/actuators.json` (la fuente de la carga). Un valor mal leído se resuelve en `corrections.json`, nunca editando `processed/`.
- `android/`: app en Kotlin + Jetpack Compose. `data/` (DTOs, Retrofit, `ConversationRepository` que traduce errores a `AppError`), `ui/` una carpeta por pantalla con su ViewModel, `AppContainer.kt` (inyección manual). Plugin de Android 9.5.1, Gradle 9.6.1, `minSdk` 26, `targetSdk` 37. En Android 17 pide `ACCESS_LOCAL_NETWORK`: sin él las conexiones a 10.0.2.2 se quedan colgadas.
- `docs/`: enunciado (`assessment-en.pdf`) y los PDFs fuente.
- PostgreSQL 16 se publica en el puerto **5433** de la máquina, porque el 5432 suele estar ocupado.

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
- Pista: usar **Google AI Studio (API gratuita)** para experimentar sin gastar la clave.

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
Nativa: **Kotlin + Jetpack Compose**. Tres pantallas:
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
- **Directorio de configuración del asistente de IA** (`.claude/`) para que vean mi setup real.

### Criterios críticos de evaluación
- **Reproducibilidad**: si no lo pueden correr siguiendo el README, no avanzo.
- **Robustez**: lo probarán con **sus propios casos de prueba**, más allá de los ejemplos. Debe ser general.
- Evalúan: diseño agéntico, creación de tools, **manejo de datos tabulares** (punto clave) y pensamiento arquitectónico.

## Lo que sabemos de los datos
**`series_76_electric_data.pdf` no tiene texto: sus tablas son imágenes.** pdfplumber y camelot no extraen nada.

| Pág. | Enclosure | Alimentación | Servicio | Frecuencia | Filas |
|---|---|---|---|---|---|
| 1 | Weatherproof | 110 V, 1 fase | On/Off y Modulating | 60/50 Hz | 11 |
| 1 | Weatherproof | 220 V, 1 fase | On/Off y Modulating | 60/50 Hz | 16 |
| 2 | Weatherproof | 220 V, 3 fases | No lo distingue | 60/50 Hz | 11 (4 con N/A) |
| 3 | Explosionproof | 24 V AC/DC | Solo On/Off | Sin frecuencia | 5 |
| 3 | Explosionproof | 24 V solo DC | Solo Modulating | Sin frecuencia | 5 |
| 4 | Explosionproof | 110 V, 1 fase | On/Off y Modulating | 60/50 Hz | 10 |
| 4 | Explosionproof | 220 V, 1 fase | On/Off y Modulating | 60/50 Hz | 10 |

Trampas que el código debe respetar:
- `761A00-11380000/A`, el ejemplo del `summary.pdf`, **no está en las tablas**.
- El part number completo parece único. La ambigüedad aparece con los parciales: `761A00` da 3 opciones y `761X30` da 4.
- La potencia del motor es una celda combinada que abarca varias filas y cambia según el voltaje (764X: 90 W a 110 V, 180 W a 220 V).
- El `*` de los tamaños 6 y 7 significa "no certificado CSA": es un dato, no parte del part number.
- Cuatro modelos de 3 fases dicen N/A: existen pero no tienen datos, que es distinto de no existir.
- Combinaciones sin ningún modelo: Explosionproof de 3 fases, Weatherproof de 24 V, 24 V AC Modulating.
- El `summary.pdf` no menciona los 220 V de 3 fases, pero sí están en las tablas.

## Decisiones

### Aprobadas
- **SQL con filtros exactos, no RAG.** El LLM interpreta la pregunta, elige la tool y redacta; los números salen de la base de datos.
- **Sin pgvector:** no hay búsqueda semántica; el `summary.pdf` cabe como glosario en el prompt.
- **Esquema de tres tablas:**
  - `actuators`: part number, alias (`1A`, `5X`), tamaño, enclosure, voltaje, fases, tipo de corriente, vatios, certificaciones, clasificación de áreas peligrosas (`hazardous_classification`), si tiene datos, página de origen.
  - `service_ratings` (part number + servicio): torque en in-lbs y Nm, duty cycle, ciclos y arranques por hora.
  - `electrical_ratings` (part number + frecuencia, `NULL` en 24 V): velocidad, FLA, LRA.
- **Monorepo** con `backend/` y `android/`; app Android porque SwiftUI exige Mac.
- **Ingesta con Docling, limpieza por código y auditoría:**
  - `--extract` lee el PDF con Docling, como dependencia opcional porque pesa varios GB. No va en la imagen Docker.
  - El código limpia errores de lectura (`1133OC0O`, part numbers juntos en una celda, notas pegadas). Las reglas solo marcan; cada corrección de un valor (`£3` → 33) queda registrada y revisada contra la imagen.
  - La potencia del motor se declara por grupos, porque Docling no conserva cuántas filas abarca cada celda.
  - Un modelo de Google AI Studio audita una vez durante el desarrollo: lee las páginas por separado y se revisa cada diferencia. No corrige nada.
  - `python ingest.py` carga el JSON revisado del repo, sin clave y sin Docling.
  - Descartados tras probarlos con el PDF: pdfplumber (0 líneas y 0 tablas), pymupdf4llm (58 de 68 part numbers), Tesseract (cambia dígitos), RapidOCR solo (cruza columnas).
- **Tablas de 3 fases, almacenamiento:** se guarda una sola fila en `service_ratings` con servicio `unspecified`. El torque no se copia a On/Off ni a Modulating, porque la tabla no dice a cuál corresponde.
- **Unidades de torque:** comparar en la columna de la unidad que pidió el usuario, porque el PDF redondea (880 in-lbs figura como 100 Nm, y 100 Nm son unos 885 in-lbs). Solo se convierten unidades que el PDF no tiene.
- **Alias:** columna con el nombre corto (`761A00-11300000/A` → `1A`), calculada por código a partir del part number. No es única: `1A` corresponde a 3 modelos y `1X` a 4, así que buscar por alias puede devolver varios y el agente debe mostrarlos o preguntar.
- **Tablas de 3 fases, búsquedas:** las filas `unspecified` aparecen al filtrar por On/Off o Modulating, con un aviso visible: "Encontré `763B00-11330C00/A`, de 500 Nm. Ojo: la tabla no indica si ese valor aplica a Modulating."

## Fase 3: agente y API (diseño aprobado)
- Agente con `create_agent` de LangChain, las 3 tools y OpenRouter mediante `langchain-openai`. Modelo configurable por `.env`; por defecto `anthropic/claude-haiku-5.5`, elegido con `eval_agent.py`. `LLM_MAX_TOKENS=3000`, porque los modelos que razonan dejaban respuestas vacías con 1000.
- El código quita de la respuesta el marcador `[Part numbers consulted]`, porque los modelos lo copiaban.
- Endpoints: `POST /api/conversation`, `GET /api/sessions`, `GET /api/sessions/{id}/messages`, `GET /health`.
- Historial en tablas `sessions` y `messages`. Al LLM se le envían los últimos 20 turnos (y un aviso si hay más antiguos): solo el texto de cada uno y, escrita por el código, la lista de part numbers consultados: `[Modelos consultados: 762A00-11300000/A]`. En los seguimientos vuelve a consultar la tool; nunca reutiliza números de turnos anteriores.
- `products` y `needs_clarification` los decide el código a partir de lo que devolvieron las tools, no el LLM.
- Un verificador revisa que cada número de la respuesta aparezca en lo que devolvieron las tools en ese turno o en sus argumentos; si no, lo marca en `debug`. El LLM no hace aritmética: rangos de tolerancia y conversiones a ft-lb y kgf·m los calcula el código.
- `debug` siempre va en la respuesta; la app lo oculta.
- El backend crea las tablas y carga los datos al arrancar. Un turno se guarda completo o no se guarda.
- Los tests usan un LLM falso; la clave real solo para la comparación de modelos y unas pocas pruebas finales.

### App
URL del backend configurable (emulador Android → `http://10.0.2.2:8000`). Chat con tarjetas o tabla comparativa a partir de `products`. Debug oculta, abierta con un gesto documentado en el README.

## Plan de trabajo (4–11 nov)
1. **Fase 0, hecha:** estructura del repo, Postgres en Docker, test de conexión.
2. **Fase 1, hecha:** `ingest.py`, validación, tests y esquema. Repetir `--extract` da archivos idénticos. La auditoría con `gemini-3.5-flash` comparó 869 celdas y encontró una diferencia, en la que el PDF confirma nuestro dato.
3. **Fase 2, hecha:** `get_actuator_specs`, `recommend_actuators` y `list_available_options`, con sus edge cases probados sin LLM. Las reglas y sus razones están en `docs/decisiones-de-diseno.md`.
4. **Fase 3, hecha:** agente, API, persistencia, verificador de números y Dockerfile. Modelo elegido: `anthropic/claude-haiku-5.5` (14/14, 3.2 s, USD 0.0007 por pregunta), comparado con GPT-5 mini y Qwen 3.7 Flash. Detalle en `docs/decisiones-de-diseno.md`.
5. **Fase 4:** app Android. **4a hecha:** proyecto, lista, historial, estados de error y permiso de red local. **4b hecha:** envío con Retry, tarjetas, tabla comparativa abierta en `focus`, opciones para tocar, negritas y viñetas. **4c hecha:** modo debug (mantener "New conversation" 3 s y confirmar; luego pulsación larga sobre una respuesta) y README de la app con capturas en `docs/screenshots/`. Las instrucciones prohíben tablas Markdown (Haiku las escribía en 3 de 14); repetida la comparación con Haiku: 14/14, 0 tablas.
6. **Pruebas adversariales, hechas:** 58 casos (81 turnos); corregidos Q10 (`sort_by`), notas del PDF, ventana de historial, normalización de part numbers, conversiones, cálculos, verificador e idioma. Detalle en `docs/decisiones-de-diseno.md`. Comparación final: 14/14.
7. **Último día:** README completo, probar desde un clon limpio, revisar que no haya claves en el historial de git, enviar. Opcionales solo si sobra tiempo.

## Edge cases a cubrir y probar
- Part number inexistente, mal escrito, con espacios/minúsculas.
- Part number parcial con varias variantes → preguntar o mostrar todas.
- Campo sin dato en la tabla → decir "no disponible", nunca inventar.
- Requisitos imposibles → decirlo + alternativas más cercanas.
- Preguntas fuera de tema → redirigir amablemente.
- Seguimiento sin contexto previo ("¿y la potencia?" en sesión nueva) → pedir el part number.
- Unidades distintas a las de la tabla (p. ej., ft-lb) → convertir con código, no con el LLM.
