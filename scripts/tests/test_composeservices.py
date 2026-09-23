from pathlib import Path

import pytest

from composeservices import DEFAULT_DOCKERFILE, Build, ComposeServiceError, read_services
from composetargets import normalize

REPO_ROOT = Path(__file__).resolve().parents[2]

PROBE = """\
name: cortex-imap-probe

x-mail-root: &mail-root "/srv/mail"
x-config-root: &config-root "/etc/dovecot"

services:
  imap-probe:
    image: "dovecot/dovecot:2.3.21"
    entrypoint: ["/bin/sh", "/probe.sh"]
    volumes:
      - type: bind
        source: ./docker/dovecot/probe.conf
        target: /probe.conf
        read_only: true
    tmpfs:
      # the store, deliberately not a volume
      - *mail-root
      - *config-root
    ports:
      - "127.0.0.1:11143:143"
"""


def _one(text: str):  # noqa: ANN202 -- the single service under test, whatever shape it took
    """Return the one service a fixture declares, asserting the count so a test can use it."""
    services = read_services(text).services
    assert len(services) == 1, services
    return services[0]


def test_an_image_is_read_with_its_quotes_dropped() -> None:
    service = _one('services:\n  redis:\n    image: "redis:8-alpine"\n')
    assert (service.image, service.builds, service.defines) == ("redis:8-alpine", False, True)


def test_an_unquoted_image_is_read_whole() -> None:
    assert _one("services:\n  redis:\n    image: redis:8-alpine\n").image == "redis:8-alpine"


def test_a_service_that_only_builds_names_no_image_but_still_defines_one() -> None:
    service = _one("services:\n  brain:\n    build: ./brain\n")
    assert (service.image, service.builds, service.defines) == (None, True, True)


def test_a_service_naming_neither_an_image_nor_a_build_is_a_fragment() -> None:
    service = _one("services:\n  brain:\n    environment:\n      A: b\n    depends_on:\n      x:\n")
    assert (service.image, service.builds, service.defines) == (None, False, False)


def test_a_service_records_the_line_it_opens_on() -> None:
    assert _one("services:\n\n  # a note\n  redis:\n    image: r\n").line == 4


def test_every_service_in_a_file_is_read_in_order() -> None:
    text = "services:\n  a:\n    image: one\n  b:\n    image: two\n"
    assert [service.name for service in read_services(text).services] == ["a", "b"]


def test_a_short_build_names_its_context_and_takes_the_default_dockerfile() -> None:
    assert _one("services:\n  brain:\n    build: ./brain\n").build == Build(
        "./brain", DEFAULT_DOCKERFILE
    )


def test_a_build_block_names_both_halves() -> None:
    text = "services:\n  host:\n    build:\n      context: ./brain\n      dockerfile: D.model\n"
    assert _one(text).build == Build("./brain", "D.model")


def test_a_build_block_naming_only_a_context_takes_the_default_dockerfile() -> None:
    text = "services:\n  host:\n    build:\n      context: ./brain\n"
    assert _one(text).build == Build("./brain", DEFAULT_DOCKERFILE)


def test_both_halves_of_a_build_are_read_with_their_quotes_dropped() -> None:
    text = 'services:\n  h:\n    build:\n      context: "./b"\n      dockerfile: "D"\n'
    assert _one(text).build == Build("./b", "D")


def test_a_nested_block_inside_a_build_names_no_dockerfile() -> None:
    text = "services:\n  h:\n    build:\n      context: ./b\n      args:\n        TAG: '1'\n"
    assert _one(text).build == Build("./b", DEFAULT_DOCKERFILE)


def test_a_build_key_this_reader_takes_no_answer_from_changes_nothing() -> None:
    text = "services:\n  h:\n    build:\n      context: ./b\n      target: builder\n"
    assert _one(text).build == Build("./b", DEFAULT_DOCKERFILE)


def test_a_key_after_a_build_block_ends_it() -> None:
    text = "services:\n  h:\n    build:\n      context: ./b\n    image: pinned:1\n"
    service = _one(text)
    assert (service.build, service.image) == (Build("./b", DEFAULT_DOCKERFILE), "pinned:1")


