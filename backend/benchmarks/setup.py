"""Setup script for benchmarking the Minecraft RCON server."""

import os
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator

    from .config import BenchmarkConfig


@contextmanager
def setup_benchmark(config: BenchmarkConfig) -> Generator[None]:
    """Run the Minecraft server."""
    # Create a directory for storing benchmark results
    if not Path(config.results_directory).exists():
        Path.mkdir(Path(config.results_directory), parents=True, exist_ok=True)

    if not Path(config.minecraft_server_jar_path).is_file():
        msg = (
            f"Minecraft server JAR file not found at {config.minecraft_server_jar_path}"
        )
        raise FileNotFoundError(msg)

    # cd to the directory containing the Minecraft server JAR file
    Path(config.minecraft_server_jar_path).parent.mkdir(parents=True, exist_ok=True)
    os.chdir(Path(config.minecraft_server_jar_path).parent)

    server = subprocess.Popen(  # noqa: S603
        ["java", "-jar", config.minecraft_server_jar_path, "nogui"],  # noqa: S607
    )

    # Wait for the Minecraft server to start up and be ready for RCON connections
    print("Waiting for Minecraft server to start...")
    time.sleep(2)  # Give the server time to fully initialize
    print("Proceeding with benchmarks...")

    yield

    print("Shutting down Minecraft server...")
    server.kill()
