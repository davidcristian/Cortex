"""Seam server configuration: env-driven (CORTEX_SEAM_*), loopback by default."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class SeamServerConfig(BaseSettings):
    """Where the brain hosts BrainService (loopback-only per ROADMAP assumption 5)."""

    model_config = SettingsConfigDict(env_prefix="CORTEX_SEAM_")

    host: str = "127.0.0.1"
    port: int = 50051

    @property
    def bind_address(self) -> str:
        """The `host:port` string handed to grpc's `add_insecure_port`."""
        return f"{self.host}:{self.port}"
