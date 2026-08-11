import sys

from app.features.rag_agent.server.router import (
    get_answer_service_dep,
    get_settings_dep,
    get_writer_db,
    router,
)

# `router` above is the `APIRouter` instance, which shadows this package's own `router`
# submodule attribute (importing `name` from `pkg.submodule` where `name == submodule`'s own
# attribute overwrites `pkg`'s reference to the submodule itself — a standard Python footgun).
# `sys.modules` recovers the actual module regardless of import order, since it isn't
# subject to that attribute-shadowing; tests need it to monkeypatch `router.py`'s
# module-global `log` (structlog's `cache_logger_on_first_use` makes `capture_logs()`
# unreliable once other tests have already warmed the real logger).
chat_router_module = sys.modules[f"{__name__}.router"]

__all__ = [
    "router",
    "get_settings_dep",
    "get_answer_service_dep",
    "get_writer_db",
    "chat_router_module",
]
