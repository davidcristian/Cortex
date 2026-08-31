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


@pytest.mark.parametrize(
    ("requested", "tainted", "tools_enabled", "expected"),
    [
        ("fast", True, False, "robust"),
        ("fast", False, True, "robust"),
        ("fast", True, True, "robust"),
        ("ghost", True, False, "robust"),
        ("fast", False, False, "fast"),
        ("", False, False, "robust"),
        ("robust", False, False, "robust"),
    ],
)
def test_resolve_pins_every_untrusted_path_to_the_default(
    requested: str, *, tainted: bool, tools_enabled: bool, expected: str
) -> None:
    resolved = _roster().resolve(requested, tainted=tainted, tools_enabled=tools_enabled)
    assert resolved == expected


def test_resolve_fails_closed_on_an_unknown_model_on_a_clean_tool_less_path() -> None:
    assert _roster().resolve("ghost", tainted=False, tools_enabled=False) is None
