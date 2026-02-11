"""Setup script for benchmarking the Minecraft RCON server."""

import logging
import os
import socket
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator

    from .config import BenchmarkConfig

LOGGER = logging.getLogger(__name__)

_SERVER_STARTUP_TIMEOUT = 60
_POLL_INTERVAL = 1


def _wait_for_rcon(port: int, timeout: int = _SERVER_STARTUP_TIMEOUT) -> None:
    """Block until the RCON port accepts connections or timeout is reached.

    :param port: The RCON port to check
    :param timeout: Maximum seconds to wait
    :raises TimeoutError: If the port is not reachable within the timeout
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("localhost", port), timeout=1):
                LOGGER.info("RCON port %d is accepting connections", port)
                return
        except OSError:
            time.sleep(_POLL_INTERVAL)

    msg = f"RCON port {port} did not become available within {timeout}s"
    raise TimeoutError(msg)


@contextmanager
def setup_benchmark(config: BenchmarkConfig) -> Generator[None]:
    """Start the Minecraft server, wait for RCON, yield, then kill the server."""
    # Resolve results_directory to an absolute path before chdir moves us
    # into the Minecraft server directory.
    config.results_directory = str(Path(config.results_directory).resolve())

    if not Path(config.results_directory).exists():
        Path.mkdir(Path(config.results_directory), parents=True, exist_ok=True)

    if not Path(config.minecraft_server_jar_path).is_file():
        msg = (
            f"Minecraft server JAR file not found at {config.minecraft_server_jar_path}"
        )
        raise FileNotFoundError(msg)

    Path(config.minecraft_server_jar_path).parent.mkdir(parents=True, exist_ok=True)
    os.chdir(Path(config.minecraft_server_jar_path).parent)

    server = subprocess.Popen(  # noqa: S603
        ["java", "-jar", config.minecraft_server_jar_path, "nogui"],  # noqa: S607
    )

    try:
        _wait_for_rcon(config.rcon_port)
    except TimeoutError:
        server.kill()
        raise

    yield

    server.kill()