def test_a_comment_beside_the_build_key_still_opens_the_block() -> None:
    text = "services:\n  h:\n    build: # the workspace\n      context: ./b\n"
    assert _one(text).build == Build("./b", DEFAULT_DOCKERFILE)


def test_a_service_that_does_not_build_carries_no_build_at_all() -> None:
    assert _one("services:\n  r:\n    image: r\n").build is None


def test_a_long_syntax_mount_covers_its_target_whatever_its_type_is() -> None:
    text = (
        "services:\n  db:\n    image: pg\n    volumes:\n"
        "      - type: volume\n        source: data\n        target: /var/lib/pg\n"
        "      - type: bind\n        source: ./init.sql\n        target: /init.sql\n"
        "        read_only: true\n"
    )
    assert _one(text).covered == ("/var/lib/pg", "/init.sql")


def test_a_short_syntax_mount_covers_its_second_field() -> None:
    assert _one(
        "services:\n  r:\n    image: r\n    volumes:\n      - redis-data:/data\n"
    ).covered == ("/data",)


def test_a_short_syntax_mount_with_a_mode_still_covers_the_middle_field() -> None:
    text = "services:\n  r:\n    image: r\n    volumes:\n      - ./seed:/seed:ro\n"
    assert _one(text).covered == ("/seed",)


def test_a_tmpfs_entry_covers_the_path_it_names() -> None:
    assert _one("services:\n  r:\n    image: r\n    tmpfs:\n      - /run\n").covered == ("/run",)


def test_a_tmpfs_entry_written_through_an_anchor_is_resolved() -> None:
    assert _one(PROBE).covered == ("/probe.conf", "/srv/mail", "/etc/dovecot")


def test_a_long_syntax_target_may_be_an_alias_too() -> None:
    text = 'x-at: &at "/srv/mail"\nservices:\n  s:\n    image: i\n    volumes:\n'
    text += "      - type: tmpfs\n        target: *at\n"
    assert _one(text).covered == ("/srv/mail",)


def test_a_flush_list_is_read_rather_than_walked_past() -> None:
    text = "services:\n  r:\n    image: r\n    volumes:\n    - type: bind\n      source: ./x\n"
    text += "      target: /x\n    - cache:/cache\n"
    assert _one(text).covered == ("/x", "/cache")


def test_a_long_entry_may_open_on_a_bare_dash() -> None:
    text = "services:\n  r:\n    image: r\n    volumes:\n      -\n        type: bind\n"
    text += "        source: ./x\n        target: /x\n"
    assert _one(text).covered == ("/x",)


def test_a_trailing_slash_is_not_a_second_form_of_one_path() -> None:
    assert _one("services:\n  r:\n    image: r\n    tmpfs:\n      - /run/\n").covered == ("/run",)


def test_normalize_leaves_the_root_a_path() -> None:
    assert (normalize("/srv/mail/"), normalize("/")) == ("/srv/mail", "/")


def test_a_key_after_a_volumes_block_ends_it() -> None:
    text = "services:\n  r:\n    image: r\n    volumes:\n      - a:/a\n    ports:\n      - '1:1'\n"
    assert _one(text).covered == ("/a",)


def test_a_top_level_key_after_a_volumes_block_ends_the_service_too() -> None:
    text = "services:\n  r:\n    image: r\n    volumes:\n      - type: bind\n"
    text += "        source: ./x\n        target: /x\nvolumes:\n  cache:\n"
    assert _one(text).covered == ("/x",)


def test_a_deeper_block_under_an_unrelated_key_covers_nothing() -> None:
    text = "services:\n  g:\n    image: g\n    deploy:\n      resources:\n        reservations:\n"
    text += "          devices:\n            - capabilities: [gpu]\n"
    assert _one(text).covered == ()


def test_the_project_name_is_read_when_the_file_sets_one() -> None:
    assert read_services(PROBE).project == "cortex-imap-probe"


def test_a_file_naming_no_project_says_so() -> None:
    assert read_services("services:\n  r:\n    image: r\n").project is None


