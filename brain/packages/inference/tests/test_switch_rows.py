"""CI-side gate on the injection harness's rows: the argv each starts with and the body it posts."""

from dataclasses import replace

import pytest
from test_injection_defense_live import (
    BRAIN_CANDIDATES,
    BRAIN_TIER,
    BUDGET_ALONE,
    CORTEX_CANDIDATES,
    CORTEX_TIER,
    CPU_PLACEMENT,
    GPU_PLACEMENT,
    MODELS,
    PLACEMENTS,
    REQUEST_KEY,
    SHIPPED_BUDGET,
    SHIPPED_REASONING_OFF,
    SHIPPED_SWITCH,
    SUBAGENT_CANDIDATES,
    SUBAGENT_TIER,
    SWITCHES,
    THINKING_ON,
    VISION_MODELS,
    Model,
    completion_body,
    lever,
    repeat_of,
    server_argv,
    switch_for,
    template_kwargs,
    tier_args,
)

from cortex_core import PlacementTarget
from cortex_model_manager import llama_server_argv
from cortex_orchestrator.config_subagents import DEFAULT_CPU_BUDGET, DEFAULT_MEM_BUDGET_GB

_TEMPLATE_KWARGS_FLAG = "--chat-template-kwargs"
_REASONING_BUDGET_FLAG = "--reasoning-budget"

# A row's own inputs, which nothing here is about: the switch is the only variable, so the
# messages and tools are a fixed stand-in the two bodies are compared over.
_MESSAGES: list[dict[str, object]] = [{"role": "user", "content": "summarise this"}]
_TOOLS: list[dict[str, object]] = [{"type": "function", "function": {"name": "read_file"}}]
_MAX_TOKENS = 1600

# What the sidecar's builder puts first, which the harness drops because the image's entrypoint
# is the server; any word does here, since only what follows it is compared.
_ANY_BINARY = "llama-server"

_THINKING_OFF = [model for model in MODELS if not model.thinking]


def test_the_sidecar_still_declares_both_halves_of_the_reasoning_off_pair() -> None:
    """The tier the shipped row copies is started with the kwarg and the budget, in that order."""
    assert SHIPPED_REASONING_OFF[0] == _TEMPLATE_KWARGS_FLAG, SHIPPED_REASONING_OFF
    assert SHIPPED_REASONING_OFF[2] == _REASONING_BUDGET_FLAG, SHIPPED_REASONING_OFF
    assert len(SHIPPED_REASONING_OFF) == 4, SHIPPED_REASONING_OFF


def test_the_request_key_renders_what_the_tiers_own_flag_tells_its_template() -> None:
    """The key a request-key row sends is the flag's own JSON, decoded rather than retyped."""
    assert REQUEST_KEY.request_key == template_kwargs(SHIPPED_REASONING_OFF)
    assert REQUEST_KEY.request_key, REQUEST_KEY


def test_a_shipped_row_starts_its_server_with_the_tiers_reasoning_off_pair() -> None:
    """Every thinking-off row on the shipped switch carries the pair at the end of its argv."""
    for model in _THINKING_OFF:
        argv = server_argv(model, SHIPPED_BUDGET, SHIPPED_SWITCH)
        assert argv[-len(SHIPPED_REASONING_OFF) :] == SHIPPED_REASONING_OFF, model.label


def test_a_request_key_row_starts_its_server_with_neither_flag() -> None:
    """The row that reproduces every subagent number published before the switch became a row."""
    for model in _THINKING_OFF:
        argv = server_argv(model, SHIPPED_BUDGET, REQUEST_KEY)
        assert _TEMPLATE_KWARGS_FLAG not in argv, model.label
        assert _REASONING_BUDGET_FLAG not in argv, model.label


