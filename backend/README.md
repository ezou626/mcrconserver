# Minecraft RCON Server

Web admin UI for managing MC servers

HTTPS should be provided by a reverse proxy like Nginx
To use the UI only (not the API), SSH tunnelling is also ok.

## Run

### Development (with auto-reload)

```bash
# With fastapi CLI if you want more workers
export ENV_FILE="/path/to/env/file"
uv run fastapi dev main.py --host X.X.X.X --port 8000 --workers 4

# Alternative: using uvicorn directly
export ENV_FILE="/path/to/env/file"
uv run uvicorn main:app --reload --host X.X.X.X --port 8000 --workers 4

# Using the module directly with environment file
uv run python -m app --env-file .env --reload --host X.X.X.X --port 8000
```

### Production

```bash

# With fastapi CLI if you want more workers
export ENV_FILE="/path/to/env/file"
uv run fastapi run main.py --host X.X.X.X --port 8000 --workers 4

# Alternative: using uvicorn directly
uv run uvicorn main:app --host X.X.X.X --port 8000 --workers 4

# Using the module directly with environment file
uv run python -m app --env-file .env --host X.X.X.X --port 8000
```

## Test

This project uses the built-in unittest framework. Tests live under `tests/` and automatically isolate a temporary SQLite database per test.

Using uv (recommended):

```bash
uv run -m unittest -v
```

Notes:

- The test base (`tests/test_base.py`) sets the auth database to a temporary file, initializes tables, and seeds a default owner account without interactive prompts.
- No external services are required for these tests. Future integration tests can target the RCON client when a server is available.
