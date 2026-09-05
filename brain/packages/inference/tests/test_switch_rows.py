"""CI-side gate on the injection harness's rows: the argv each starts with and the body it posts.

The measurement needs a GPU, but which lever each row pulls and where its server runs do not:
both are properties of the command line the row starts with and of the body it posts, and both
can be read here in a second. That reading is what the rows are for. A thinking-off tier is told
to stop deliberating in two separate places, the server's own flags and the request's
``chat_template_kwargs`` key, and the shipped stack pulls the first while this harness pulled the
second on every subagent number it published before 2026-09-04 (ADR-0004's switch-row addendum,
ADR-0005's thinking-lever addendum). The subagent tier is also placed on the card or on the CPU
per spawn, and every number this harness published before 2026-09-05 was a card number (ADR-0004's
placement-row addendum). A shipped row that quietly stopped carrying the flags, a request-key row
that started carrying them, or a CPU row that offloaded a layer would go on printing a matrix
under the other row's name and nothing would say so.

The pair and the head of every command line are read off ``ModelHostConfig`` rather than typed
into the harness, so most of what is held here is that the harness spends what it read. The one
claim about the sidecar is that its subagent tier still declares both flags: a tier that emitted
neither would make the shipped row a row with no lever in it at all, which is the drift this file
exists to catch.
"""

from dataclasses import replace

import pytest
from test_injection_defense_live import (
    BRAIN_CANDIDATES,
    BRAIN_TIER,
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
    repeat_of,
    server_argv,
    switch_for,
    template_kwargs,
    tier_args,
)

from cortex_core import PlacementTarget
from cortex_model_manager import llama_server_argv
from cortex_orchestrator.config_subagents import DEFAULT_CPU_BUDGET

# The two flags a subagent server is started with, named here because naming them is the whole of
# what this file claims about the sidecar. A rename on that side fails this rather than passing:
# llama.cpp has already deprecated the second spelling once, and the successor renders what the
# first renders, so a tier that moved to it would leave every "shipped" row measuring a lever it
# no longer pulls.
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
    """The tier the shipped row copies is started with the kwarg and the budget, in that order.

    The order is held because the pair is spent as a run of argv items and llama.cpp takes the
    last spelling of a repeated flag, so a pair that arrived reordered would be a different
    command line from the one the compose servers write.
    """
    assert SHIPPED_REASONING_OFF[0] == _TEMPLATE_KWARGS_FLAG, SHIPPED_REASONING_OFF
    assert SHIPPED_REASONING_OFF[2] == _REASONING_BUDGET_FLAG, SHIPPED_REASONING_OFF
    assert len(SHIPPED_REASONING_OFF) == 4, SHIPPED_REASONING_OFF


def test_the_request_key_renders_what_the_tiers_own_flag_tells_its_template() -> None:
    """The key a request-key row sends is the flag's own JSON, decoded rather than retyped.

    The two are one answer under two spellings, so a harness that typed the key would keep
    sending the old one after the tier changed what it tells its template, and the two rows would
    stop being two routes to one place.
    """
    assert REQUEST_KEY.request_key == template_kwargs(SHIPPED_REASONING_OFF)
    assert REQUEST_KEY.request_key, REQUEST_KEY


def test_a_shipped_row_starts_its_server_with_the_tiers_reasoning_off_pair() -> None:
    """Every thinking-off row on the shipped switch carries the pair at the end of its argv."""
    for model in _THINKING_OFF:
        argv = server_argv(model, SHIPPED_BUDGET, SHIPPED_SWITCH)
        assert argv[-len(SHIPPED_REASONING_OFF) :] == SHIPPED_REASONING_OFF, model.label


def test_a_request_key_row_starts_its_server_with_neither_flag() -> None:
    """The row that reproduces every subagent number published before the switch became a row.

    Those rows ran on a server started with no reasoning flag at all, so a request-key row that
    picked one up would no longer replicate them and the comparison between the two switches
    would have two variables in it.
    """
    for model in _THINKING_OFF:
        argv = server_argv(model, SHIPPED_BUDGET, REQUEST_KEY)
        assert _TEMPLATE_KWARGS_FLAG not in argv, model.label
        assert _REASONING_BUDGET_FLAG not in argv, model.label


