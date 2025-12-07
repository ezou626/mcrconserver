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
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to run the FastAPI application on.",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host to run the FastAPI application on.",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker processes to run.",
    )
    args = parser.parse_args()

    app = create_app(args.env_file)
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=args.workers,
    )


if __name__ == "__main__":
    main()
