"""Five synthetic 4K desktops carrying 47 ground-truth strings, and the window on each.

The corpus behind the legibility arm of [test_image_budget_live.py](test_image_budget_live.py)
(ADR-0029). Every desktop is 3840x2160 and is built the same way: a wallpaper, a taskbar, a
background window, and **one focused application window** whose bounds are declared before any
ground-truth string is placed. That rectangle is the crop a ``focus`` capture would produce, and
declaring it first is what keeps the measurement honest: no string can be nudged to flatter the
crop, and whether a string falls inside the window is computed from where it was drawn rather
than asserted.

The strings are named by their place on screen and never by their value, so the model is asked
what is in the editor's status bar rather than shown a candidate to agree with. Their physical
type sizes are the ones a real desktop uses: 15 px is what an unscaled monitor gives a terminal,
and the rest are what a 4K laptop at 150% scaling draws. The 15 px row is the residue the window
crop is under test against.

Rebuilt rather than reused: the 2026-08-06 legibility corpus was a scratch harness and only its
numbers were recorded, so this one reproduces its **shape** (five desktops, 47 strings, the same
size ladder, dark and light themes, full contrast and spreadsheet grey) and not its bytes. That
is why the arm runs its own whole-display control in the same session rather than comparing
against the recorded table.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from screen_paint import Colour, Rect, Screen, advance

WIDTH = 3840
HEIGHT = 2160

_INK: Colour = (24, 26, 30)
_PAPER: Colour = (250, 250, 248)
_GREY: Colour = (122, 126, 134)
_PANEL: Colour = (236, 238, 241)
_RULE: Colour = (206, 209, 214)
_DARK: Colour = (22, 24, 32)
_DARK_PANEL: Colour = (34, 37, 48)
_DARK_BAR: Colour = (44, 48, 62)
_DARK_INK: Colour = (206, 212, 224)
_DIM: Colour = (138, 146, 162)
_ACCENT: Colour = (56, 122, 210)
_WHITE: Colour = (255, 255, 255)


@dataclass(frozen=True)
class Truth:
    """One scored string: where it sits, what it says, its type size, and whether the crop
    contains it."""

    key: str
    where: str
    value: str
    size: int
    inside: bool


@dataclass(frozen=True)
class Desktop:
    """One rendered desktop, its focused window, and the strings it carries."""

    name: str
    screen: Screen
    window: Rect
    truths: tuple[Truth, ...]


@dataclass
class Scene:
    """A desktop under construction: the buffer, the focused window, and what was drawn."""

    screen: Screen
    window: Rect
    truths: list[Truth] = field(default_factory=list[Truth])

    def note(self, x: int, y: int, value: str, *, size: int, colour: Colour) -> None:
        """Draw ordinary screen furniture, which is never scored."""
        self.screen.text(x, y, value, size=size, colour=colour)

    def truth(
        self, key: str, where: str, value: str, *, at: tuple[int, int], size: int, colour: Colour
    ) -> None:
        """Draw a scored string and record whether the focused window contains it."""
        drawn = self.screen.text(at[0], at[1], value, size=size, colour=colour)
        self.truths.append(
            Truth(key=key, where=where, value=value, size=size, inside=self.window.contains(drawn))
        )

    def run(
        self,
        prefix: str,
        spec: tuple[str, str, str],
        *,
        at: tuple[int, int],
        size: int,
        colour: Colour,
    ) -> None:
        """Draw ``prefix`` then a scored ``(key, where, value)`` after it, on one line."""
        self.note(at[0], at[1], prefix, size=size, colour=colour)
        left = at[0] + advance(size) * len(prefix)
        self.truth(spec[0], spec[1], spec[2], at=(left, at[1]), size=size, colour=colour)


def _wallpaper(*, dark: bool) -> Screen:
    """A banded gradient with a taskbar, which is what a downscale has to survive."""
    top: Colour = (18, 22, 34) if dark else (188, 199, 214)
    screen = Screen(WIDTH, HEIGHT, top)
    step = 2 if dark else 1
    for band in range(24):
        shade = (
            min(255, top[0] + band * step),
            min(255, top[1] + band * step),
            min(255, top[2] + band * step),
        )
        screen.fill(Rect(0, band * 90, WIDTH, 90), shade)
    screen.fill(Rect(0, HEIGHT - 64, WIDTH, 64), _DARK_PANEL)
    return screen


def _frame(screen: Screen, rect: Rect, title: str, *, dark: bool) -> None:
    """A window: border, title bar with its title, and the client area behind its content."""
    screen.fill(rect, (58, 62, 78) if dark else _RULE)
    bar = Rect(rect.x + 3, rect.y + 3, rect.width - 6, 54)
    screen.fill(bar, _DARK_BAR if dark else _ACCENT)
    body = Rect(rect.x + 3, rect.y + 57, rect.width - 6, rect.height - 60)
    screen.fill(body, _DARK if dark else _PAPER)
    screen.text(rect.x + 24, rect.y + 16, title, size=26, colour=_WHITE)


def _editor() -> Desktop:
    """A code editor at 150% scaling, dark theme, over a wallpaper and a taskbar."""
    screen = _wallpaper(dark=True)
    window = Rect(280, 200, 2000, 1400)
    _frame(screen, window, "screen_tool.py", dark=True)
    scene = Scene(screen, window)
    screen.fill(Rect(window.x + 3, window.y + 57, 90, window.height - 60), _DARK_PANEL)
    for row in range(22):
        scene.note(window.x + 30, window.y + 120 + row * 44, f"{row + 41}", size=20, colour=_DIM)
    code = (
        "def describe(capture: ScreenCapture) -> str:",
        "    image = capture.image",
        "    size = str(image.width) + image.mime_type",
        "    if capture.target is CaptureTarget.FOCUS:",
        "        return window_sentence(image, capture)",
    )
    for row, line in enumerate(code):
        scene.note(window.x + 130, window.y + 120 + row * 44, line, size=20, colour=_DARK_INK)
    scene.run(
        "    stub = connect(host, ",
        (
            "editor_port",
            "the port number in the connect() call in the editor's code",
            "50419)",
        ),
        at=(window.x + 130, window.y + 340),
        size=20,
        colour=_DARK_INK,
    )
    scene.run(
        "    deadline = ",
        (
            "editor_timeout",
            "the number the deadline is assigned in the editor's code",
            "27.5",
        ),
        at=(window.x + 130, window.y + 384),
        size=20,
        colour=_DARK_INK,
    )
    scene.run(
        "    digest = ",
        (
            "editor_digest",
            "the digest literal in the editor's code",
            "'a91f7c04'",
        ),
        at=(window.x + 130, window.y + 428),
        size=20,
        colour=_DARK_INK,
    )
    scene.run(
        "def ",
        (
            "editor_symbol",
            "the function name on the def line below the digest",
            "rehydrate_slot(slot):",
        ),
        at=(window.x + 130, window.y + 472),
        size=20,
        colour=_DARK_INK,
    )
    panel = Rect(window.x + 3, window.y + window.height - 320, window.width - 6, 260)
    screen.fill(panel, _DARK_PANEL)
    scene.run(
        "PROBLEMS      ",
        (
            "editor_lint_count",
            "the number of problems in the editor's problems panel header",
            "14 problems",
        ),
        at=(panel.x + 30, panel.y + 20),
        size=18,
        colour=_DIM,
    )
    scene.run(
        "line 96  ",
        (
            "editor_lint_rule",
            "the lint rule code on the first line of the editor's problems panel",
            "PLR0913",
        ),
        at=(panel.x + 30, panel.y + 78),
        size=18,
        colour=_DARK_INK,
    )
    bar = Rect(window.x + 3, window.y + window.height - 60, window.width - 6, 57)
    screen.fill(bar, _DARK_BAR)
    status = (
        ("editor_branch", "the git branch name in the editor's status bar", "slice/window-target"),
        ("editor_position", "the line and column readout in the status bar", "Ln 482, Col 37"),
        ("editor_encoding", "the file encoding shown in the status bar", "UTF-8 LF"),
    )
    for index, (key, where, value) in enumerate(status):
        scene.truth(
            key, where, value, at=(bar.x + 24 + index * 400, bar.y + 18), size=15, colour=_DARK_INK
        )
    scene.truth(
        "desk_clock_editor",
        "the clock in the taskbar at the bottom of the screen",
        "09:47",
        at=(WIDTH - 260, HEIGHT - 44),
        size=15,
        colour=_DARK_INK,
    )
    return Desktop("editor", screen, window, tuple(scene.truths))


def _terminal() -> Desktop:
    """A terminal at 100% scaling: the unscaled monitor, and where 15 px type lives."""
    screen = _wallpaper(dark=True)
    _frame(screen, Rect(120, 120, 900, 500), "", dark=True)
    window = Rect(1980, 980, 1500, 950)
    _frame(screen, window, "bash", dark=True)
    scene = Scene(screen, window)
    scene.truth(
        "term_host",
        "the hostname beside the shell name in the terminal's title bar",
        "build02",
        at=(window.x + 160, window.y + 18),
        size=21,
        colour=_WHITE,
    )
    lines = (
        ("term_digest", "the digest the terminal printed for the build", "7f2c9ab1"),
        ("term_bytes", "the byte count the terminal printed for the artifact", "43450 B"),
        ("term_port", "the port the terminal says the server is listening on", "9317"),
        ("term_path", "the file path in the terminal's last error line", "/srv/models/cx.gguf"),
        ("term_elapsed", "the elapsed time the terminal printed for the run", "184.6s"),
    )
    scene.note(window.x + 30, window.y + 90, "user@build02:~$ just check", size=15, colour=_DIM)
    for row, (key, where, value) in enumerate(lines):
        top = window.y + 140 + row * 40
        scene.run(
            "  ->  ",
            (key, where, value),
            at=(window.x + 30, top),
            size=15,
            colour=_DARK_INK,
        )
    for row in range(12):
        scene.note(
            window.x + 30,
            window.y + 380 + row * 40,
            f"  ok  packages/core/tests/test_case_{row}.py passed in 0.0{row}s",
            size=15,
            colour=_DIM,
        )
    scene.truth(
        "desk_icon_terminal",
        "the title bar of the file manager window at the top left of the screen",
        "Files",
        at=(144, 136),
        size=18,
        colour=_WHITE,
    )
    return Desktop("terminal", screen, window, tuple(scene.truths))


def _spreadsheet() -> Desktop:
    """A spreadsheet at 150% scaling: grey cell text, in a window wider than the capture edge."""
    screen = _wallpaper(dark=False)
    window = Rect(560, 380, 2400, 1350)
    _frame(screen, window, "forecast.xlsx", dark=False)
    scene = Scene(screen, window)
    scene.run(
        "fx  ",
        (
            "sheet_formula",
            "the formula shown in the spreadsheet's formula bar",
            "=SUM(D4:D19)*1.075",
        ),
        at=(window.x + 40, window.y + 90),
        size=26,
        colour=_INK,
    )
    headers = (
        ("sheet_header_c", "the third column header of the spreadsheet", "Renewals"),
        ("sheet_header_d", "the fourth column header of the spreadsheet", "Net ARR"),
    )
    for index, (key, where, value) in enumerate(headers):
        scene.truth(
            key,
            where,
            value,
            at=(window.x + 700 + index * 520, window.y + 180),
            size=21,
            colour=_INK,
        )
    for row in range(14):
        rule = Rect(window.x + 40, window.y + 240 + row * 62, window.width - 80, 2)
        screen.fill(rule, _RULE)
        scene.note(window.x + 60, window.y + 258 + row * 62, f"{row + 4}", size=20, colour=_GREY)
    cells = (
        ("sheet_cell_1", "the fourth column value in the spreadsheet's first data row", "418,220"),
        ("sheet_cell_2", "the fourth column value in the second data row", "91,455"),
        ("sheet_cell_3", "the fourth column value in the third data row", "6,038"),
        ("sheet_cell_4", "the third column value in the fourth data row", "72.4%"),
        ("sheet_cell_5", "the third column value in the fifth data row", "31.9%"),
        ("sheet_cell_6", "the first column label in the sixth data row", "Aurelia SA"),
    )
    columns = (1220, 1220, 1220, 700, 700, 200)
    for index, (key, where, value) in enumerate(cells):
        top = window.y + 258 + index * 62
        scene.truth(key, where, value, at=(window.x + columns[index], top), size=20, colour=_GREY)
    scene.truth(
        "desk_clock_sheet",
        "the clock in the taskbar at the bottom of the screen",
        "14:06",
        at=(WIDTH - 260, HEIGHT - 44),
        size=15,
        colour=_DARK_INK,
    )
    return Desktop("spreadsheet", screen, window, tuple(scene.truths))


def _browser() -> Desktop:
    """A browser article at 150% scaling: a headline, body prose, and two footnotes."""
    screen = _wallpaper(dark=False)
    _frame(screen, Rect(140, 240, 900, 620), "", dark=False)
    window = Rect(1420, 240, 1750, 1600)
    _frame(screen, window, "Ledger Weekly", dark=False)
    scene = Scene(screen, window)
    screen.fill(Rect(window.x + 3, window.y + 57, window.width - 6, 70), _PANEL)
    scene.truth(
        "web_url",
        "the address shown in the browser's address bar",
        "ledgerweekly.example/storage",
        at=(window.x + 40, window.y + 74),
        size=20,
        colour=_GREY,
    )
    scene.truth(
        "web_headline",
        "the headline of the article in the browser",
        "Storage Costs Fall",
        at=(window.x + 40, window.y + 170),
        size=52,
        colour=_INK,
    )
    scene.run(
        "by ",
        (
            "web_byline",
            "the name in the byline under the article's headline",
            "Marta Ilves",
        ),
        at=(window.x + 40, window.y + 260),
        size=18,
        colour=_GREY,
    )
    body = (
        ("web_body_1", "the price per terabyte in the article's first paragraph", "$4.18 per TB"),
        ("web_body_2", "the percentage in the article's second paragraph", "37 percent"),
        ("web_body_3", "the year the article's third paragraph names", "2031"),
    )
    for index, (key, where, value) in enumerate(body):
        top = window.y + 330 + index * 200
        scene.note(window.x + 40, top, "Analysts said the change was", size=26, colour=_INK)
        scene.truth(key, where, value, at=(window.x + 40, top + 50), size=26, colour=_INK)
        scene.note(window.x + 40, top + 100, "over the period covered.", size=26, colour=_INK)
    scene.truth(
        "web_quote",
        "the pull quote set larger than the article's body text",
        "Nobody rents tape now",
        at=(window.x + 40, window.y + 960),
        size=30,
        colour=_ACCENT,
    )
    notes = (
        ("web_note_1", "the reference number in the article's first footnote", "note 12"),
        ("web_note_2", "the source named in the article's second footnote", "Kestrel Index"),
    )
    for index, (key, where, value) in enumerate(notes):
        top = window.y + 1120 + index * 40
        scene.truth(key, where, value, at=(window.x + 40, top), size=15, colour=_GREY)
    scene.truth(
        "desk_other_window",
        "the title bar of the window behind the browser, at the left of the screen",
        "Downloads",
        at=(164, 256),
        size=26,
        colour=_WHITE,
    )
    return Desktop("browser", screen, window, tuple(scene.truths))


def _chat() -> Desktop:
    """A chat client at 150% scaling: a tall narrow window with timestamps and a badge."""
    screen = _wallpaper(dark=False)
    _frame(screen, Rect(160, 620, 1100, 700), "", dark=False)
    window = Rect(2280, 480, 1300, 1500)
    _frame(screen, window, "Threads", dark=False)
    scene = Scene(screen, window)
    scene.truth(
        "chat_name",
        "the name of the person in the open chat conversation",
        "Priya Raman",
        at=(window.x + 40, window.y + 90),
        size=26,
        colour=_INK,
    )
    messages = (
        ("chat_msg_1", "the invoice number in the first chat message", "invoice 4021"),
        ("chat_msg_2", "the time the second chat message proposes", "16:30 Thursday"),
        ("chat_msg_3", "the room named in the third chat message", "room B2"),
    )
    tails = (
        ("chat_time_1", "the timestamp under the first chat message", "09:12", 15),
        ("chat_time_2", "the timestamp under the second chat message", "09:41", 15),
        ("chat_status", "the delivery status under the third chat message", "Delivered 09:58", 18),
    )
    for index, (key, where, value) in enumerate(messages):
        top = window.y + 200 + index * 260
        screen.fill(Rect(window.x + 40, top - 16, window.width - 160, 150), _PANEL)
        scene.truth(key, where, value, at=(window.x + 64, top), size=21, colour=_INK)
        scene.note(window.x + 64, top + 44, "let me know if that works", size=21, colour=_INK)
        tail_key, tail_where, tail_value, tail_size = tails[index]
        scene.truth(
            tail_key,
            tail_where,
            tail_value,
            at=(window.x + 64, top + 96),
            size=tail_size,
            colour=_GREY,
        )
    scene.truth(
        "chat_badge",
        "the unread count in the badge at the top right of the chat window",
        "23",
        at=(window.x + window.width - 140, window.y + 90),
        size=30,
        colour=_ACCENT,
    )
    scene.truth(
        "chat_typing",
        "the line at the bottom of the chat window saying who is typing",
        "Priya is typing",
        at=(window.x + 40, window.y + window.height - 100),
        size=18,
        colour=_GREY,
    )
    scene.truth(
        "desk_strip_chat",
        "the title bar of the window behind the chat window, at the left of the screen",
        "Sprint 42 board",
        at=(184, 636),
        size=18,
        colour=_WHITE,
    )
    return Desktop("chat", screen, window, tuple(scene.truths))


_BUILDERS: tuple[Callable[[], Desktop], ...] = (_editor, _terminal, _spreadsheet, _browser, _chat)


def desktops() -> tuple[Desktop, ...]:
    """Render the whole corpus, in a fixed order."""
    return tuple(build() for build in _BUILDERS)
