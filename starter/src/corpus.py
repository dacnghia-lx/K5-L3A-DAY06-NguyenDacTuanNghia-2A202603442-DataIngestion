"""Corpus configuration shared by every script: sources, versions, paths."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .ingestion import load_pydoc_topics
from .models import DocumentPage

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
BENCHMARK_PATH = REPO_ROOT / "benchmark" / "questions.json"
RESULTS_DIR = REPO_ROOT / "results"

# (python_version, path relative to repo root). Raw files are byte-for-byte
# copies of CPython's Lib/pydoc_data/topics.py (see data/manifest.json).
SOURCES = [
    ("3.11", "data/raw/pydoc_topics_py3.11.py"),
    ("3.13", "data/raw/pydoc_topics_py3.13.py"),
]


def load_corpus(errors: list[dict[str, Any]] | None = None) -> list[DocumentPage]:
    pages: list[DocumentPage] = []
    for version, rel in SOURCES:
        path = REPO_ROOT / rel
        if not path.exists():
            raise FileNotFoundError(f"Missing corpus file {rel}; see data/manifest.json")
        pages.extend(load_pydoc_topics(path, version, rel, errors))
    return pages
