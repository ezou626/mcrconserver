# Minecraft RCON Server

Web admin UI for managing MC servers

HTTPS should be provided by a reverse proxy like Nginx
To use the UI only (not the API), SSH tunnelling is also ok.

## Run

```bash
uv run fastapi run main:app --host 0.0.0.0 --port 8000 # or whatever port
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
