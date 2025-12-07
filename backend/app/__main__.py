"""Main entry point for the FastAPI application."""

import argparse

import uvicorn

from app import create_app


def main() -> None:
    """Run the FastAPI application using Uvicorn."""
    parser = argparse.ArgumentParser(
        description="Run the Minecraft RCON Server API FastAPI application.",
    )
    parser.add_argument(
        "--env-file",
        type=str,
        default=".env",
        help="Path to the environment configuration file.",
    )
    args = parser.parse_args()

    app = create_app(args.env_file)
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
