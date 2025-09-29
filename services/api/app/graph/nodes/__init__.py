"""Lazy re-exports for graph nodes.

Importing `app.graph.nodes.planner` pulls in heavy optional dependencies. Tests
and callers often rely on `from app.graph.nodes import planner`, so we expose a
lightweight shim that loads modules on demand while keeping type-checkers happy.
"""

from importlib import import_module
from typing import TYPE_CHECKING, Any

__all__ = (
    "answer_gen",
    "critic",
    "health",
    "memory",
    "places",
    "planner",
    "risk_ml",
    "scrub",
    "supervisor",
)


if TYPE_CHECKING:  # pragma: no cover - only for static analysis
    from . import (
        answer_gen,
        critic,
        health,
        memory,
        places,
        planner,
        risk_ml,
        scrub,
        supervisor,
    )


def __getattr__(name: str) -> Any:  # pragma: no cover - thin shim
    if name in __all__:
        module = import_module(f".{name}", __name__)
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:  # pragma: no cover - convenience for REPL/tests
    return sorted(set(__all__) | set(globals().keys()))
