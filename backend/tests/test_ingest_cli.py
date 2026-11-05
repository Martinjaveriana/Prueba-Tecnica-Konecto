"""What someone sees when ingest.py is run the wrong way: a next step, not a traceback."""

import sys

import ingest
from app.config import settings


def run(monkeypatch, *arguments: str) -> int:
    monkeypatch.setattr(sys, "argv", ["ingest.py", *arguments])
    return ingest.main()


def test_loading_without_the_database_says_how_to_start_it(monkeypatch, capsys):
    monkeypatch.setattr(settings, "database_url", "postgresql://nobody@127.0.0.1:1/none")
    assert run(monkeypatch) == 2
    assert "docker compose up -d --wait db" in capsys.readouterr().out


def test_extracting_without_docling_says_what_to_install(monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "docling", None)
    monkeypatch.delitem(sys.modules, "docling.document_converter", raising=False)
    monkeypatch.delitem(sys.modules, "ingestion.extract", raising=False)
    assert run(monkeypatch, "--extract") == 2
    assert "uv run --group extract python ingest.py --extract" in capsys.readouterr().out


def test_building_needs_no_database_or_optional_dependency(monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "docling", None)
    monkeypatch.setattr(settings, "database_url", "postgresql://nobody@127.0.0.1:1/none")
    assert run(monkeypatch, "--build") == 0
    assert "68 actuators" in capsys.readouterr().out