def test_the_switch_rows_differ_by_the_lever_and_by_nothing_else() -> None:
    """One row moves the pair onto the argv and the key off the request, one moves half the pair
    there; nothing else moves.
    """
    for model in _THINKING_OFF:
        keyed = server_argv(model, SHIPPED_BUDGET, REQUEST_KEY)
        shipped = server_argv(model, SHIPPED_BUDGET, SHIPPED_SWITCH)
        budgeted = server_argv(model, SHIPPED_BUDGET, BUDGET_ALONE)
        assert shipped == (*keyed, *SHIPPED_REASONING_OFF), model.label
        assert budgeted == (*keyed, *BUDGET_ALONE.argv), model.label
    bodies = {
        switch.label: completion_body(_MESSAGES, _TOOLS, switch=switch, max_tokens=_MAX_TOKENS)
        for switch in SWITCHES
    }
    keyed_body = bodies[REQUEST_KEY.label]
    shipped_body = bodies[SHIPPED_SWITCH.label]
    assert set(keyed_body) - set(shipped_body) == {"chat_template_kwargs"}
    assert {key: keyed_body[key] for key in shipped_body} == shipped_body
    assert bodies[BUDGET_ALONE.label] == shipped_body


def test_the_budget_alone_row_carries_the_budget_half_and_not_the_kwarg() -> None:
    """The third cell is the pair's second half on the argv, at the tier's own count, and no key."""
    at = SHIPPED_REASONING_OFF.index(_REASONING_BUDGET_FLAG)
    assert BUDGET_ALONE.argv == (_REASONING_BUDGET_FLAG, SHIPPED_REASONING_OFF[at + 1])
    assert BUDGET_ALONE.request_key is None
    assert BUDGET_ALONE in SWITCHES
    for model in _THINKING_OFF:
        argv = server_argv(model, SHIPPED_BUDGET, BUDGET_ALONE)
        assert _TEMPLATE_KWARGS_FLAG not in argv, model.label
        assert argv[-2:] == BUDGET_ALONE.argv, model.label


def test_a_lever_is_read_by_its_flag_and_a_missing_one_refuses() -> None:
    """A lever is the flag and the value after it, and an argv without the flag raises."""
    assert lever(("--a", "1", "--b", "2"), "--b") == ("--b", "2")
    with pytest.raises(LookupError):
        lever(("--a", "1"), "--b")
    with pytest.raises(LookupError):
        lever(("--a", "1", "--b"), "--b")


def test_a_shipped_row_sends_no_request_key_and_a_keyed_row_sends_one() -> None:
    """The lever really is on one side or the other, in the body the row posts."""
    shipped = completion_body(_MESSAGES, _TOOLS, switch=SHIPPED_SWITCH, max_tokens=_MAX_TOKENS)
    keyed = completion_body(_MESSAGES, _TOOLS, switch=REQUEST_KEY, max_tokens=_MAX_TOKENS)
    assert "chat_template_kwargs" not in shipped
    assert keyed["chat_template_kwargs"] == dict(template_kwargs(SHIPPED_REASONING_OFF))


def test_a_thinking_on_tier_pulls_neither_lever_whichever_row_asks() -> None:
    """A tier measured deliberating is measured deliberating under every switch."""
    thinking = [model for model in MODELS if model.thinking]
    assert thinking, MODELS
    for model in (*thinking, *VISION_MODELS):
        for switch in SWITCHES:
            assert switch_for(model, switch) is THINKING_ON, f"{model.label}/{switch.label}"
    assert THINKING_ON.argv == ()
    assert THINKING_ON.request_key is None


def test_the_image_arms_rows_post_what_they_posted_before_the_switch_became_a_row() -> None:
    """Every seeing row's body is unchanged, so the published pixel matrices stay reproducible."""
    for model in VISION_MODELS:
        body = completion_body(_MESSAGES, _TOOLS, switch=switch_for(model), max_tokens=None)
        assert "chat_template_kwargs" not in body, model.label
        assert "max_tokens" not in body, model.label
        assert server_argv(model, SHIPPED_BUDGET, switch_for(model)) == server_argv(
            model, SHIPPED_BUDGET
        ), model.label


def test_the_default_switch_is_the_row_every_published_subagent_number_was_taken_under() -> None:
    """A caller naming no switch gets the request key, which is what the old rows sent."""
    subagent: Model = _THINKING_OFF[0]
    assert switch_for(subagent) is REQUEST_KEY
    assert server_argv(subagent, SHIPPED_BUDGET) == server_argv(
        subagent, SHIPPED_BUDGET, REQUEST_KEY
    )
    assert server_argv(subagent, SHIPPED_BUDGET, REQUEST_KEY) == server_argv(
        subagent, SHIPPED_BUDGET, REQUEST_KEY, GPU_PLACEMENT
    )


