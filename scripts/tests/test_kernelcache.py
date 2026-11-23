import pytest

from composeservices import read_services
from kernelcache import CACHE_VARIABLE, Lost, Source, kernel_caches

GPU = "docker/docker-compose.gpu.yml"

CARD = (
    "    deploy:\n"
    "      resources:\n"
    "        reservations:\n"
    "          devices:\n"
    "            - driver: nvidia\n"
    "              count: 1\n"
)


def _mount(target: str = "/srv/keep") -> str:
    return (
        f"    volumes:\n      - type: volume\n        source: kernels\n        target: {target}\n"
    )


def _env(value: str = "/srv/keep/kernels") -> str:
    return f"    environment:\n      {CACHE_VARIABLE}: {value}\n"


def _service(*parts: str, name: str = "host") -> str:
    return f"  {name}:\n    image: host:1\n" + "".join(parts)


PLAIN = "volumes:\n  kernels:\n"


def _source(*services: str, name: str = GPU, declared: str = PLAIN) -> Source:
    text = "services:\n" + "".join(services) + declared
    return Source(name, text, read_services(text))


def _judge(*parts: str) -> tuple[Lost, ...]:
    return kernel_caches([_source(_service(*parts))]).faults


def test_a_service_given_the_card_with_its_directory_under_a_mount_has_no_fault() -> None:
    kept = kernel_caches([_source(_service(_env(), _mount(), CARD))])
    assert kept.carded == 1
    assert kept.faults == ()


def test_a_service_given_the_card_that_sets_no_directory_is_reported() -> None:
    (fault,) = _judge(_mount(), CARD)
    assert (fault.path, fault.line) == (GPU, 2)
    assert f"service 'host' is given the card and no compose file sets {CACHE_VARIABLE}" in (
        fault.detail
    )


def test_a_directory_set_with_no_mount_at_all_is_reported() -> None:
    (fault,) = _judge(_env(), CARD)
    assert (fault.path, fault.line) == (GPU, 2)
    assert f"service 'host' sets {CACHE_VARIABLE} to '/srv/keep/kernels' and no compose" in (
        fault.detail
    )


@pytest.mark.parametrize(
    "value",
    ["/home/cortex/x", "/srv/keeps/kernels", "/srv/keep/../lib/kernels", "/srv"],
)
def test_a_directory_outside_every_mount_is_reported(value: str) -> None:
    (fault,) = _judge(_env(value), _mount(), CARD)
    assert f"to {value!r} and no compose file mounts anything at that directory" in fault.detail


@pytest.mark.parametrize("target", ["/srv/kee", "/srv/keep/kern", "/srv/keep/kernels/sub"])
def test_a_mount_beside_or_below_the_directory_does_not_contain_it(target: str) -> None:
    (fault,) = _judge(_env(), _mount(target), CARD)
    assert "mounts anything at that directory or above it" in fault.detail


@pytest.mark.parametrize("target", ["/srv/keep", "/srv/keep/kernels", "/srv/keep/", "/srv", "/"])
def test_a_mount_at_the_directory_or_above_it_contains_it(target: str) -> None:
    assert _judge(_env(), _mount(target), CARD) == ()


@pytest.mark.parametrize(
    ("written", "read"),
    [
        (
            '"${CUDA_CACHE_PATH:-/srv/keep/kernels}"',
            "${CUDA_CACHE_PATH:-/srv/keep/kernels}",
        ),
        ("/srv/keep/${NAME}", "/srv/keep/${NAME}"),
        ("srv/keep/kernels", "srv/keep/kernels"),
        ("", ""),
    ],
)
def test_a_directory_not_written_out_as_an_absolute_path_is_reported(
    written: str, read: str
) -> None:
    (fault,) = _judge(_env(written), _mount(), CARD)
    assert f"to {read!r}, which is not an absolute container path written out" in fault.detail


@pytest.mark.parametrize(
    "reservation",
    [
        CARD,
        CARD.replace("driver: nvidia", 'driver: "nvidia"'),
        "    runtime: nvidia\n",
        "    gpus: all\n",
    ],
)
def test_each_compose_form_that_gives_a_service_the_card_is_read(reservation: str) -> None:
    kept = kernel_caches([_source(_service(reservation))])
    assert kept.carded == 1
    assert [fault.line for fault in kept.faults] == [2]