def test_the_two_switch_rows_differ_by_the_lever_and_by_nothing_else() -> None:
    """One row moves the pair onto the argv and the key off the request; nothing else moves.

    This is what makes the pair of rows a comparison. If the bodies differed in a cap or the
    command lines in a context size as well, a matrix that moved between them would not say which
    change moved it.
    """
    for model in _THINKING_OFF:
        keyed = server_argv(model, SHIPPED_BUDGET, REQUEST_KEY)
        shipped = server_argv(model, SHIPPED_BUDGET, SHIPPED_SWITCH)
        assert shipped == (*keyed, *SHIPPED_REASONING_OFF), model.label
    bodies = {
        switch.label: completion_body(_MESSAGES, _TOOLS, switch=switch, max_tokens=_MAX_TOKENS)
        for switch in SWITCHES
    }
    keyed_body = bodies[REQUEST_KEY.label]
    shipped_body = bodies[SHIPPED_SWITCH.label]
    assert set(keyed_body) - set(shipped_body) == {"chat_template_kwargs"}
    assert {key: keyed_body[key] for key in shipped_body} == shipped_body


def test_a_shipped_row_sends_no_request_key_and_a_keyed_row_sends_one() -> None:
    """The lever really is on one side or the other, in the body the row posts."""
    shipped = completion_body(_MESSAGES, _TOOLS, switch=SHIPPED_SWITCH, max_tokens=_MAX_TOKENS)
    keyed = completion_body(_MESSAGES, _TOOLS, switch=REQUEST_KEY, max_tokens=_MAX_TOKENS)
    assert "chat_template_kwargs" not in shipped
    assert keyed["chat_template_kwargs"] == dict(template_kwargs(SHIPPED_REASONING_OFF))


def test_a_thinking_on_tier_pulls_neither_lever_whichever_row_asks() -> None:
    """A tier measured deliberating is measured deliberating under every switch.

    The cortex and the deep tier are the models whose published rows say what the framing does
    with thinking on, so a switch reaching them would silently re-measure those rows against a
    model told to stop.
    """
    thinking = [model for model in MODELS if model.thinking]
    assert thinking, MODELS
    for model in (*thinking, *VISION_MODELS):
        for switch in SWITCHES:
            assert switch_for(model, switch) is THINKING_ON, f"{model.label}/{switch.label}"
    assert THINKING_ON.argv == ()
    assert THINKING_ON.request_key is None


def test_the_image_arms_rows_post_what_they_posted_before_the_switch_became_a_row() -> None:
    """Every seeing row's body is unchanged, so the published pixel matrices stay reproducible.

    The image arm runs the cortex tier alone, which thinks on purpose, so its request carries no
    key and its server no flag; asserted rather than assumed, because those rows are read against
    numbers taken before this file existed.
    """
    for model in VISION_MODELS:
        body = completion_body(_MESSAGES, _TOOLS, switch=switch_for(model), max_tokens=None)
        assert "chat_template_kwargs" not in body, model.label
        assert "max_tokens" not in body, model.label
        assert server_argv(model, SHIPPED_BUDGET, switch_for(model)) == server_argv(
            model, SHIPPED_BUDGET
        ), model.label


def test_the_default_switch_is_the_row_every_published_subagent_number_was_taken_under() -> None:
    """A caller naming no switch gets the request key, which is what the old rows sent.

    ``server_argv`` defaults the other way, to no flag at all, and the two defaults together are
    exactly the cell this harness measured before it could be handed a tier's argv. The default
    placement is the card, for the same reason: every published row is a card row.
    """
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

    Built by the sidecar's own builder here as well, so what is compared is that the harness
    substitutes nothing else: not the layer count, not the window, not the slot count, not the
    tail. Until 2026-09-05 the harness typed `-ngl 99 --ctx-size 8192 --parallel 1` for every
    row, which this fails for the cortex tier, whose window is twice that, and for the subagent
    tier, whose slot count is two.
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
    """The CPU row is the card row with the layer count the core hands the host for that server.

    The image differs as well, because the stack starts that server from the CPU build, and the
    card row's layer count is the tier's own rather than the core's word for the card, since the
    model host is what really starts that process.
    """
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
    assert CPU_PLACEMENT.reservation == ("--cpus", str(DEFAULT_CPU_BUDGET))
    assert [placement.label for placement in PLACEMENTS] == [
        PlacementTarget.GPU.value,
        PlacementTarget.CPU.value,
    ]


def test_which_rows_are_a_models_own() -> None:
    """A thinking-off model has a row per switch on the card and a shipped row on the CPU; a
    thinking-on model has one row, under the shipped switch on the card.

    The thinking-on rule is the one that skipped both of a cortex row's copies from 2026-09-04 to
    2026-09-05, so the cortex row's one remaining copy is asserted to run rather than inferred.
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
