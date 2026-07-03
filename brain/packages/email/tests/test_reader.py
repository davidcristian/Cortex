"""Behavior tests for EmailReader: parse raw RFC822 into email values over a fake Mailbox."""

from collections.abc import Sequence

from cortex_email import EmailReader, RawEmail

_SIMPLE = (
    b"From: Alice <alice@example.com>\r\n"
    b"To: Bob <bob@example.com>\r\n"
    b"Subject: Lunch\r\n"
    b"Date: Fri, 03 Jul 2026 12:00:00 +0000\r\n"
    b"\r\n"
    b"Let's do lunch.\r\n"
)
# A message with no text/plain part: _body_text must return "" (and absent To/Date -> "").
_NO_TEXT_BODY = (
    b"From: Carol <carol@example.com>\r\n"
    b"Subject: Attachment\r\n"
    b"Content-Type: application/octet-stream\r\n"
    b"\r\n"
    b"\x00\x01\x02\r\n"
)
# HTML-only message: _body_text falls back to the html part (most real mail is HTML-only)
# and extracts readable text from it (ADR-0009 refinements addendum).
_HTML_ONLY = (
    b"From: Dave <dave@example.com>\r\n"
    b"Subject: Newsletter\r\n"
    b"Content-Type: text/html\r\n"
    b"\r\n"
    b"<p>Hello <b>world</b></p>\r\n"
)
# HTML-only message with no extractable prose: the raw HTML is kept so the body stays non-empty.
_HTML_IMAGE_ONLY = (
    b"From: Eve <eve@example.com>\r\n"
    b"Subject: Postcard\r\n"
    b"Content-Type: text/html\r\n"
    b"\r\n"
    b'<img src="cid:photo">\r\n'
)


class FakeMailbox:
    """A fake Mailbox returning canned raw messages, recording the search it was asked."""

    def __init__(
        self,
        *,
        folders: Sequence[str] = (),
        found: Sequence[RawEmail] = (),
        one: RawEmail | None = None,
    ) -> None:
        self._folders = folders
        self._found = found
        self._one = one
        self.searched: list[tuple[str, str, int]] = []

    def list_folders(self) -> Sequence[str]:
        return self._folders

    def search(self, folder: str, query: str, limit: int) -> Sequence[RawEmail]:
        self.searched.append((folder, query, limit))
        return self._found

    def fetch(self, folder: str, uid: str) -> RawEmail | None:
        del folder, uid
        return self._one


def test_folders_pass_through() -> None:
    assert list(EmailReader(FakeMailbox(folders=["INBOX", "Sent"])).folders()) == ["INBOX", "Sent"]


def test_search_maps_raw_headers_to_summaries() -> None:
    mailbox = FakeMailbox(found=[RawEmail(uid="7", raw=_SIMPLE)])
    (summary,) = EmailReader(mailbox).search("INBOX", "ALL", 10)
    assert (summary.uid, summary.sender, summary.subject) == (
        "7",
        "Alice <alice@example.com>",
        "Lunch",
    )
    assert "2026" in summary.date
    assert mailbox.searched == [("INBOX", "ALL", 10)]


def test_read_returns_full_detail_with_plain_body() -> None:
    detail = EmailReader(FakeMailbox(one=RawEmail(uid="7", raw=_SIMPLE))).read("INBOX", "7")
    assert detail is not None
    assert (detail.recipients, detail.subject, detail.body) == (
        "Bob <bob@example.com>",
        "Lunch",
        "Let's do lunch.",
    )


def test_read_missing_message_returns_none() -> None:
    assert EmailReader(FakeMailbox(one=None)).read("INBOX", "999") is None


def test_body_and_absent_headers_are_empty_without_any_text_part() -> None:
    detail = EmailReader(FakeMailbox(one=RawEmail(uid="8", raw=_NO_TEXT_BODY))).read("INBOX", "8")
    assert detail is not None
    assert (detail.body, detail.recipients, detail.date) == ("", "", "")


def test_read_extracts_text_from_html_when_no_plain_part() -> None:
    detail = EmailReader(FakeMailbox(one=RawEmail(uid="9", raw=_HTML_ONLY))).read("INBOX", "9")
    assert detail is not None
    assert detail.body == "Hello world"


def test_read_keeps_raw_html_when_nothing_extracts() -> None:
    detail = EmailReader(FakeMailbox(one=RawEmail(uid="10", raw=_HTML_IMAGE_ONLY))).read(
        "INBOX", "10"
    )
    assert detail is not None
    assert detail.body == '<img src="cid:photo">'
