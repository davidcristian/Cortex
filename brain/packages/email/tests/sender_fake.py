"""The fake `EmailSender`: records what it would have sent, and fails on demand."""

from email.utils import getaddresses

from cortex_email import EmailDraft, SendError
from cortex_email.drafts import confirmation, refuse_unsendable


class FakeSender:
    """A fake EmailSender keeping every draft it accepted in ``sent``."""

    def __init__(self) -> None:
        self.sent: list[EmailDraft] = []
        self._refused: set[str] = set()
        self._failure: SendError | None = None

    def fail_with(self, error: SendError) -> None:
        """Make every later send raise ``error``, as a sender whose server is gone does."""
        self._failure = error

    def refuse(self, address: str) -> None:
        """Make the server turn ``address`` away on every later send."""
        self._refused.add(address)

    def send(self, draft: EmailDraft) -> str:
        """Refuse what the port refuses, then record the draft and answer the port's line."""
        refuse_unsendable(draft)
        if self._failure is not None:
            raise self._failure
        fields = [value for value in (draft.to, draft.cc, draft.bcc) if value]
        recipients = [address for _, address in getaddresses(fields)]
        refused = [address for address in recipients if address in self._refused]
        if len(refused) == len(recipients):
            msg = f"the email was not sent: the server refused {', '.join(refused)}"
            raise SendError(msg)
        self.sent.append(draft)
        return confirmation(draft, refused)
