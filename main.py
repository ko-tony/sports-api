"""Compatibility entrypoint for local and Cloud Run deployments."""

from app.main import app

__all__ = ["app"]
