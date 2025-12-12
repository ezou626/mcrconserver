"""Main entry point for the benchmarking application."""

import argparse

from backend.app.rconclient import RCONWorkerPoolConfig
from backend.benchmarks.setup import setup_benchmark
from backend.config import configure_logging, load_config_from_env

from .rconclient import worker_benchmark


def main() -> None:
    """Run the benchmarks."""
    parser = argparse.ArgumentParser(
        description="Run the benchmarks for the RCON server.",
    )
    parser.add_argument(
        "--env-file",
        type=str,
        default=".env",
        help="Path to the environment configuration file.",
    )
    args = parser.parse_args()

    config = load_config_from_env(args.env_file)

    worker_config = RCONWorkerPoolConfig(
        password=config.rcon_password,
        port=config.rcon_port,
        socket_timeout=config.rcon_socket_timeout,
        worker_count=config.worker_count,
        reconnect_pause=config.reconnect_pause,
        grace_period=config.shutdown_grace_period,
        await_shutdown_period=config.shutdown_await_period,
    )

    configure_logging(config)

    with setup_benchmark(config.benchmark_config):
        worker_benchmark(config.benchmark_config, worker_config)


if __name__ == "__main__":
    main()
