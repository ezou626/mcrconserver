"""Config for benchmarking the Minecraft RCON server."""

from dataclasses import dataclass


@dataclass
class BenchmarkConfig:
    """Configuration for the benchmarking process."""

    minecraft_server_jar_path: str
    rcon_port: int
    rcon_password: str
    results_directory: str
