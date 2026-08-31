from imagevolumes import IMAGE_VOLUMES


def test_every_recorded_path_is_an_absolute_container_path() -> None:
    assert all(path.startswith("/") for row in IMAGE_VOLUMES.values() for path in row.volumes)


def test_the_record_holds_the_images_that_declare_nothing_too() -> None:
    silent = [reference for reference, row in IMAGE_VOLUMES.items() if not row.volumes]
    assert len(silent) >= 2, IMAGE_VOLUMES
    assert len(silent) < len(IMAGE_VOLUMES), IMAGE_VOLUMES


def test_each_rows_paths_are_written_in_the_order_docker_sorts_them() -> None:
    assert all(list(row.volumes) == sorted(row.volumes) for row in IMAGE_VOLUMES.values())
