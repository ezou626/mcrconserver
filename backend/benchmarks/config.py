"""Config for benchmarking the Minecraft RCON server."""

import os
from dataclasses import dataclass, field


@dataclass
class BenchmarkConfig:
    """Configuration for the benchmarking process."""

    minecraft_server_jar_path: str
    rcon_port: int
    rcon_password: str
    results_directory: str
