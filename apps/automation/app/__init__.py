"""omniboost-rag automation service.

Single source of truth for the service version: `pyproject.toml` reads this via
Hatchling's dynamic version, and `app.main` stamps it onto the FastAPI app (and
thus the OpenAPI schema). Bump it here and both follow.
"""

__version__ = "0.2.0"
