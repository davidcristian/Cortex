"""Behaviour of the recorded image-volume table: the shape a row written by hand has to have."""

from imagevolumes import IMAGE_VOLUMES


def test_every_recorded_path_is_an_absolute_container_path() -> None:
    """A relative row could never match a mount target, so the gate would read it as a leak."""
    assert all(path.startswith("/") for row in IMAGE_VOLUMES.values() for path in row.volumes)


def test_the_record_holds_the_images_that_declare_nothing_too() -> None:
    """A measured silence is what tells an image nobody has asked about from one that answered."""
    silent = [reference for reference, row in IMAGE_VOLUMES.items() if not row.volumes]
    assert len(silent) >= 2, IMAGE_VOLUMES
    assert len(silent) < len(IMAGE_VOLUMES), IMAGE_VOLUMES


def test_each_rows_paths_are_written_in_the_order_docker_sorts_them() -> None:
    """A tidiness the comparison does not need and a reader does: one row, one obvious order."""
    assert all(list(row.volumes) == sorted(row.volumes) for row in IMAGE_VOLUMES.values())
