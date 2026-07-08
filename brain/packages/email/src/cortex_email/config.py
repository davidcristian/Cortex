"""Email MCP server configuration: env-driven (ProtonMail Bridge by default).

Two independent halves: `EmailConfig` (the Slice 6 read-only IMAP reader) and `SmtpConfig`
(the ADR-0022 send path, off unless CORTEX_EMAIL_SEND_ENABLED=true).
"""

from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

TlsSecurity = Literal["starttls", "ssl"]
# The reader's historical name for the same two modes; both halves accept the same values.
ImapSecurity = TlsSecurity


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


class SmtpConfig(BaseSettings):
    """Where (and whether) the email server sends over SMTP (ADR-0022).

    Defaults target a local ProtonMail Bridge: STARTTLS on 1025 (the Bridge's SMTP
    loopback) with the same cert-verification escape hatches as the IMAP half. The send
    path is OFF unless ``CORTEX_EMAIL_SEND_ENABLED=true``, which is an explicit, documented act
    (the sidecar stays byte-for-byte the read-only Slice 6 server otherwise), and
    enabling it without credentials fails fast at startup, never at first send.
    """

    # No `validate_by_name`: the env prefix would otherwise open a second, undocumented
    # `CORTEX_EMAIL_SMTP_ENABLED` channel for the write switch. `CORTEX_EMAIL_SEND_ENABLED`
    # is the one and only way to flip it (ADR-0022).
    model_config = SettingsConfigDict(env_prefix="CORTEX_EMAIL_SMTP_")

    # env CORTEX_EMAIL_SEND_ENABLED sits deliberately outside the SMTP_ prefix: it flips the
    # server's write capability, not a connection detail.
    enabled: bool = Field(default=False, validation_alias="CORTEX_EMAIL_SEND_ENABLED")
    host: str = "127.0.0.1"
    port: int = 1025
    user: str = ""
    password: SecretStr = SecretStr("")
    security: TlsSecurity = "starttls"
    ca_cert: str = ""
    tls_insecure: bool = False

    @model_validator(mode="after")
    def _enabled_needs_credentials(self) -> "SmtpConfig":
        if self.enabled and not (self.user and self.password.get_secret_value()):
            msg = (
                "CORTEX_EMAIL_SMTP_USER and CORTEX_EMAIL_SMTP_PASSWORD are required when "
                "CORTEX_EMAIL_SEND_ENABLED=true"
            )
            raise ValueError(msg)
        return self
