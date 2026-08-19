"""Typed errors of the `Mailbox` port: the IMAP library's own exceptions never cross it.

The sidecar cannot import the brain's core (it is deployed on its own, ADR-0009), so the port's
failure channel is declared here rather than in `cortex_core.errors`, in the same two-member
shape that module established: one base for every way the mailbox could not answer, and one
narrower type for the single failure a caller can act on.
"""

from cortex_email.values import SEARCH_REFUSED


class MailboxError(Exception):
    """A `Mailbox` operation failed; the adapter wraps its library's errors into this.

    Says the mailbox could not answer: the Bridge was not reachable, TLS or the login was
    refused, the folder could not be examined, the connection went away mid-command. All of
    them are conditions of the machine rather than of the request, so none of them is fixed by
    writing a different query, and the honest thing to tell a caller is that email is not
    working right now.
    """


class SearchRefusedError(MailboxError):
    """The server read the search and refused it: the query is malformed (a `BAD` answer).

    The port's one narrower failure, and the distinction is between **a mailbox that could not
    answer** and **a request the server understood well enough to reject** (ADR-0022
    refused-search addendum). Every other `MailboxError` heals on its own once the Bridge, the
    network, or the credentials are fixed, and nothing about the query changes it. This one heals
    only when the query is rewritten, which is something the model reading the result can do, so
    it carries the `query` it refused and its message points at the dialect the tool's own field
    description spells out.

    It carries no part of the server's answer. What imaplib raises here reads
    ``UID command error: BAD [b'[Error offset=38]: expected space']``, an offset into a wire
    command the model never saw, from a library it is not told about; that stays on the chained
    cause, where an operator reading a traceback finds it.

    It is a subclass rather than a sibling so every existing ``except MailboxError`` keeps
    catching it, the `MemoryDataError` and `ModelNotHostedError` precedent: a caller with no use
    for the distinction goes on failing exactly as it did.
    """

    def __init__(self, query: str) -> None:
        super().__init__(f"{SEARCH_REFUSED}{query!r}")
        self.query = query
