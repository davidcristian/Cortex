"""Which connection URLs the Postgres and Redis drivers can read as an authority.

Both drivers raise naming the segment they could not read as a port, which for a password
containing a ``/`` is part of that password. A segment that does read as a port is printed too.
"""

from urllib.parse import unquote, urlparse

__all__ = ["authority_is_readable"]


def authority_is_readable(dsn: str) -> bool:
    """Whether the drivers' URL parsers can read this URL's authority."""
    parsed = urlparse(dsn)
    # An ``@`` past the authority is a password's own ``@``: a ``/``, ``?`` or ``#`` before it
    # ended the authority early. A query value may hold one, so only a query key is searched.
    if "@" in parsed.path + parsed.fragment + parsed.query.partition("=")[0]:
        return False
    userinfo, at_sign, hostlist = parsed.netloc.partition("@")
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
