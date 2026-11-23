from pathlib import Path

import pytest

from composevolumes import Declared, read_volumes

REPO_ROOT = Path(__file__).resolve().parents[2]

SERVICES = "services:\n  r:\n    image: r\n    volumes:\n      - keep:/a\n"


def test_every_declaration_in_the_block_is_read_with_its_line() -> None:
    text = SERVICES + "volumes:\n  keep:\n  # a note\n  other:  # a note\n"
    assert read_volumes(text) == (Declared("keep", 7, plain=True), Declared("other", 9, plain=True))


def test_a_name_and_labels_leave_a_declaration_plain() -> None:
    text = "volumes:\n  keep:\n    name: kept\n    labels:\n      driver: tmpfs\n"
    assert read_volumes(text) == (Declared("keep", 2, plain=True),)


@pytest.mark.parametrize(
    "body",
    [
        "    driver: local\n",
        "    driver_opts:\n      type: tmpfs\n      device: tmpfs\n",
        "    external: true\n",
        "    name: kept\n    x-note: a\n",
        "    <<: *base\n",
    ],
)
def test_any_other_key_under_a_declaration_makes_it_not_plain(body: str) -> None:
    (declared,) = read_volumes("volumes:\n  keep:\n" + body)
    assert declared == Declared("keep", 2, plain=False)


@pytest.mark.parametrize("value", ["{}", "&cache", "{driver: local}"])
def test_a_declaration_with_a_value_after_its_name_is_not_plain(value: str) -> None:
    assert read_volumes(f"volumes:\n  keep: {value}\n") == (Declared("keep", 2, plain=False),)


def test_only_the_declaration_a_key_is_written_under_is_changed() -> None:
    text = "volumes:\n  first:\n    driver: local\n  second:\n    name: two\n"
    assert read_volumes(text) == (
        Declared("first", 2, plain=False),
        Declared("second", 4, plain=True),
    )


@pytest.mark.parametrize(
    "text",
    [
        SERVICES,
        "volumes: {keep: {}}\n",
        "volumes: &all\n  keep:\n",
        "x-volumes:\n  keep:\n",
        "volumes:\n  - keep\n    driver: local\n",
        "- volumes:\n  keep:\n",
    ],
)
def test_nothing_is_declared_outside_a_bare_top_level_volumes_block(text: str) -> None:
    assert read_volumes(text) == ()


def test_a_later_top_level_key_ends_the_block() -> None:
    text = "volumes:\n  keep:\nservices:\n  r:\n    driver: local\n"
    assert read_volumes(text) == (Declared("keep", 2, plain=True),)


def test_a_line_that_is_not_a_key_ends_the_block() -> None:
    text = "volumes:\n  keep:\n  - stray\n    driver: local\n  other:\n"
    assert read_volumes(text) == (Declared("keep", 2, plain=True),)


def test_the_gpu_overlay_declares_the_kernel_volume_plainly() -> None:
    text = (REPO_ROOT / "docker" / "docker-compose.gpu.yml").read_text(encoding="utf-8")
    line = text.splitlines().index("  compute-cache:") + 1
    assert Declared("compute-cache", line, plain=True) in read_volumes(text)
