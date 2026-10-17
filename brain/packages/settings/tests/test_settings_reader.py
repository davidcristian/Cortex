import traceback
from typing import Self

import pytest
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from cortex_settings import ConfigError, read_settings


class _Probe(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PROBE_")

    port: int = Field(default=1, gt=0)
    zone: str = "UTC"
    names: list[str] = []
    gain: float = Field(default=1.0, validation_alias="PROBE_GAIN_LEVEL")
    tags: list[str] = Field(default=[], validation_alias="PROBE_TAG_LIST")
    switch: bool = False

    @field_validator("zone")
    @classmethod
    def _known_zone(cls, value: str) -> str:
        if value != "UTC":
            msg = f"unknown zone {value!r}"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def _switch_needs_names(self) -> Self:
        if self.switch and not self.names:
            msg = "PROBE_NAMES is required when PROBE_SWITCH=true"
            raise ValueError(msg)
        return self


def _refusal(monkeypatch: pytest.MonkeyPatch, **env: str) -> ConfigError:
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    with pytest.raises(ConfigError) as caught:
        read_settings(_Probe)
    return caught.value


@pytest.mark.parametrize(
    ("variable", "value"),
    [("PROBE_PORT", "8o80"), ("PROBE_GAIN_LEVEL", "loud"), ("PROBE_ZONE", "Mars/Olympus")],
)
def test_a_refused_value_is_named_by_its_variable_and_never_shown(
    monkeypatch: pytest.MonkeyPatch, variable: str, value: str
) -> None:
    refusal = _refusal(monkeypatch, **{variable: value})
    assert str(refusal).startswith(f"{variable}: ")
    assert value not in "".join(traceback.format_exception(refusal))


def test_a_validator_message_has_its_input_replaced(monkeypatch: pytest.MonkeyPatch) -> None:
    refusal = _refusal(monkeypatch, PROBE_ZONE="Mars/Olympus")
    assert str(refusal) == "PROBE_ZONE: unknown zone '<value>'"


def test_an_empty_value_leaves_the_reason_whole(monkeypatch: pytest.MonkeyPatch) -> None:
    assert str(_refusal(monkeypatch, PROBE_ZONE="")) == "PROBE_ZONE: unknown zone ''"


def test_a_built_in_rule_is_named_in_pydantic_words(monkeypatch: pytest.MonkeyPatch) -> None:
    assert (
        str(_refusal(monkeypatch, PROBE_PORT="0")) == "PROBE_PORT: Input should be greater than 0"
    )


def test_every_refused_variable_is_named(monkeypatch: pytest.MonkeyPatch) -> None:
    refusal = _refusal(monkeypatch, PROBE_PORT="0", PROBE_GAIN_LEVEL="loud")
    assert str(refusal) == (
        "PROBE_PORT: Input should be greater than 0; "
        "PROBE_GAIN_LEVEL: Input should be a valid number, unable to parse string as a number"
    )


def test_a_value_that_is_not_json_is_named_as_such(monkeypatch: pytest.MonkeyPatch) -> None:
    refusal = _refusal(monkeypatch, PROBE_NAMES="[alpha")
    assert str(refusal) == "PROBE_NAMES is not valid JSON"
    assert "[alpha" not in str(refusal)


def test_an_aliased_value_that_is_not_json_is_named_by_its_alias(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert str(_refusal(monkeypatch, PROBE_TAG_LIST="[alpha")) == "PROBE_TAG_LIST is not valid JSON"


def test_a_refusal_of_the_whole_class_keeps_its_own_words_and_hides_the_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    refusal = _refusal(monkeypatch, PROBE_SWITCH="true", PROBE_ZONE="UTC", PROBE_PORT="4417")
    assert str(refusal) == "PROBE_NAMES is required when PROBE_SWITCH=true"
    assert "4417" not in "".join(traceback.format_exception(refusal))


def test_a_valid_environment_reads_through(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROBE_PORT", "8080")
    monkeypatch.setenv("PROBE_GAIN_LEVEL", "2.5")
    probe = read_settings(_Probe)
    assert (probe.port, probe.gain) == (8080, 2.5)
