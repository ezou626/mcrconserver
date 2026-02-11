"""Main FastAPI app instance for CLI usage."""

from backend.app import create_app

# Create app instance for FastAPI CLI
app = create_app()
