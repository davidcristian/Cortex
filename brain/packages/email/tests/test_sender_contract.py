from collections.abc import Callable
from email.message import EmailMessage, MIMEPart

import pytest
from sender_contract import ALL_CHECKS, Check, SenderUnderTest, Sent
from sender_fake import FakeSender
from smtp_stub import FakeSmtp, config, patch_smtp

from cortex_email import EmailAttachment, SendError, SmtpSender

type Build = Callable[[pytest.MonkeyPatch], SenderUnderTest]


def _fake(_monkeypatch: pytest.MonkeyPatch) -> SenderUnderTest:
    sender = FakeSender()

    def outbox() -> list[Sent]:
        return [
            Sent(d.to, d.subject, d.body, d.cc, d.bcc, d.html, d.attachments) for d in sender.sent
        ]

    def break_transport() -> None:
        sender.fail_with(SendError("the email was not sent: connection refused"))

    return SenderUnderTest(sender, outbox, break_transport, sender.refuse)


def _text(part: MIMEPart | None) -> str:
    return "" if part is None else str(part.get_content()).removesuffix("\n")


def _read(message: EmailMessage) -> Sent:
    """What ``message`` contains, in the draft's terms."""
    return Sent(
        to=str(message["To"]),
        subject=str(message["Subject"]),
        body=_text(message.get_body(preferencelist=("plain",))),
        cc=str(message.get("Cc", "")),
        bcc=str(message.get("Bcc", "")),
        html=_text(message.get_body(preferencelist=("html",))),
        attachments=tuple(
            EmailAttachment(str(part.get_filename()), _text(part), part.get_content_subtype())
            for part in message.iter_attachments()
        ),
    )


def _smtp(monkeypatch: pytest.MonkeyPatch) -> SenderUnderTest:
    client = FakeSmtp()
    patch_smtp(monkeypatch, client)

    def break_transport() -> None:
        refused = ConnectionRefusedError(111, "Connection refused")
        patch_smtp(monkeypatch, client, connect_error=refused)

    return SenderUnderTest(
        sender=SmtpSender(config()),
        outbox=lambda: [_read(message) for message in client.sent],
        break_transport=break_transport,
        refuse_recipient=client.refused.add,
    )


@pytest.mark.parametrize("check", ALL_CHECKS, ids=lambda check: check.__name__)
@pytest.mark.parametrize("build", [_fake, _smtp], ids=["fake", "smtp"])
def test_the_contract_holds(check: Check, build: Build, monkeypatch: pytest.MonkeyPatch) -> None:
    check(build(monkeypatch))
