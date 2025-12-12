"""Benchmark suite for RCON worker pool and queueing.

This script validates the benefit of having a worker pool versus a single worker,
batch submission over sequential command execution, and characterizes the shutdown
speed of the worker pool with a large number of queued commands.
"""

import asyncio
import logging
import timeit
from pathlib import Path
from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
import pandas as pd

from backend.app.rconclient import (
    RCONCommand,
    RCONWorkerPool,
    RCONWorkerPoolConfig,
)

if TYPE_CHECKING:
    from backend.benchmarks.config import BenchmarkConfig

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


async def pool_versus_single_worker_one_iteration(
    config: BenchmarkConfig,
    rcon_config: RCONWorkerPoolConfig,
) -> tuple[float, float]:
    """Benchmark the performance of various worker pools versus a single worker."""
    num_commands = 1000

    def command_factory() -> RCONCommand:
        return RCONCommand(command="status", user=None)

    print("Creating single worker pool")
    rcon_config.worker_count = 1
    single_pool = RCONWorkerPool(rcon_config)
    print("Connected to RCON server")

    commands = [command_factory() for _ in range(num_commands)]
    await asyncio.gather(
        *[single_pool.queue_command(command) for command in commands],
    )
    print("done queueing commands")
    start_time = timeit.default_timer()
    await asyncio.gather(*[command.completion.wait() for command in commands])
    single_worker_time = timeit.default_timer() - start_time

    # Properly shut down the single worker pool
    await single_pool.shutdown()

    rcon_config.worker_count = 4
    multi_pool = RCONWorkerPool(rcon_config)

    commands = [command_factory() for _ in range(num_commands)]
    await asyncio.gather(
        *[multi_pool.queue_command(command) for command in commands],
    )
    start_time = timeit.default_timer()
    await asyncio.gather(*[command.completion.wait() for command in commands])
    multi_worker_time = timeit.default_timer() - start_time

    # Properly shut down the multi worker pool
    await multi_pool.shutdown()

    return single_worker_time, multi_worker_time


def worker_benchmark(
    config: BenchmarkConfig,
    rcon_config: RCONWorkerPoolConfig,
) -> None:
    """Run the benchmark suite for the RCON worker pool and save the results."""
    results = []

    for _ in range(10):
        print("Running benchmark iteration...")
        single_worker_time, multi_worker_time = asyncio.run(
            pool_versus_single_worker_one_iteration(config, rcon_config),
        )
        results.append((single_worker_time, multi_worker_time))

    df = pd.DataFrame(results, columns=["single_worker_time", "multi_worker_time"])

    plt.figure(figsize=(10, 6))
    plt.plot(df["single_worker_time"], marker="o", label="Single Worker")
    plt.plot(df["multi_worker_time"], marker="o", label="Multi Worker")
    plt.xlabel("Worker Count")
    plt.ylabel("Time (s)")
    plt.title("RCON Worker Pool Performance")
    plt.legend()
    plt.grid(True)  # noqa: FBT003
    plt.savefig(Path(config.results_directory) / "rcon_worker_pool_performance.png")
