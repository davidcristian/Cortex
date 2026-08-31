"""Email MCP server configuration: env-driven (ProtonMail Bridge by default).

Two independent halves: `EmailConfig` (the read-only IMAP reader) and `SmtpConfig`
(the ADR-0022 send path, off unless CORTEX_EMAIL_SEND_ENABLED=true).
"""

from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

TlsSecurity = Literal["starttls", "ssl"]
# The reader's historical name for the same two modes; both halves accept the same values.
ImapSecurity = TlsSecurity

# The two shipped answers the email compose override restates as its own substitution defaults,
# named here rather than left inside the fields so `scripts/crosscheck.py` can read them: a default
# the scan cannot compare is a default the stack may flip alone. One name covers both TLS escape
# hatches because it is one answer rather than two that coincide: an escape hatch is worth nothing
# unless it has to be opened deliberately, and the reader's and the sender's are shut for that
# single reason.
DEFAULT_TLS_INSECURE = False
DEFAULT_SEND_ENABLED = False


class EmailConfig(BaseSettings):
    """Where the read-only email server connects (ADR-0009).

    Defaults target a local ProtonMail Bridge: STARTTLS on 1143 with the Bridge's self-signed
    cert. Supply the Bridge username + generated password via env; verify the cert with
    ``ca_cert`` (the exported Bridge cert), or accept the self-signed cert on loopback with
    ``tls_insecure``, which ships off and has to be set for that deployment.
    """

    model_config = SettingsConfigDict(env_prefix="CORTEX_EMAIL_IMAP_")

    host: str = "127.0.0.1"
    port: int = 1143
    user: str = ""
    password: SecretStr = SecretStr("")
    security: ImapSecurity = "starttls"
    ca_cert: str = ""
    tls_insecure: bool = DEFAULT_TLS_INSECURE


class SmtpConfig(BaseSettings):
    """Where (and whether) the email server sends over SMTP (ADR-0022).

    Defaults target a local ProtonMail Bridge: STARTTLS on 1025 (the Bridge's SMTP
    loopback) with the same cert-verification escape hatches as the IMAP half. The send path is
    off unless ``CORTEX_EMAIL_SEND_ENABLED=true``, and the sidecar is byte-for-byte the read-only
    server until that is set. Enabling it without credentials fails at startup rather than at the
    first send.
    """

    # No `validate_by_name`: the env prefix would otherwise open a second, undocumented
    # `CORTEX_EMAIL_SMTP_ENABLED` channel for the write switch. `CORTEX_EMAIL_SEND_ENABLED`
    # is the one and only way to flip it (ADR-0022).
    model_config = SettingsConfigDict(env_prefix="CORTEX_EMAIL_SMTP_")

    # env CORTEX_EMAIL_SEND_ENABLED sits deliberately outside the SMTP_ prefix: it flips the
    # server's write capability, not a connection detail.
    enabled: bool = Field(
        default=DEFAULT_SEND_ENABLED, validation_alias="CORTEX_EMAIL_SEND_ENABLED"
    )
    host: str = "127.0.0.1"
    port: int = 1025
    user: str = ""
    password: SecretStr = SecretStr("")
    security: TlsSecurity = "starttls"
    ca_cert: str = ""
    tls_insecure: bool = DEFAULT_TLS_INSECURE

    @model_validator(mode="after")
    def _enabled_needs_credentials(self) -> "SmtpConfig":
        if self.enabled and not (self.user and self.password.get_secret_value()):
            msg = (
                "CORTEX_EMAIL_SMTP_USER and CORTEX_EMAIL_SMTP_PASSWORD are required when "
                "CORTEX_EMAIL_SEND_ENABLED=true"
            )
            raise ValueError(msg)
        return self
