"""Tests for the shape of the hand-written rows in the recorded image-volume table.

Drift between the record and a real docker is covered elsewhere: `test_imagedrift.py` checks it
against a fake docker, and `just image-volumes` against a real one. What is left here is a row
written in a shape the gate would misread: a container path that can never match a mount, a table
holding no zero-volume row, or paths listed in an order that makes two readers disagree about
whether a row moved.
"""

from imagevolumes import IMAGE_VOLUMES


def test_every_recorded_path_is_an_absolute_container_path() -> None:
    """Every recorded path is absolute, since a relative path can never match a mount target."""
    assert all(path.startswith("/") for row in IMAGE_VOLUMES.values() for path in row.volumes)


def test_the_record_holds_the_images_that_declare_nothing_too() -> None:
    """Some rows record no volumes and some record volumes.

    An empty row records that the image declares nothing, which is a different fact from an image
    that was never measured, so the table has to contain both kinds of row.
    """
    silent = [reference for reference, row in IMAGE_VOLUMES.items() if not row.volumes]
    assert len(silent) >= 2, IMAGE_VOLUMES
    assert len(silent) < len(IMAGE_VOLUMES), IMAGE_VOLUMES


def test_each_rows_paths_are_written_in_the_order_docker_sorts_them() -> None:
    """Each row's paths are sorted, so a reader scanning the table sees one consistent order."""
    assert all(list(row.volumes) == sorted(row.volumes) for row in IMAGE_VOLUMES.values())