def test_a_bare_name_key_names_no_project() -> None:
    assert read_services("name:\nservices:\n  r:\n    image: r\n").project is None


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("- not a key\n", "is not a top-level key"),
        ("services:\n  - r\n", "is not a service name"),
        ("services:\n  r: {image: x}\n", "inline service body"),
        ("services:\n  r:\n    image x\n", "is not a service key"),
        ("services:\n  r:\n    volumes: [a:/a]\n", "inline volumes list"),
        ("services:\n  r:\n    image:\n", "image key names nothing"),
        ("services:\n  r:\n    volumes:\n      - {type: bind}\n", "flow-style entry"),
        ("services:\n  r:\n    volumes:\n      - ${DIR:-./x}:/x\n", "contains an expansion"),
        ("services:\n  r:\n    volumes:\n      - /x\n", "is not source:target"),
        ("services:\n  r:\n    volumes:\n      - type: bind\n        source: ./x\n", "no target"),
        ("services:\n  r:\n    volumes:\n      - type: bind\n        oops\n", "is not a mount key"),
        ("services:\n  r:\n    tmpfs:\n      - relative/path\n", "is not an absolute container"),
        ("services:\n  r:\n    tmpfs:\n      - *nowhere\n", "names no anchor"),
        ("services:\n    r:\n      image: x\n  s:\n", "is indented under no service"),
        ("services:\n  r:\n    build: {context: ./b}\n", "inline build"),
        ("services:\n  r:\n    build:\n      - ./b\n", "is not a build key"),
        ("services:\n  r:\n    build:\n      args:\n        A: b\n", "build names no context"),
    ],
)
def test_a_shape_the_reader_was_not_taught_is_refused(text: str, message: str) -> None:
    with pytest.raises(ComposeServiceError, match=message):
        read_services(text)


def test_an_unclosed_mount_entry_at_the_end_of_a_file_is_still_refused() -> None:
    with pytest.raises(ComposeServiceError, match="no target"):
        read_services("services:\n  r:\n    volumes:\n      - type: bind\n        source: ./x\n")


def test_a_mount_key_outside_any_entry_is_refused() -> None:
    text = "services:\n  r:\n    volumes:\n      - a:/a\n        stray: 1\n"
    with pytest.raises(ComposeServiceError, match="is not a mount key"):
        read_services(text)


def test_an_anchor_that_carries_no_scalar_is_not_recorded_and_its_alias_is_refused() -> None:
    text = "x-common: &common\n  a: b\nservices:\n  r:\n    tmpfs:\n      - *common\n"
    with pytest.raises(ComposeServiceError, match="names no anchor"):
        read_services(text)


def test_a_comment_only_file_declares_nothing() -> None:
    assert read_services("# just a note\n\n") == (None, ())


def test_a_trailing_comment_beside_a_key_is_not_read_as_a_value() -> None:
    text = "services:\n  r: # the store\n    image: r\n    volumes: # the mounts\n      - a:/a\n"
    assert _one(text).covered == ("/a",)


def test_the_real_compose_files_are_all_readable() -> None:
    files = sorted((REPO_ROOT / "docker").glob("docker-compose*.yml"))
    read = {path.name: read_services(path.read_text(encoding="utf-8")) for path in files}
    assert len(read) >= 8, sorted(read)
    services = [service for found in read.values() for service in found.services]
    assert sum(service.defines for service in services) >= 8, services
    assert sum(len(service.covered) for service in services) >= 12, services


def test_the_real_build_stanzas_are_read_in_both_forms() -> None:
    files = sorted((REPO_ROOT / "docker").glob("docker-compose*.yml"))
    read = {path.name: read_services(path.read_text(encoding="utf-8")) for path in files}
    builds = {
        f"{name}:{service.name}": service.build
        for name, found in read.items()
        for service in found.services
        if service.build is not None
    }
    assert builds == {
        "docker-compose.yml:brain": Build("./brain", DEFAULT_DOCKERFILE),
        "docker-compose.email.yml:mcp-email": Build("./brain", DEFAULT_DOCKERFILE),
        "docker-compose.gpu.yml:model-host": Build("./brain", "Dockerfile.modelhost"),
    }


def test_the_probe_file_really_covers_dovecots_two_declarations_through_its_anchors() -> None:
    text = (REPO_ROOT / "docker" / "docker-compose.imap-probe.yml").read_text(encoding="utf-8")
    probe = read_services(text).services[0]
    assert {"/srv/mail", "/etc/dovecot"} <= set(probe.covered)
