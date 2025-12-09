"""Pytest configuration file for setting up test environment."""

import sys
from pathlib import Path

# Add the backend directory to Python path so tests can import from app
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))
