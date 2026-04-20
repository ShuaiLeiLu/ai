"""Backward-compatible alias.

All module registration is managed by ``module_registry.py`` and assembled
by ``router_factory.py``.  This file re-exports the factory-built router so
that any legacy import of ``api_router`` still works.
"""
from __future__ import annotations

from app.api.v1.router_factory import create_api_v1_router

api_router = create_api_v1_router()
