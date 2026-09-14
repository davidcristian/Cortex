"""Which Postgres DSNs the driver this deployment dials can read as an authority.

``asyncpg`` reads the DSN inside ``create_pool`` and raises naming the segment it could not read
as a port, which for a password containing a ``/`` is part of that password.
"""

from urllib.parse import unquote, urlparse

__all__ = ["authority_is_readable"]


def authority_is_readable(dsn: str) -> bool:
    """Whether asyncpg's DSN parser can read this DSN's authority."""
    netloc = urlparse(dsn).netloc
    userinfo, at_sign, hostlist = netloc.partition("@")
    for hostspec in (hostlist if at_sign else userinfo).split(","):
        # A leading ``[`` opens an IPv6 literal, whose own colons are not a port separator.
        if not hostspec or hostspec[0] == "[":
            continue
        _, _, port = hostspec.partition(":")
        if not port:
            continue
        try:
            int(unquote(port))
        except ValueError:
            return False
    return True
