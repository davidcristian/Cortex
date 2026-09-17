"""The `EmailSender` contract checks, run over every implementation of the port."""

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import pytest

from cortex_email import EmailAttachment, EmailDraft, EmailSender, SendError
from cortex_email.values import MAX_ATTACHMENT_CHARS, MAX_ATTACHMENTS, MAX_FILENAME_CHARS

_TO = "you@example.com"
_DRAFT = EmailDraft(_TO, "Lunch", "Shall we?")
_BLIND = "gone@example.com"


@dataclass(frozen=True, slots=True)
class Sent:
    """What one accepted send handed its transport, read back into the draft's own terms."""

    to: str
    subject: str
    body: str
    cc: str
    bcc: str
    html: str
    attachments: tuple[EmailAttachment, ...]


@dataclass(frozen=True, slots=True)
class SenderUnderTest:
    """One implementation, what its transport was handed, and the two conditions to arrange."""

    sender: EmailSender
    outbox: Callable[[], Sequence[Sent]]
    break_transport: Callable[[], None]
    refuse_recipient: Callable[[str], None]


def _draft(
    *, cc: str = "", bcc: str = "", attachments: tuple[EmailAttachment, ...] = ()
) -> EmailDraft:
    return EmailDraft(_TO, "Hi", "b", cc=cc, bcc=bcc, attachments=attachments)


_UNSENDABLE: tuple[tuple[str, EmailDraft], ...] = (
    ("recipient must not contain a newline", EmailDraft(f"{_TO}\r\nBcc: evil@x.test", "Hi", "b")),
    ("subject must not contain a newline", EmailDraft(_TO, "Hi\nBcc: evil@x.test", "b")),
    ("cc must not contain a newline", _draft(cc="c@example.com\r\nBcc: evil@x.test")),
    ("bcc must not contain a newline", _draft(bcc="b@example.com\r\nTo: evil@x.test")),
    (
        "attachment filename must not contain a newline",
        _draft(attachments=(EmailAttachment("n.txt\r\nBcc: evil@x.test", "x"),)),
    ),
    ("filename must not be empty", _draft(attachments=(EmailAttachment("", "x"),))),
    (
        f"filename must be at most {MAX_FILENAME_CHARS} characters",
        _draft(attachments=(EmailAttachment("n" * (MAX_FILENAME_CHARS + 1), "x"),)),
    ),
    (
        f"at most {MAX_ATTACHMENTS} attachments",
        _draft(
            attachments=tuple(EmailAttachment(f"{n}.txt", "x") for n in range(MAX_ATTACHMENTS + 1))
        ),
    ),
    (
        f"must total at most {MAX_ATTACHMENT_CHARS} characters",
        _draft(attachments=(EmailAttachment("big.txt", "x" * (MAX_ATTACHMENT_CHARS + 1)),)),
    ),
    *(
        ("is not a MIME subtype token", _draft(attachments=(EmailAttachment("n.txt", "x", kind),)))
        for kind in ("text/csv", "plain; boundary=x", "plain\r\nX-Evil: y", "", "-plain")
    ),
)


def a_send_answers_one_line_naming_its_recipient_and_subject(case: SenderUnderTest) -> None:
    line = case.sender.send(_DRAFT)
    assert "\n" not in line
    assert _DRAFT.to in line
    assert _DRAFT.subject in line


def a_plain_draft_is_handed_over_with_no_optional_part(case: SenderUnderTest) -> None:
    case.sender.send(_DRAFT)
    assert list(case.outbox()) == [Sent(_TO, "Lunch", "Shall we?", "", "", "", ())]


def every_part_of_a_draft_is_handed_over_as_written(case: SenderUnderTest) -> None:
    attachments = (
        EmailAttachment("notes.md", "# Notes\n\n- one", "markdown"),
        EmailAttachment("data.csv", "a,b\n1,2", "csv"),
    )
    draft = EmailDraft(
        _TO,
        "Notes",
        "plain body",
        cc="cc@example.com",
        bcc="bcc@example.com",
        html="<p>rich</p>",
        attachments=attachments,
    )
    case.sender.send(draft)
    expected = Sent(
        _TO, "Notes", "plain body", "cc@example.com", "bcc@example.com", "<p>rich</p>", attachments
    )
    assert list(case.outbox()) == [expected]


def a_draft_the_port_refuses_never_reaches_the_transport(case: SenderUnderTest) -> None:
    for reason, draft in _UNSENDABLE:
        with pytest.raises(ValueError, match=re.escape(reason)):
            case.sender.send(draft)
    assert list(case.outbox()) == []


def attachments_up_to_both_bounds_are_handed_over_whole(case: SenderUnderTest) -> None:
    most = tuple(EmailAttachment(f"part{n}.txt", "x") for n in range(MAX_ATTACHMENTS))
    half = MAX_ATTACHMENT_CHARS // 2
    budget = (EmailAttachment("a.txt", "a" * half), EmailAttachment("b.txt", "b" * half))
    accented = (EmailAttachment("accents.txt", "é" * MAX_ATTACHMENT_CHARS),)
    for attachments in (most, budget, accented):
        case.sender.send(_draft(attachments=attachments))
    assert [sent.attachments for sent in case.outbox()] == [most, budget, accented]


def a_transport_that_cannot_deliver_raises_send_error(case: SenderUnderTest) -> None:
    case.break_transport()
    with pytest.raises(SendError):
        case.sender.send(_DRAFT)
    assert list(case.outbox()) == []


def a_send_every_recipient_refused_raises_send_error_naming_them(case: SenderUnderTest) -> None:
    case.refuse_recipient(_TO)
    with pytest.raises(SendError, match=re.escape(_TO)):
        case.sender.send(_DRAFT)
    assert list(case.outbox()) == []


def a_send_refused_in_part_is_handed_over_and_names_whom_it_missed(case: SenderUnderTest) -> None:
    case.refuse_recipient(_BLIND)
    line = case.sender.send(_draft(bcc=_BLIND))
    assert "\n" not in line
    assert _BLIND in line
    assert [sent.bcc for sent in case.outbox()] == [_BLIND]


type Check = Callable[[SenderUnderTest], None]

ALL_CHECKS: tuple[Check, ...] = (
    a_send_answers_one_line_naming_its_recipient_and_subject,
    a_plain_draft_is_handed_over_with_no_optional_part,
    every_part_of_a_draft_is_handed_over_as_written,
    a_draft_the_port_refuses_never_reaches_the_transport,
    attachments_up_to_both_bounds_are_handed_over_whole,
    a_transport_that_cannot_deliver_raises_send_error,
    a_send_every_recipient_refused_raises_send_error_naming_them,
    a_send_refused_in_part_is_handed_over_and_names_whom_it_missed,
)
