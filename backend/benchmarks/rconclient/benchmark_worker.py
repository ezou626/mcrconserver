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
import numpy as np

from backend.rconclient import (
    RCONCommand,
    RCONWorkerPool,
    RCONWorkerPoolConfig,
)

if TYPE_CHECKING:
    from backend.benchmarks.config import BenchmarkConfig

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

NUM_COMMANDS = 100
NUM_SAMPLES = 10
CONFIDENCE_Z = 1.96  # 95 % confidence


def _make_config(
    base: RCONWorkerPoolConfig,
    worker_count: int,
) -> RCONWorkerPoolConfig:
    """Create a new RCONWorkerPoolConfig with a different worker count.

    :param base: The base configuration to copy settings from
    :param worker_count: The desired number of workers
    :return: A fresh config with the given worker count
    """
    return RCONWorkerPoolConfig(
        password=base.password,
        port=base.port,
        socket_timeout=base.socket_timeout,
        worker_count=worker_count,
        reconnect_pause=base.reconnect_pause,
        grace_period=base.grace_period,
        await_shutdown_period=base.await_shutdown_period,
        command_delay=base.command_delay,
    )


async def _run_pool(config: RCONWorkerPoolConfig) -> float:
    """Time the end-to-end execution of NUM_COMMANDS through a worker pool.

    Measures from the moment commands are queued until every command's
    completion event has been set, giving the true wall-clock throughput.

    :param config: Worker pool configuration to benchmark
    :return: Elapsed wall-clock seconds
    """
    commands = [RCONCommand(command="list", user=None) for _ in range(NUM_COMMANDS)]

    async with RCONWorkerPool(config) as pool:
        start = timeit.default_timer()
        for cmd in commands:
            await pool.queue_command(cmd)
        await asyncio.gather(*(cmd.completion.wait() for cmd in commands))
        return timeit.default_timer() - start


def worker_benchmark(
    config: BenchmarkConfig,
    rcon_config: RCONWorkerPoolConfig,
) -> None:
    """Run the benchmark suite for the RCON worker pool and save the results."""
    single_times: list[float] = []
    multi_times: list[float] = []

    single_cfg = _make_config(rcon_config, worker_count=1)
    multi_cfg = _make_config(rcon_config, worker_count=5)

    for i in range(1, NUM_SAMPLES + 1):
        st = asyncio.run(_run_pool(single_cfg))
        mt = asyncio.run(_run_pool(multi_cfg))
        single_times.append(st)
        multi_times.append(mt)
        print(f"[{i}/{NUM_SAMPLES}]  1 worker: {st:.4f}s   5 workers: {mt:.4f}s")

    # ---------- statistics ----------
    single_arr = np.array(single_times)
    multi_arr = np.array(multi_times)

    means = [single_arr.mean(), multi_arr.mean()]
    ci = [
        CONFIDENCE_Z * single_arr.std(ddof=1) / np.sqrt(NUM_SAMPLES),
        CONFIDENCE_Z * multi_arr.std(ddof=1) / np.sqrt(NUM_SAMPLES),
    ]

    print(f"\n1 worker  — mean: {means[0]:.4f}s  ± {ci[0]:.4f}s (95% CI)")
    print(f"5 workers — mean: {means[1]:.4f}s  ± {ci[1]:.4f}s (95% CI)")

    # ---------- bar plot ----------
    labels = ["1 Worker", "5 Workers"]
    x = np.arange(len(labels))

    fig, ax = plt.subplots(figsize=(7, 5))
    colors = ["#4C72B0", "#DD8452"]
    bars = ax.bar(x, means, yerr=ci, capsize=8, width=0.45, color=colors)

    ax.set_ylabel("Time (s)")
    ax.set_title(f"RCON Worker Pool — {NUM_COMMANDS} commands, {NUM_SAMPLES} samples")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.bar_label(bars, fmt="%.4f", padding=4)
    ax.set_ylim(bottom=0)
    ax.grid(axis="y", alpha=0.3)

    fig.tight_layout()
    out = Path(config.results_directory) / "rcon_worker_pool_performance.png"
    fig.savefig(out, dpi=150)