def test_a_shipped_row_is_its_tiers_own_command_line() -> None:
    """A text-only row on the shipped switch is the tier's argv with the artifact and port swapped.
    """
    for model in MODELS:
        tier = tier_args(model.tier)
        started = server_argv(model, SHIPPED_BUDGET, switch_for(model, SHIPPED_SWITCH))
        artifact = started[started.index("--model") + 1]
        port = int(started[started.index("--port") + 1])
        own = llama_server_argv(_ANY_BINARY, replace(tier, model_path=artifact, port=port))
        assert started == own[1:], model.label
        assert artifact.endswith(model.gguf), model.label


def test_the_cpu_row_offloads_no_layer_and_changes_nothing_else() -> None:
    """The CPU row is the card row with the layer count the core hands the host for that server."""
    for model in _THINKING_OFF:
        tier = tier_args(model.tier)
        card = server_argv(model, SHIPPED_BUDGET, SHIPPED_SWITCH, GPU_PLACEMENT)
        cpu = server_argv(model, SHIPPED_BUDGET, SHIPPED_SWITCH, CPU_PLACEMENT)
        at = card.index("-ngl") + 1
        assert card[at] == str(tier.ngl), model.label
        assert cpu[at] == str(PlacementTarget.CPU.ngl), model.label
        assert cpu[:at] + cpu[at + 1 :] == card[:at] + card[at + 1 :], model.label
    assert GPU_PLACEMENT.on_card
    assert not CPU_PLACEMENT.on_card
    assert GPU_PLACEMENT.image != CPU_PLACEMENT.image
    assert "--gpus" in GPU_PLACEMENT.reservation
    memory = f"{DEFAULT_MEM_BUDGET_GB}g"
    assert CPU_PLACEMENT.reservation == (
        "--cpus",
        str(DEFAULT_CPU_BUDGET),
        "--memory",
        memory,
        "--memory-swap",
        memory,
    )
    assert [placement.label for placement in PLACEMENTS] == [
        PlacementTarget.GPU.value,
        PlacementTarget.CPU.value,
    ]


def test_which_rows_are_a_models_own() -> None:
    """A thinking-off model has a row per switch on the card and a shipped row on the CPU; a
    thinking-on model has one row, under the shipped switch on the card.
    """
    thinking = [model for model in MODELS if model.thinking]
    assert thinking, MODELS
    for model in MODELS:
        own = {
            (switch.label, placement.label)
            for switch in SWITCHES
            for placement in PLACEMENTS
            if repeat_of(model, switch, placement) is None
        }
        card = {(switch.label, GPU_PLACEMENT.label) for switch in SWITCHES}
        expected = (
            {(SHIPPED_SWITCH.label, GPU_PLACEMENT.label)}
            if model.thinking
            else card | {(SHIPPED_SWITCH.label, CPU_PLACEMENT.label)}
        )
        assert own == expected, model.label


def test_thinking_follows_the_tier_and_each_lineup_names_its_own() -> None:
    """Whether a model thinks is read off the tier it is measured as, and no lineup is mis-tiered.

    A subagent candidate measured as the cortex tier would be started without the pair and read
    as deliberating on purpose, so its published row would be a row of another tier.
    """
    assert all(model.tier == CORTEX_TIER for model in (*CORTEX_CANDIDATES, *VISION_MODELS))
    assert all(model.tier == SUBAGENT_TIER for model in SUBAGENT_CANDIDATES)
    assert all(model.tier == BRAIN_TIER for model in BRAIN_CANDIDATES)
    assert all(model.thinking for model in (*CORTEX_CANDIDATES, *BRAIN_CANDIDATES))
    assert not any(model.thinking for model in SUBAGENT_CANDIDATES)


def test_a_tier_the_sidecar_does_not_declare_is_refused() -> None:
    """A model naming a tier the model host has no row for fails at the read, not at the card."""
    with pytest.raises(LookupError):
        tier_args("no-such-tier")
