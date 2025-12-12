"""Setup script for benchmarking the Minecraft RCON server."""

import subprocess
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

    server = subprocess.Popen(  # noqa: S603
        ["java", "-jar", config.minecraft_server_jar_path, "nogui"],  # noqa: S607
    )

    yield

    server.kill()
