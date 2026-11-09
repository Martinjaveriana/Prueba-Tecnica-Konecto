# Guía de comandos

Qué ejecutar según lo que quieras hacer. Las razones detrás de cada paso están en [decisiones-de-diseno.md](decisiones-de-diseno.md).

## El flujo completo

```
PDF ──(--extract)──> raw/docling_tables.json
                              │
          spec.py + corrections.json
                              │  build.py (--build, y también al final de --extract)
                              ▼
                     processed/actuators.json ──(sin opciones)──> PostgreSQL
                              │
                       (--audit) compara con Gemini ──> audit/report.json
```

## Uso diario

Parten de que ya hiciste la preparación inicial, más abajo.

| Quiero... | Pasos |
|---|---|
| **Probar que el backend funciona** | [Probar el backend paso a paso](#probar-el-backend-paso-a-paso) |
| **Levantar todo y conversar con el agente** | [Levantar el backend con Docker](#levantar-el-backend-con-docker) y [preguntar](#preguntar-desde-la-terminal) |
| Trabajar en el código del backend | [Levantar la base](#levantar-la-base), [cargar los datos](#cargar-los-datos) y [correr la API sin Docker](#correr-la-api-sin-docker) |
| Tener los datos en la base | [Levantar la base](#levantar-la-base) y [cargar los datos](#cargar-los-datos) |
| Comprobar que todo está bien | [Levantar la base](#levantar-la-base) y [correr los tests](#correr-los-tests) |
| Volver a leer el PDF | [Extraer](#extraer-del-pdf), revisar con `git diff`, [correr los tests](#correr-los-tests) y [cargar los datos](#cargar-los-datos) |
| Corregir un valor | Editar `corrections.json`, [reconstruir](#reconstruir-el-resultado), [correr los tests](#correr-los-tests) y [cargar los datos](#cargar-los-datos) |
| Auditar los datos | [Auditar](#auditar) y revisar `audit/report.json` |

## Preparación inicial

Se hace una sola vez, desde la raíz del repo. Necesitas Docker y [uv](https://docs.astral.sh/uv/).

Crea tu configuración. Si ya tienes un `.env` con claves, no lo ejecutes, porque lo sobrescribe:

```bash
cp .env.example .env
```

Para que el agente responda, pon tu clave en `OPENROUTER_API_KEY` dentro de `.env`. Para auditar, pon la de Google en `GOOGLE_API_KEY`.

## Backend y API

### Levantar el backend con Docker

Desde la raíz del repo. Levanta la base y el backend, crea las tablas y carga los datos. Después de cambiar el código o el `.env`, vuelve a correrlo.

```bash
docker compose up -d --build --wait
```

La documentación interactiva queda en <http://localhost:8000/docs>.

### Ver los registros del backend

```bash
docker compose logs -f backend
```

### Preguntar desde la terminal

Gasta de la clave de OpenRouter.

```bash
curl -s -X POST http://localhost:8000/api/conversation -H "Content-Type: application/json" -d '{"query": "What is the output torque of 762A00-11300000/A?"}'
```

Para seguir la misma conversación, agrega el `session_id` que devolvió la respuesta:

```bash
curl -s -X POST http://localhost:8000/api/conversation -H "Content-Type: application/json" -d '{"session_id": "PEGALO-AQUI", "query": "And how much power does it draw?"}'
```

### Ver las conversaciones guardadas

```bash
curl -s http://localhost:8000/api/sessions
```

### Correr la API sin Docker

Desde `backend/`, con la base levantada. Se recarga sola cuando cambia el código. Si el backend de Docker está corriendo, primero detenlo con `docker compose stop backend`, porque usan el mismo puerto.

```bash
uv run uvicorn app.api:app --reload
```

### Comparar modelos

Desde `backend/`. Gasta de la clave de OpenRouter, unos centavos por modelo. Corre las mismas 14 preguntas con cada modelo y guarda el resultado en `eval/results.json`. Las dos corridas con las que se eligió el modelo están en `eval/results-run1-max-tokens-1000.json` y `eval/results-run2-max-tokens-3000.json`; la tercera, solo Haiku tras prohibir las tablas, en `eval/results-run3-no-tables.json`. Para guardar en otro archivo: `--out eval/mi-corrida.json`.

```bash
uv run python eval_agent.py openai/gpt-5-mini anthropic/claude-haiku-5.5 qwen/qwen3.7-flash
```

## Probar el backend paso a paso

Desde la raíz del repo, con `OPENROUTER_API_KEY`, `LLM_MODEL=anthropic/claude-haiku-5.5` y `LLM_MAX_TOKENS=3000` en `.env`. Cada pregunta gasta unos USD 0.0007.

### 1. Levantar y revisar que esté sano

```bash
docker compose up -d --build --wait
```

```bash
curl -s http://localhost:8000/health
```

Debe decir `"status": "ok"` y `"language_model_configured": true`.

### 2. Preguntar desde el navegador

Abre <http://localhost:8000/docs>, entra a `POST /api/conversation` y pulsa **Try it out**. El cuadro ya trae una pregunta lista; pulsa **Execute**, o cámbiala por otra:

```json
{ "query": "What is the output torque of 762A00-11300000/A?" }
```

Para seguir la conversación, copia el `session_id` de la respuesta y agrégalo a la siguiente pregunta:

```json
{ "session_id": "PEGALO-AQUI", "query": "And how much power does it draw?" }
```

Si responde `404 Conversation not found`, el `session_id` no existe en tu base: usa uno que haya devuelto una respuesta anterior, o quítalo para empezar una conversación nueva.

### 3. O desde la terminal

`jq` ordena la salida; si no lo tienes, cambia `jq` por `python3 -m json.tool`.

Una pregunta, mostrando solo la respuesta y las tools llamadas:

```bash
curl -s -X POST http://localhost:8000/api/conversation -H "Content-Type: application/json" -d '{"query": "What is the output torque of 762A00-11300000/A?"}' | jq '{answer, needs_clarification, tools: [.debug.tool_calls[] | {name, args}]}'
```

Una pregunta y su seguimiento, en una sola línea:

```bash
SID=$(curl -s -X POST http://localhost:8000/api/conversation -H "Content-Type: application/json" -d '{"query": "What torque does the 2A give at 110 V?"}' | jq -r .session_id) && curl -s -X POST http://localhost:8000/api/conversation -H "Content-Type: application/json" -d "{\"session_id\": \"$SID\", \"query\": \"And how much power does it draw?\"}" | jq '{answer, tools: [.debug.tool_calls[] | {name, args}]}'
```

En el seguimiento, la tool debe recibir `762A00-11300000/A` completo, no "2A".

### 4. Preguntas para probar los casos difíciles

Usa cada una en una conversación nueva, sin `session_id`:

| Pregunta | Qué debería pasar |
|---|---|
| `What is the output torque of 762A00-11300000/A?` | 150 Nm en On/Off y 130 Nm en Modulating |
| `Tell me about the 1A` | Muestra 3 opciones o pregunta el voltaje; `needs_clarification: true` |
| `Specs for 761800-11300000/A` | Dice que no existe y sugiere `761B00-11300000/A` |
| `Give me the data of 761A00-11380000/A` | Dice que no está en las tablas, aunque aparece en el summary |
| `What is the torque of 761A00-11330C00/A?` | Dice que la tabla lo lista como N/A y ofrece alternativas |
| `Recommend an On/Off weatherproof actuator at 110 V with at least 500 Nm` | Empieza por `763B00-11300000/A` |
| `I need an explosionproof, 3-phase actuator with at least 400 Nm` | Dice que ninguno cumple y ofrece `763Y30`, aclarando que es de 1 fase |
| `Necesito un actuador modulating de 3 fases con al menos 400 Nm` | Ofrece `763B00-11330C00/A` y avisa que la tabla no indica el modo |
| `I need an actuator with 500 of torque` | Pregunta la unidad |
| `I need 70 ft-lb, On/Off, weatherproof, 110 V` | Empieza por `761B00-11300000/A` |
| `What is the capital of France?` | No responde la pregunta y redirige |
| `And how much power does it draw?` | Pregunta de qué modelo se habla |

### 5. Qué revisar en `debug`

| Campo | Qué debería tener |
|---|---|
| `tool_calls` | Las tools llamadas, con sus argumentos y lo que devolvieron |
| `unverified_numbers` | `[]`: si aparece un número, el agente dijo algo que no salió de las tools |
| `finish_reason` | No debe ser `length`, que significa respuesta cortada |
| `part_numbers_consulted` | Los modelos que el siguiente turno podrá usar |
| `input_tokens`, `output_tokens`, `latency_ms` | Consumo y tiempo de esa pregunta |

### 6. Comprobar que las conversaciones se guardan

Lista las conversaciones:

```bash
curl -s http://localhost:8000/api/sessions | jq
```

Reinicia el backend:

```bash
docker compose restart backend
```

Vuelve a listarlas cuando arranque: deben seguir ahí. Para ver una completa, con productos y debug:

```bash
curl -s http://localhost:8000/api/sessions/PEGALO-AQUI/messages | jq
```

### 7. Comprobar los errores

| Prueba | Comando | Respuesta esperada |
|---|---|---|
| Conversación inexistente | `curl -s http://localhost:8000/api/sessions/00000000-0000-0000-0000-000000000000/messages` | 404 |
| Pregunta vacía | `curl -s -X POST http://localhost:8000/api/conversation -H "Content-Type: application/json" -d '{"query": "   "}'` | 422, sin gastar |
| Base apagada | `docker compose stop db` y luego `curl -s http://localhost:8000/health` | 503 con un mensaje claro |
| Backend que arranca sin base | Con la base apagada, `docker compose restart backend` y luego `docker inspect konecto-backend-1 --format '{{.RestartCount}}'` | El backend sigue arriba, responde 503 y el contador de reinicios no sube |

Después de la última prueba, vuelve a levantar la base con `docker compose start db`. El backend se recupera solo: en `docker compose logs backend` verás `Database not available, will retry` y luego `Loaded`.

### 8. Ver qué pasa por dentro

```bash
docker compose logs -f backend
```

## Android Studio

### Instalación (ya hecha en esta máquina)

Se instaló sin `sudo`, con el `.tar.gz` oficial de <https://developer.android.com/studio> (versión 2026.2.2, 1.5 GB). Antes de descomprimirlo se comparó su SHA-256 con el publicado en esa página. Quedó en `~/android-studio`, y aparece en el menú de aplicaciones como "Android Studio".

Para abrirlo desde la terminal:

```bash
~/android-studio/bin/studio &
```

La primera vez, el asistente pide el tipo de instalación: elige **Standard**. Descarga el SDK en `~/Android/Sdk` y pide aceptar las licencias del SDK, algo que hace cada desarrollador por su cuenta.

### Por qué así

- **El `.tar.gz` y no snap:** `snap install` necesita `sudo` y actualiza Android Studio por su cuenta. El `.tar.gz` se instala en la carpeta personal y la versión no cambia a mitad de la prueba.
- **El emulador va rápido:** el procesador tiene virtualización y el usuario puede usar `/dev/kvm`. Para comprobarlo:

```bash
test -r /dev/kvm -a -w /dev/kvm && echo "KVM disponible"
```

### El emulador

El asistente creó el emulador `Medium_Phone_API_37.0`: Android 17 (API 37), x86_64, con Google Play. Para ver los emuladores que hay:

```bash
~/Android/Sdk/emulator/emulator -list-avds
```

Para arrancarlo sin Android Studio:

```bash
~/Android/Sdk/emulator/emulator -avd Medium_Phone_API_37.0 -no-snapshot-save &
```

Para saber si ya terminó de arrancar (responde `1` cuando está listo):

```bash
~/Android/Sdk/platform-tools/adb shell getprop sys.boot_completed
```

### Comprobar que el emulador llega al backend

Dentro del emulador, `localhost` es el propio emulador, no tu computador. Tu computador se ve como `10.0.2.2`, por eso la app usará `http://10.0.2.2:8000`. Con el backend arriba, esto debe imprimir el JSON de `/health`:

```bash
~/Android/Sdk/platform-tools/adb shell '(printf "GET /health HTTP/1.0\r\n\r\n"; sleep 3) | nc 10.0.2.2 8000'
```

## App Android

Todos desde `android/`. Usan el Java que trae Android Studio; si `java -version` ya muestra 17 o más, puedes omitir `JAVA_HOME=...`. En una carpeta que Android Studio nunca abrió (por ejemplo, un clon nuevo), Gradle no sabe dónde está el SDK: antes, `export ANDROID_HOME=~/Android/Sdk`.

### Compilar y correr los tests

```bash
cd android && JAVA_HOME=~/android-studio/jbr ./gradlew assembleDebug testDebugUnitTest
```

La primera vez descarga Gradle y las dependencias (unos minutos). Los tests no necesitan emulador ni backend.

### Instalar y abrir en el emulador

Con el emulador y el backend arriba:

```bash
cd android && JAVA_HOME=~/android-studio/jbr ./gradlew installDebug
```

```bash
~/Android/Sdk/platform-tools/adb shell am start -n com.series76.assistant/.MainActivity
```

En Android 17 la app pide primero el permiso de red local: hay que tocar **Allow**. Sin él no puede llegar a `10.0.2.2`.

También se puede abrir la carpeta `android/` en Android Studio y pulsar ▶ Run.

### Usar un celular

Por cable, sin cambiar la URL ni pedir el permiso: `adb reverse` hace que `localhost` del celular sea tu computador.

```bash
~/Android/Sdk/platform-tools/adb reverse tcp:8000 tcp:8000
```

```bash
cd android && JAVA_HOME=~/android-studio/jbr ./gradlew installDebug -PbackendUrl=http://localhost:8000
```

Por Wi-Fi, con la IP de tu computador en la red local (por ejemplo, `192.168.1.50`):

```bash
cd android && JAVA_HOME=~/android-studio/jbr ./gradlew installDebug -PbackendUrl=http://192.168.1.50:8000
```

### Preguntas para probar el chat

Cada una prueba una vista distinta. Gastan de la clave (unos USD 0.0007 cada una con Haiku).

| Pregunta | Qué debe verse |
|---|---|
| `What is the torque of 762A00-11300000/A?` | Una tarjeta con On/Off y Modulating, 60 y 50 Hz |
| Luego `And how much power does it draw?` | Responde 40 W sin repetir el part number |
| `What about the 1A?` | Tres opciones para tocar; una dice que no tiene valores |
| `I need at least 500 Nm, On/Off, 110 V` | Tabla comparativa abierta en On/Off y 60 Hz |
| `I need 3000 Nm modulating at 24 V` | "Ninguno cumple", tabla de alternativas y diferencias en rojo |
| `Which 3 phase actuators give at least 400 Nm modulating?` | Tabla abierta en Modulating, valores con `*` |
| `761A00-11330C00/A` | Tarjeta N/A sin valores y modelos con datos para mirar |

### Abrir la pantalla de debug

1. En la lista, **mantener "New conversation" 3 segundos** y confirmar **Enter**. Aparece "Debug mode" en rojo arriba.
2. En un chat, **pulsación larga sobre el texto de una respuesta** (la burbuja gris, no la tarjeta del producto).
3. Para apagarlo: mantener otra vez el botón y elegir **Leave**.

Desde la terminal, con el emulador (las coordenadas son las del emulador `Medium_Phone`):

```bash
~/Android/Sdk/platform-tools/adb shell input swipe 795 2221 795 2221 3500
```

Para ver si el modo quedó guardado:

```bash
~/Android/Sdk/platform-tools/adb shell run-as com.series76.assistant cat shared_prefs/developer.xml
```

### Probar los estados de error

| Prueba | Cómo | Qué debe verse |
|---|---|---|
| Backend caído al abrir | `docker compose stop backend` y abrir la app | "Can't reach the server" y **Retry** |
| Backend caído con la lista cargada | Abrir una conversación, `docker compose stop backend` y volver | La lista sigue, con el aviso arriba |
| Permiso denegado | Tocar **Don't allow** en el diálogo | Pantalla que explica el permiso, con **Allow** y **Open settings** |
| Pregunta con el backend caído | `docker compose stop backend`, enviar, `docker compose start backend` y **Retry** | "Not sent" y luego la respuesta, sin duplicar la pregunta |
| Volver a pedir el permiso | El comando de abajo y abrir la app de nuevo | Aparece otra vez el diálogo |

```bash
~/Android/Sdk/platform-tools/adb shell pm revoke com.series76.assistant android.permission.ACCESS_LOCAL_NETWORK
```

## Base de datos

Estos comandos van desde la raíz del repo.

### Levantar la base

```bash
docker compose up -d --wait db
```

### Detener la base

Los datos se conservan.

```bash
docker compose down
```

### Abrir una consola SQL

Sales con `\q`.

```bash
docker compose exec db psql -U konecto -d series76
```

### Borrar la base por completo

Elimina también el volumen con todos los datos. Después hay que levantarla y [cargar los datos](#cargar-los-datos) otra vez.

```bash
docker compose down -v
```

## Ingesta

Estos comandos van desde `backend/`.

### Cargar los datos

Carga `processed/actuators.json` en PostgreSQL y reemplaza lo que había. Necesita la base levantada; no necesita claves ni Docling.

```bash
uv run python ingest.py
```

### Reconstruir el resultado

Usa `raw/docling_tables.json`, `spec.py` y `corrections.json` para crear `processed/actuators.json`. Si encuentra un problema, lo muestra y no escribe nada. No carga en la base.

```bash
uv run python ingest.py --build
```

### Extraer del PDF

Lee el PDF con Docling, sobrescribe `raw/docling_tables.json` y reconstruye el resultado. No carga en la base. La primera vez descarga varios GB.

```bash
uv run --group extract python ingest.py --extract
```

### Auditar

Compara lo que leyó Gemini con `processed/actuators.json` y guarda las diferencias en `audit/report.json`. No cambia los datos.

```bash
uv run --group extract python ingest.py --audit
```

Reutiliza las páginas ya leídas en `audit/pages/`, que están en el repo, así que no necesita clave para el modelo ya usado. Para que Gemini lea otra vez, borra los archivos de ese modelo o cambia `AUDIT_MODEL` en `.env`; en ese caso sí necesita `GOOGLE_API_KEY` en `.env`.

## Probar las tools a mano

Estos comandos van desde `backend/` y necesitan la base levantada con los datos cargados. Llaman a las mismas tools que usará el agente, sin LLM, así que no gastan presupuesto.

Buscar un modelo, por part number o alias:

```bash
uv run python try_tools.py specs 762A00-11300000/A
```

Elegir entre varios modelos con el mismo alias:

```bash
uv run python try_tools.py specs 1A --voltage 110
```

Buscar por requisitos:

```bash
uv run python try_tools.py recommend min_torque=500 torque_unit=nm service=on_off voltage_v=110
```

Ver qué opciones existen:

```bash
uv run python try_tools.py options
```

Agrega `--full` al final para ver el resultado completo, tal como lo recibe el agente.

| Requisito | Valores |
|---|---|
| `min_torque` y `torque_unit` | Un número, y `nm`, `in_lbs`, `ft_lbs` o `kgf_m` |
| `service` | `on_off` o `modulating` |
| `enclosure` | `weatherproof` o `explosionproof` |
| `voltage_v` | 24, 110 o 220 |
| `phases` | 1 o 3 |
| `current_type` | `AC` o `DC` |
| `frequency_hz` | 50 o 60 |
| `max_speed_sec` | Segundos para girar 90° |
| `min_duty_cycle_pct` | Porcentaje |
| `min_cycles_per_hour`, `min_starts_per_hour` | Un número |
| `max_fla_a`, `max_lra_a` | Amperios |
| `max_motor_power_w` | Vatios |
| `certification` | `CSA`, `CE` o `UKCA` |
| `limit` | Cuántos modelos mostrar, hasta 20 |

## Tests

Estos comandos van desde `backend/`.

### Correr los tests

Los de carga y conexión necesitan la base levantada.

```bash
uv run pytest
```

### Correr solo los tests de las tools

Prueban las consultas y los edge cases sin LLM, así que no gastan presupuesto. Necesitan la base levantada.

```bash
uv run pytest tests/test_catalog.py
```

### Correr solo los tests de los datos

No necesitan la base.

```bash
uv run pytest tests/test_build.py
```

## Si algo falla

| Mensaje | Qué significa | Qué hacer |
|---|---|---|
| `The language model is not configured` | Falta `OPENROUTER_API_KEY` | Ponerla en `.env` y volver a levantar el backend |
| `The language model could not answer` | OpenRouter falló, por ejemplo por falta de saldo | Revisar la clave en OpenRouter o reintentar |
| `Cannot connect to the database` | La base no está levantada | [Levantar la base](#levantar-la-base) |
| `can't open file ... ingest.py` | No estás en `backend/` | `cd backend` primero |
| `--extract and --audit need the optional dependencies` | Falta `--group extract` | Usar el comando que muestra el mensaje |
| `N problems, nothing was written` | Un valor o una regla no pasó la validación | Revisar esa celda en el PDF y, si fue un error de lectura, seguir [guia-de-correcciones.md](guia-de-correcciones.md) |
| `correction expects ...` | Docling leyó algo distinto a lo que espera una corrección | Mirar la celda en el PDF y actualizar la corrección |
| `There is no saved reading` | Ese modelo no se ha usado en la auditoría y falta la clave | Agregar `GOOGLE_API_KEY` a `.env` |
| `no longer available` | Google retiró ese modelo | Cambiar `AUDIT_MODEL` en `.env` |
| `The model did not answer (503)` | El modelo está saturado | Reintentar más tarde o cambiar `AUDIT_MODEL` |