@pytest.mark.parametrize(
    "body",
    [
        "    # - driver: nvidia\n",
        "    deploy:\n      resources:\n        reservations:\n          devices:\n"
        "            - driver: other\n",
        "    environment:\n      CORTEX_DRIVER: nvidia\n",
    ],
)
def test_a_service_not_given_the_card_needs_no_directory(body: str) -> None:
    assert kernel_caches([_source(_service(body))]) == (0, ())


def test_a_directory_set_without_the_card_still_needs_its_mount() -> None:
    kept = kernel_caches([_source(_service(_env()))])
    assert kept.carded == 0
    assert [fault.line for fault in kept.faults] == [2]


def test_a_reservation_belongs_to_the_service_it_is_written_under() -> None:
    plain = _service(name="plain")
    kept = kernel_caches([_source(plain, _service(_env(), _mount(), CARD))])
    assert kept == (1, ())


def test_another_services_directory_does_not_count_for_the_one_given_the_card() -> None:
    carded = _service(CARD, name="first")
    (fault,) = kernel_caches([_source(carded, _service(_env(), _mount()))]).faults
    assert fault.line == 2
    assert "service 'first' is given the card" in fault.detail


def test_a_blank_line_or_a_comment_at_any_indent_does_not_end_a_service_body() -> None:
    body = "\n# a note at the margin\n" + CARD
    assert kernel_caches([_source(_service(_env(), _mount(), body))]) == (1, ())


def test_a_top_level_key_ends_the_last_service_body() -> None:
    text = "services:\n" + _service() + "volumes:\n  kernels:\n    driver: nvidia\n"
    assert kernel_caches([Source(GPU, text, read_services(text))]) == (0, ())


def test_the_files_are_judged_together_as_compose_merges_them() -> None:
    base = _source(_service(_env()), name="docker/docker-compose.yml")
    overlay = _source(_service(_mount(), CARD))
    assert kernel_caches([base, overlay]) == (1, ())


def test_a_mount_in_one_file_still_counts_when_a_later_file_names_the_service() -> None:
    base = _source(_service(_mount()), name="docker/docker-compose.yml")
    overlay = _source(_service(_env(), CARD))
    assert kernel_caches([base, overlay]) == (1, ())


def test_every_file_that_sets_the_directory_is_judged_on_its_own_value() -> None:
    base = _source(_service(_env("/home/cortex/x")), name="docker/docker-compose.yml")
    overlay = _source(_service(_env(), _mount(), CARD))
    (fault,) = kernel_caches([base, overlay]).faults
    assert (fault.path, fault.line) == ("docker/docker-compose.yml", 2)
    assert "'/home/cortex/x'" in fault.detail


def test_a_file_whose_environment_cannot_be_read_is_a_fault_and_gives_nothing() -> None:
    listed = "    environment:\n      - A=b\n"
    kept = kernel_caches([_source(_service(listed, _mount(), CARD))])
    assert kept.carded == 0
    assert kept.faults == (
        Lost(GPU, 0, "line 5: an environment written as a list is not supported"),
    )


def _typed(kind: str, target: str = "/srv/keep", source: str = "") -> str:
    named = f"        source: {source}\n" if source else ""
    return f"      - type: {kind}\n{named}        target: {target}\n"


TMPFS_LIST = "    tmpfs:\n      - /srv/keep\n"


@pytest.mark.parametrize(
    "mount",
    [
        "    volumes:\n" + _typed("tmpfs"),
        TMPFS_LIST,
        "    volumes:\n" + _typed("volume"),
        "    volumes:\n" + _typed("image", source="host:1"),
        "    volumes:\n      - target: /srv/keep\n        source: kernels\n",
    ],
)
def test_a_mount_a_new_container_gets_empty_does_not_keep_the_kernels(mount: str) -> None:
    (fault,) = _judge(_env(), mount, CARD)
    assert (fault.path, fault.line) == (GPU, 2)
    assert (
        f"sets {CACHE_VARIABLE} to '/srv/keep/kernels' and the mount over it at '/srv/keep' "
        "is not a named volume or a bind"
    ) in fault.detail


@pytest.mark.parametrize(
    "mount",
    [
        "    volumes:\n" + _typed("bind", source="./kernels"),
        "    volumes:\n" + _typed("volume", source="kernels"),
        "    volumes:\n      - kernels:/srv/keep\n",
        "    volumes:\n      - ./kernels:/srv/keep:rw\n",
    ],
)
def test_a_named_volume_or_a_bind_in_either_syntax_keeps_the_kernels(mount: str) -> None:
    assert _judge(_env(), mount, CARD) == ()


