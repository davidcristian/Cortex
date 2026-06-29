"""`python -m cortex_email` runs the read-only IMAP MCP server."""

from cortex_email.server import main

if __name__ == "__main__":  # pragma: no cover - module entry guard, reachable only via -m
    main()
