"""Main entry point for the benchmarking application."""

import argparse

from backend.app.rconclient import RCONWorkerPoolConfig
from backend.config import configure_logging, get_env_str, load_config_from_env

from .config import BenchmarkConfig
from .rconclient import worker_benchmark
from .setup import setup_benchmark


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
    parser.add_argument(
        "--results-dir",
        type=str,
        default="./benchmark_results",
        help="Directory to store benchmark results.",
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

    benchmark_config = BenchmarkConfig(
        minecraft_server_jar_path=get_env_str("MINECRAFT_SERVER_PATH", ""),
        rcon_port=config.rcon_port,
        rcon_password=config.rcon_password,
        results_directory=args.results_dir,
    )

    configure_logging(config)

    with setup_benchmark(benchmark_config):
        worker_benchmark(benchmark_config, worker_config)


if __name__ == "__main__":
    main()
