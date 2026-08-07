"""Evaluation feature: DB-free RAG evaluation harness (metrics, datasets, runner).

Public surface. External code (other features, routes, tests) imports the
operations and types it needs from `app.features.evaluation` — never from a
deeper module.

Internal rule: modules inside this feature MUST NOT import through this root
(`from app.features.evaluation import X`); they import each other by their full
submodule path. Importing the root while it is still initializing raises
ImportError.
"""

from __future__ import annotations

from .fixtures import confluence_fixtures_dir, datasets_dir, load_corpus_loader
from .run_baseline import load_dataset
from .runner import RankFn, evaluate
from .schemas import EvalCase, EvalDataset, EvalReport, EvalResult

__all__ = [
    "EvalCase",
    "EvalDataset",
    "EvalReport",
    "EvalResult",
    "RankFn",
    "confluence_fixtures_dir",
    "datasets_dir",
    "evaluate",
    "load_corpus_loader",
    "load_dataset",
]
