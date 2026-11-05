# Series 76 Technical Assistant

Technical assistant for choosing Series 76 electric actuators: a Python backend with an AI agent and a native Android app.

> Work in progress. Only the project foundation exists so far.

## Repository layout

| Path | Contents |
|---|---|
| `backend/` | Python backend |
| `android/` | Kotlin + Jetpack Compose app (not created yet) |
| `docs/` | Assessment and source PDFs |
| `docker-compose.yml` | Local services |

## Requirements

- Docker with Docker Compose
- [uv](https://docs.astral.sh/uv/) to run the backend tests outside Docker

## Getting started

Create your local configuration:

```bash
cp .env.example .env
```

Start the database:

```bash
docker compose up -d --wait db
```

Load the actuator data into the database:

```bash
cd backend && uv run python ingest.py
```

Run the tests:

```bash
cd backend && uv run pytest
```

## Data ingestion

The tables in `series_76_electric_data.pdf` are images, so the data comes through OCR. The reviewed result is versioned in the repository, which means loading it needs no API key and no OCR libraries.

| Command, from `backend/` | What it does | Needs |
|---|---|---|
| `uv run python ingest.py` | Loads `data/processed/actuators.json` into PostgreSQL. Safe to run repeatedly | Database |
| `uv run python ingest.py --build` | Rebuilds the reviewed data from `data/raw/docling_tables.json` | Nothing |
| `uv run --group extract python ingest.py --extract` | Reads the PDF again with Docling, then rebuilds | Several GB of downloads |
| `uv run --group extract python ingest.py --audit` | Compares the data with an independent reading by a vision model | `GOOGLE_API_KEY` |

Where the data lives:

| Path | Contents |
|---|---|
| `backend/data/raw/docling_tables.json` | What Docling read, untouched |
| `backend/data/corrections.json` | Each manual correction, with what was read and why it changed |
| `backend/data/processed/actuators.json` | The reviewed data the database is loaded from |
| `backend/data/audit/report.json` | Differences found by the audit, once it has run |

A rebuild writes nothing if any value is invalid or a validation rule fails, and `git diff` shows any change to the reviewed data.

The audit with `gemini-3.5-flash` read all 68 rows and compared 869 cells against the reviewed data. It found one difference, the motor power of `764Y30-11300000/A` (reviewed: 180 W, model: 90 W). The PDF image confirms 180 W, so the reviewed data did not change. The audit is a second opinion and never changes the data.
