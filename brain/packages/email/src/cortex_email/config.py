"""Email MCP server configuration: env-driven (ProtonMail Bridge by default)."""

from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

TlsSecurity = Literal["starttls", "ssl"]
ImapSecurity = TlsSecurity

# The two defaults the email compose override repeats as its own substitution defaults, named
# here so `scripts/crosscheck.py` can compare the two. One name covers both TLS escape hatches
# because they are shut for the same reason.
DEFAULT_TLS_INSECURE = False
DEFAULT_SEND_ENABLED = False


class EmailConfig(BaseSettings):
    """Where the read-only email server connects."""

    model_config = SettingsConfigDict(env_prefix="CORTEX_EMAIL_IMAP_")

    host: str = "127.0.0.1"
    port: int = 1143
    user: str = ""
    password: SecretStr = SecretStr("")
    security: ImapSecurity = "starttls"
    ca_cert: str = ""
    tls_insecure: bool = DEFAULT_TLS_INSECURE


class SmtpConfig(BaseSettings):
    """Where, and whether, the email server sends over SMTP."""

    # No `validate_by_name`: with it the env prefix would open a second, undocumented
    # CORTEX_EMAIL_SMTP_ENABLED channel for the write switch. CORTEX_EMAIL_SEND_ENABLED, which
    # sits outside the prefix because it is a capability and not a connection detail, is the one.
    model_config = SettingsConfigDict(env_prefix="CORTEX_EMAIL_SMTP_")

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
