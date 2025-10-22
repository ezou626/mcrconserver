## Backend

### Run tests

This project uses the built-in unittest framework. Tests live under `tests/` and automatically isolate a temporary SQLite database per test.

Using uv (recommended):

```
uv run -q python -m unittest -v
```

Using Python directly:

```
python -m unittest -v
```

Notes:

- The test base (`tests/test_base.py`) sets the auth database to a temporary file, initializes tables, and seeds a default owner account without interactive prompts.
- No external services are required for these tests. Future integration tests can target the RCON client when a server is available.
