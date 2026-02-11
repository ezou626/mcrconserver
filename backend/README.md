# Minecraft RCON Server

Web admin UI for managing MC servers

HTTPS should be provided by a reverse proxy like Nginx or Apache mod_proxy,
or you can modify the code to provide the SSL certs to uvicorn
To use the UI only (not the API), SSH tunnelling is also ok.

## Setup

Install dependencies using [uv](https://docs.astral.sh/uv/):

```bash
uv sync
```

This installs the `backend` package (from `src/backend/`) in editable mode along with all dependencies.

## Run

### Development (with auto-reload)

```bash
# With fastapi CLI
export ENV_FILE="/path/to/env/file"
uv run fastapi dev main.py --host X.X.X.X --port 8000

# Alternative: using uvicorn directly
export ENV_FILE="/path/to/env/file"
uv run uvicorn main:app --reload --host X.X.X.X --port 8000

# Using the module directly with environment file
uv run python -m backend.app --env-file .env --reload --host X.X.X.X --port 8000
```

### Production

```bash
# With fastapi CLI (supports multiple workers)
export ENV_FILE="/path/to/env/file"
uv run fastapi run main.py --host X.X.X.X --port 8000 --workers 4

# Alternative: using uvicorn directly
export ENV_FILE="/path/to/env/file"
uv run uvicorn main:app --host X.X.X.X --port 8000 --workers 4

# Using the module directly with environment file
uv run python -m backend.app --env-file .env --host X.X.X.X --port 8000
```

## Test

This project uses the pytest framework. Tests live under `tests/`.

```bash
uv run pytest -v
```

Notes:

- No external services are required for these tests. Future integration tests can target the RCON client when a server is available.

## Benchmarks

Benchmarks live under `benchmarks/` and are run as a standalone module.
They require a running Minecraft server JAR and the `MINECRAFT_SERVER_PATH` environment variable.

```bash
uv run python -m benchmarks --env-file .env --results-dir ./benchmark_results
```

## Project Structure

```
backend/
├── main.py                  # FastAPI entry point for CLI usage
├── pyproject.toml
├── src/
│   └── backend/             # Installable backend package
│       ├── app/             # FastAPI application
│       │   ├── auth/        # Authentication routes & logic
│       │   ├── command_router/
│       │   ├── common/      # Shared models (User, Role)
│       │   └── rconclient/  # Async RCON client & worker pool
│       └── config/          # Configuration loading from env
├── benchmarks/              # Performance benchmarks (standalone)
└── tests/                   # pytest test suite
```