def test_a_tmpfs_below_a_volume_and_over_the_directory_is_the_mount_that_is_judged() -> None:
    nested = _mount() + _typed("tmpfs", "/srv/keep/kernels")
    (fault,) = _judge(_env(), nested, CARD)
    assert "the mount over it at '/srv/keep/kernels' is not a named volume" in fault.detail


def test_a_volume_below_a_tmpfs_and_over_the_directory_keeps_the_kernels() -> None:
    nested = "    volumes:\n" + _typed("tmpfs", "/srv") + _typed("volume", "/srv//keep/", "kernels")
    assert _judge(_env(), nested, CARD) == ()


def test_the_deepest_mount_is_found_by_its_path_parts_and_not_by_its_length() -> None:
    long = "    volumes:\n" + _typed("tmpfs", "/srv" + "/" * 20 + "keep")
    assert _judge(_env(), long + _typed("volume", "/srv/keep/kernels", "kernels"), CARD) == ()


def test_a_tmpfs_beside_the_directory_changes_nothing() -> None:
    assert _judge(_env(), _mount() + _typed("tmpfs", "/srv/keep/other"), CARD) == ()


@pytest.mark.parametrize("order", [(0, 1), (1, 0)])
def test_a_tmpfs_any_file_mounts_at_the_volumes_target_is_reported(order: tuple[int, int]) -> None:
    mounts = (_mount(), TMPFS_LIST)
    base = _source(_service(_env(), mounts[order[0]]), name="docker/docker-compose.yml")
    overlay = _source(_service(mounts[order[1]], CARD))
    (fault,) = kernel_caches([base, overlay]).faults
    assert fault.path == "docker/docker-compose.yml"
    assert "is not a named volume or a bind in every compose file" in fault.detail


DRIVEN = "the named volume 'kernels' over it at '/srv/keep' is declared in no top-level volumes"


@pytest.mark.parametrize(
    "declared",
    [
        "",
        "volumes:\n  other:\n",
        PLAIN + "    driver: local\n    driver_opts:\n      type: tmpfs\n      device: tmpfs\n",
        PLAIN + "    external: true\n",
        "volumes:\n  kernels: {}\n",
    ],
)
@pytest.mark.parametrize("mount", [_mount(), "    volumes:\n      - kernels:/srv/keep\n"])
def test_a_named_volume_not_declared_plainly_does_not_keep_the_kernels(
    declared: str, mount: str
) -> None:
    (fault,) = kernel_caches([_source(_service(_env(), mount, CARD), declared=declared)]).faults
    assert (fault.path, fault.line) == (GPU, 2)
    assert f"sets {CACHE_VARIABLE} to '/srv/keep/kernels' and {DRIVEN}" in fault.detail


def test_a_named_volume_with_a_name_and_labels_keeps_the_kernels() -> None:
    declared = PLAIN + "    name: cortex-kernels\n    labels:\n      driver: tmpfs\n"
    assert kernel_caches([_source(_service(_env(), _mount(), CARD), declared=declared)]) == (1, ())


@pytest.mark.parametrize("order", [(0, 1), (1, 0)])
def test_a_driver_any_file_declares_for_the_volume_is_reported(order: tuple[int, int]) -> None:
    declared = (PLAIN, PLAIN + "    driver: local\n")
    base = _source(_service(_env()), name="docker/docker-compose.yml", declared=declared[order[0]])
    overlay = _source(_service(_mount(), CARD), declared=declared[order[1]])
    (fault,) = kernel_caches([base, overlay]).faults
    assert DRIVEN in fault.detail


def test_a_declaration_in_another_file_counts_for_the_volume() -> None:
    base = _source(_service(_env()), name="docker/docker-compose.yml")
    overlay = _source(_service(_mount(), CARD), declared="")
    assert kernel_caches([base, overlay]) == (1, ())


def test_only_the_named_volume_over_the_directory_is_judged() -> None:
    other = "      - type: volume\n        source: other\n        target: /srv/elsewhere\n"
    assert _judge(_env(), _mount() + other, CARD) == ()


def test_a_bind_below_a_driven_volume_and_over_the_directory_keeps_the_kernels() -> None:
    bind = _typed("bind", "/srv/keep/kernels", "./kernels")
    driven = PLAIN + "    driver: local\n"
    service = _service(_env(), _mount() + bind, CARD)
    assert kernel_caches([_source(service, declared=driven)]) == (1, ())
