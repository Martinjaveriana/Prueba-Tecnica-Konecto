# Series 76 Technical Assistant

A technical assistant for choosing Series 76 electric actuators: a Python backend with an AI agent, and a native Android app.

## Project status

| Part | Status |
|---|---|
| Data ingestion from the PDF | Done |
| Agent tools, tested without an LLM | Done |
| Agent, REST API and conversation history | Not built yet |
| Backend `Dockerfile` | Not built yet |
| Android app | Not built yet |

## Quick start

**You need:** [Docker](https://docs.docker.com/get-docker/) with Docker Compose, and [uv](https://docs.astral.sh/uv/getting-started/installation/), which installs the right Python version by itself. No API key is needed for anything in this section.

From the root of the repository, create your configuration:

```bash
cp .env.example .env
```

Start the database:

```bash
docker compose up -d --wait db
```

Move to the backend folder. **All the commands from here on run from `backend/`:**

```bash
cd backend
```

Load the actuator data:

```bash
uv run python ingest.py
```

You should see:

```
Loaded: actuators=68, service_ratings=111, electrical_ratings=118
```

Run the tests:

```bash
uv run pytest
```

Try the tools the agent will use. This calls no LLM and spends nothing:

```bash
uv run python try_tools.py recommend min_torque=500 torque_unit=nm service=on_off voltage_v=110 enclosure=weatherproof
```

The port on your machine is `5433`, so it does not clash with a local PostgreSQL. To use another one, change `POSTGRES_PORT` and `DATABASE_URL` in `.env`.

## Data ingestion

### You only need one command

The tables in `series_76_electric_data.pdf` are images, so reading them takes OCR, which weighs several GB. Its reviewed result is versioned in this repository. **The Quick start already loaded it, so you do not need to read the PDF again to run the project.** The other commands exist so you can verify where the data comes from.

| What you want | Command, from `backend/` | Needs | Changes |
|---|---|---|---|
| **Load the data into the database** | `uv run python ingest.py` | Running database | Database |
| Rebuild the data from the saved OCR output | `uv run python ingest.py --build` | Nothing | `processed/` |
| Read the PDF again, from scratch | `uv run --group extract python ingest.py --extract` | About 6 GB of packages and up to 5 GB of models | `raw/`, `processed/` |
| Compare with the saved audit readings | `uv run --group extract python ingest.py --audit` | About 6 GB of packages | `audit/` |
| Run the audit with a different model | Set `AUDIT_MODEL` in `.env`, then the same `--audit` command | `GOOGLE_API_KEY` in `.env` | `audit/` |

`--extract` and `--build` do not load the database. Run `uv run python ingest.py` afterwards. Reading the PDF again should leave the data unchanged, which you can confirm with `git status`.

### How the data flows

```
series_76_electric_data.pdf
        │  --extract: Docling reads the table images
        ▼
data/raw/docling_tables.json       what Docling read, untouched
        │  ingestion/spec.py       declared structure of the 7 tables
        │  data/corrections.json   reviewed fixes for misread values
        │  ingestion/build.py      cleans and validates (--build)
        ▼
data/processed/actuators.json      THE RESULT: 68 models
        │  no options: ingestion/load.py
        ▼
PostgreSQL                         what the agent's tools query
```

Separately, as a check that never changes the data, `--audit` has a vision model read the PDF on its own. It compares that reading with `actuators.json` and writes the differences to `data/audit/report.json`.

### Where the data lives

All paths are under `backend/data/`.

| Path | Contents |
|---|---|
| `raw/docling_tables.json` | What Docling read, with its mistakes |
| `corrections.json` | Each misread value, its real value and where in the PDF it was checked |
| `processed/actuators.json` | The reviewed data the database is loaded from |
| `audit/pages/` | What the vision model read, one file per page |
| `audit/report.json` | Differences between that reading and the reviewed data |

### How the numbers were verified

- **Validation:** a rebuild writes nothing if a value is malformed, a row is missing, in-lbs and Nm disagree by more than 5%, or LRA is below FLA. On the first read, this flagged 6 misread speeds, such as `£3` for 33.
- **Review:** every row was compared by eye with the PDF images.
- **Repeatability:** reading the PDF twice on the same machine produced identical files.
- **Independent audit:** `gemini-3.5-flash` read all 68 rows, and 869 cells were compared. It found one difference, the motor power of `764Y30-11300000/A` (reviewed: 180 W, model: 90 W). The PDF image confirms 180 W, so the data did not change.

This lowers the risk of a wrong number, but cannot rule it out entirely.

## Trying the tools

From `backend/`, with the database running and the data loaded. Add `--full` at the end to see the complete result the agent receives.

Look up a model by part number:

```bash
uv run python try_tools.py specs 762A00-11300000/A
```

Look up a short alias that covers several models:

```bash
uv run python try_tools.py specs 1A
```

Try a mistyped part number:

```bash
uv run python try_tools.py specs 761800-11300000/A
```

Try requirements no model meets:

```bash
uv run python try_tools.py recommend enclosure=explosionproof phases=3 min_torque=400 torque_unit=nm
```

List what exists:

```bash
uv run python try_tools.py options
```

## Design and trade-offs

| Decision | Why | Trade-off |
|---|---|---|
| SQL tables, not RAG | "At least 500 Nm" needs an exact comparison, and similarity search can return a close but wrong row | Questions must map to fixed filters |
| Fixed tools; the LLM never writes SQL | A wrong condition would produce a wrong number that looks right | Less flexible |
| Docling for OCR, reviewed data versioned in the repository | Found all 7 tables with no API key. Running the project needs no OCR download | Reading the PDF is a separate, heavy step |
| Table structure declared in code | Merged motor power cells cannot be read reliably, and a mismatch stops the build | Does not work for a PDF with another format |
| Rules report; they never correct | A rule can tell that something is wrong, not which cell is | Each misread value needs a person to check it |
| Torque compared in the unit requested | The PDF rounds each column: 880 in-lbs is listed as 100 Nm, but 100 Nm is about 885 in-lbs. Converting would wrongly reject that model | Only units missing from the PDF are converted |
| 3-phase ratings stored as "unspecified" | The table gives one torque and does not say which service it applies to | Results need a visible warning |
| Tightest fit first; alternatives only if nothing qualifies | Asked-for results first, and much larger actuators are usually unnecessary | The order of alternatives is a reasonable rule, not an engineering truth |

Every decision, the alternatives rejected and the OCR tools compared are in [docs/decisiones-de-diseno.md](docs/decisiones-de-diseno.md), in Spanish. So are the [command guide](docs/guia-de-comandos.md) and the [guide to correcting the data](docs/guia-de-correcciones.md).

## Troubleshooting

| What you see | What it means | What to do |
|---|---|---|
| `Cannot connect to the database` | The database is not running | From the root: `docker compose up -d --wait db` |
| `can't open file ... ingest.py` | You are not in `backend/` | `cd backend` first |
| `No module named 'pydantic_settings'` | You ran plain `python` instead of `uv run` | Start the command with `uv run python` |
| `--extract and --audit need the optional dependencies` | You left out `--group extract` | Use the command it prints |
| `port is already allocated` | Port 5433 is in use | Change `POSTGRES_PORT` and `DATABASE_URL` in `.env` |
| `N problems, nothing was written` | A value failed validation, so the previous data was kept | See the [guide to correcting the data](docs/guia-de-correcciones.md) |
| `There is no saved reading` | That audit model has not been run | Set `GOOGLE_API_KEY` in `.env` |

## Repository layout

| Path | Contents |
|---|---|
| `backend/ingest.py` | The ingestion script |
| `backend/ingestion/` | Its stages: structure, extract, build, load, audit |
| `backend/data/` | Raw, corrected, processed and audit data |
| `backend/app/` | Configuration, database schema, queries and agent tools |
| `backend/tests/` | Tests |
| `docs/` | The assessment, source PDFs and project guides |
| `.claude/` | AI assistant configuration, together with `CLAUDE.md` |
