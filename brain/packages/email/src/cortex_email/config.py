"""Read-only IMAP MCP server configuration: env-driven (ProtonMail Bridge by default)."""

from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ImapSecurity = Literal["starttls", "ssl"]


class EmailConfig(BaseSettings):
    """Where the read-only email server connects (ADR-0009).

    Defaults target a local ProtonMail Bridge: STARTTLS on 1143 with the Bridge's self-signed
    cert. Supply the Bridge username + generated password via env; verify the cert with
    ``ca_cert`` (the exported Bridge cert), or accept the self-signed cert on loopback with
    ``tls_insecure``. It is an explicit, documented escape hatch, never a silent default.
    """

    model_config = SettingsConfigDict(env_prefix="CORTEX_EMAIL_IMAP_")

    host: str = "127.0.0.1"
    port: int = 1143
    user: str = ""
    password: SecretStr = SecretStr("")
    security: ImapSecurity = "starttls"
    ca_cert: str = ""
    tls_insecure: bool = False
