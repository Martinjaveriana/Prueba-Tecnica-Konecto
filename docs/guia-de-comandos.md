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

Para auditar, pon tu clave en `GOOGLE_API_KEY` dentro de `.env`.

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

Gemini lee el PDF y `audit/report.json` guarda las diferencias con `processed/actuators.json`. No cambia los datos. Necesita `GOOGLE_API_KEY` en `.env`.

```bash
uv run --group extract python ingest.py --audit
```

Reutiliza las páginas ya leídas en `audit/pages/`. Para que Gemini lea otra vez, borra los archivos de ese modelo o cambia `AUDIT_MODEL` en `.env`.

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
| `Connection refused` | La base no está levantada | [Levantar la base](#levantar-la-base) |
| `N problems, nothing was written` | Un valor o una regla no pasó la validación | Revisar esa celda en el PDF y, si fue un error de lectura, seguir [guia-de-correcciones.md](guia-de-correcciones.md) |
| `correction expects ...` | Docling leyó algo distinto a lo que espera una corrección | Mirar la celda en el PDF y actualizar la corrección |
| `Set GOOGLE_API_KEY in .env` | Falta la clave | Agregarla a `.env` |
| `no longer available` | Google retiró ese modelo | Cambiar `AUDIT_MODEL` en `.env` |
| `The model did not answer (503)` | El modelo está saturado | Reintentar más tarde o cambiar `AUDIT_MODEL` |
