"""CI-side gate on the injection harness's thinking-switch rows: the argv and the request."""

from test_injection_defense_live import (
    MODELS,
    REQUEST_KEY,
    SHIPPED_BUDGET,
    SHIPPED_REASONING_OFF,
    SHIPPED_SWITCH,
    SWITCHES,
    THINKING_ON,
    VISION_MODELS,
    Model,
    completion_body,
    server_argv,
    switch_for,
    template_kwargs,
)

_TEMPLATE_KWARGS_FLAG = "--chat-template-kwargs"
_REASONING_BUDGET_FLAG = "--reasoning-budget"

# A row's own inputs, which nothing here is about: the switch is the only variable, so the
# messages and tools are a fixed stand-in the two bodies are compared over.
_MESSAGES: list[dict[str, object]] = [{"role": "user", "content": "summarise this"}]
_TOOLS: list[dict[str, object]] = [{"type": "function", "function": {"name": "read_file"}}]
_MAX_TOKENS = 1600

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


def test_the_two_switch_rows_differ_by_the_lever_and_by_nothing_else() -> None:
    """One row moves the pair onto the argv and the key off the request; nothing else moves."""
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
    """A caller naming no switch gets the request key, which is what the old rows sent.

    ``server_argv`` defaults the other way, to no flag at all, and the two defaults together are
    exactly the cell this harness measured before it could be handed a tier's argv.
    """
    subagent: Model = _THINKING_OFF[0]
    assert switch_for(subagent) is REQUEST_KEY
    assert server_argv(subagent, SHIPPED_BUDGET) == server_argv(
        subagent, SHIPPED_BUDGET, REQUEST_KEY
    )
