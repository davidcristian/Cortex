import pytest

from cortex_orchestrator.dsn import authority_is_readable


@pytest.mark.parametrize(
    "dsn",
    [
        "postgresql://cortex:hunter@postgres:5432/cortex",
        "postgresql://cortex:hunter@postgres/cortex",
        "postgresql://cortex:hunter@postgres:/cortex",
        "postgresql://postgres:5432/cortex",
        "postgresql://cortex:hunter@[::1]:5432/cortex",
        "postgresql:///cortex?host=/var/run/postgresql",
        "postgresql://cortex:hunter@db1:5432,db2:5433/cortex",
        "postgresql://cortex:hunter@db:%35%34%33%32/cortex",
        "postgresql://postgres:5432/cortex?user=cortex@example.com",
        "redis://:p%2Fq%40r@redis:6379/0",
    ],
)
def test_authorities_the_driver_reads(dsn: str) -> None:
    assert authority_is_readable(dsn)


# A `/` inside the password ends the authority, so what follows is read as a port and the
# driver's `int()` fails naming it, or reads it and prints it in its connection error.
@pytest.mark.parametrize(
    "dsn",
    [
        "postgresql://cortex:hun/ter@postgres:5432/cortex",
        "postgresql://cortex:pw/5432@postgres:5432/cortex",
        "postgresql://cortex:hunter@db1:5432,db2:no/cortex",
        "postgresql://cortex:hunter@db:54 32/cortex",
        "redis://cortex:7/hunter@redis:6379/0",
        "redis://:2024/hunter@redis:6379/0",
        "redis://:7?hunter@redis:6379/0",
        "redis://:7#hunter@redis:6379/0",
    ],
)
def test_authorities_the_driver_cannot_read(dsn: str) -> None:
    assert not authority_is_readable(dsn)
