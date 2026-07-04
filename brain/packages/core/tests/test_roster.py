"""Behavior tests for the subagent roster and its ADR-0017 resolution boundary (ADR-0018)."""

import pytest

from cortex_core import (
    EchoInferenceBackend,
    PlacementRequest,
    PlacementTarget,
    ResourceBudgetScheduler,
    SubagentProfile,
    SubagentResources,
    SubagentRoster,
    VramBudgetPlacer,
)


def _profile(model: str, description: str = "") -> SubagentProfile:
    echo = EchoInferenceBackend()
    return SubagentProfile(
        resources=SubagentResources(
            backends={PlacementTarget.GPU: echo, PlacementTarget.CPU: echo},
            scheduler=ResourceBudgetScheduler(4.0, 8.0),
            placer=VramBudgetPlacer(soft_cap_gb=14.0, cortex_reservation_gb=11.0),
            request=PlacementRequest(model, vram_gb=2.0, cpus=2.0, memory_gb=2.0),
        ),
        description=description,
    )


def _roster() -> SubagentRoster:
    return SubagentRoster(
        entries={"robust": _profile("robust"), "fast": _profile("fast", "small and quick")},
        default="robust",
    )


def test_an_empty_roster_is_a_wiring_error() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        SubagentRoster(entries={}, default="robust")


def test_a_default_outside_the_entries_is_a_wiring_error() -> None:
    with pytest.raises(ValueError, match="'ghost' is not a roster entry"):
        SubagentRoster(entries={"robust": _profile("robust")}, default="ghost")


def test_profile_description_defaults_empty() -> None:
    assert _profile("m").description == ""


# The ADR-0017 matrix: any spawn path that can carry untrusted content resolves to the robust
# default, whatever was requested; the cortex's pick is honored only clean + tool-less.
@pytest.mark.parametrize(
    ("requested", "tainted", "tools_enabled", "expected"),
    [
        ("fast", True, False, "robust"),  # tainted turn -> forced robust (rule 2a)
        ("fast", False, True, "robust"),  # tools-enabled subagent -> forced robust (rule 2b)
        ("fast", True, True, "robust"),  # both signals -> forced robust
        ("ghost", True, False, "robust"),  # unknown + untrusted path -> still the safe default
        ("fast", False, False, "fast"),  # clean + tool-less -> the pick is honored
        ("", False, False, "robust"),  # no pick -> the default
        ("robust", False, False, "robust"),  # picking the default explicitly is fine
    ],
)
def test_resolve_pins_every_untrusted_path_to_the_default(
    requested: str, *, tainted: bool, tools_enabled: bool, expected: str
) -> None:
    resolved = _roster().resolve(requested, tainted=tainted, tools_enabled=tools_enabled)
    assert resolved == expected


def test_resolve_fails_closed_on_an_unknown_model_on_a_clean_tool_less_path() -> None:
    assert _roster().resolve("ghost", tainted=False, tools_enabled=False) is None
