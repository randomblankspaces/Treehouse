"""Optional offline product API; import does not require the API extra."""

from .web import create_app

__all__ = ["create_app"]
