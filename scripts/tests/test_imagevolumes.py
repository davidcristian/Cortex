"""Behaviour of the recorded image-volume table: the shape a row written by hand has to have.

The record is a measurement pasted into the tree, so what can go wrong with it here is not drift,
which `test_imagedrift.py` covers against a fake docker and `just image-volumes` against a real
one. It is a row written in a shape the gate would read as something else: a path that could never
match a mount, a table with no measured silences in it to tell an unasked image from a silent one,
or a row listed in an order that makes two readers disagree about whether it moved.
"""

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
