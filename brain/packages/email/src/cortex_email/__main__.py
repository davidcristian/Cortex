"""`python -m cortex_email` runs the read-only IMAP MCP server.

Env: CORTEX_EMAIL_IMAP_HOST/PORT/USER/PASSWORD (ProtonMail Bridge), plus SECURITY, CA_CERT,
TLS_INSECURE (see `config.EmailConfig`). Wiring: `server.main`.
"""

from cortex_email.server import main

if __name__ == "__main__":  # pragma: no cover - module entry guard, reachable only via -m
    main()
