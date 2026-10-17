# brain/packages/settings (`cortex_settings`)

**Purpose.** The one reader every Python entry point reads its pydantic-settings classes through:
the brain (`cortex_orchestrator.entry`), the model host (`cortex_model_manager.server.main`) and
the email sidecar (`cortex_email.server.main`). It turns a value a class refuses into an error that
names the environment variable and the rule broken, and never a text value, so a malformed setting
ends a container with one line an operator can act on instead of a traceback naming a code field
and quoting the input.

## Public contract

`__all__` is the API.

- `read_settings(cls)` constructs `cls` from the environment and returns it, or raises
  `ConfigError`:
  - for a `pydantic.ValidationError`, one `<variable>: <reason>` per refused field, joined by `; `,
    raised `from None` because the `ValidationError`'s own text includes the input. A refusal of the
    whole class (a model validator) has no field and keeps its own words.
  - for a `pydantic_settings.SettingsError`, which is a complex field (a list, a dict) whose value
    is not JSON, `<variable> is not valid JSON`, chained to the cause, whose text names the field
    and not the value.
- The variable is the field's string `validation_alias` when it has one, which pydantic reports in
  place of the field name, and otherwise the class's `env_prefix` plus the field name, upper case.
- The reason is pydantic's own message without its `Value error, ` prefix. Pydantic's built-in
  messages state the rule and not the input. A validator's own message quotes the input as its
  `repr` (`{value!r}`), so for a `value_error` on a non-empty string input each copy of that `repr`
  is replaced by `'<value>'`. Any other copy of the value is part of the message's own words and
  stays: masking it would garble them, as `pack` inside `packed` did, and the gaps would show the
  value.
- `ConfigError` is a plain `Exception`. A settings class whose validator must refuse a value
  without pydantic rendering it raises a `ConfigError` subclass, which pydantic lets through
  unchanged (`MemoryConfigError` and `RuntimeConfigError` in `cortex_orchestrator.config`).

## How each entry point reports a refusal

Each catches `ConfigError`, writes one line and returns exit status 1 to `sys.exit` in its
`__main__`. The rendering differs because what is installed at that moment differs:

| Entry point | Line | Why that rendering |
| --- | --- | --- |
| brain | `ERROR:cortex_orchestrator.entry:setting refused reason="..."` | logging is configured from `CORTEX_LOG_FORMAT` first, so the line is in the rendering asked for; a refused `CORTEX_LOG_FORMAT` is written in `plain` |
| model host | `ERROR:cortex_model_manager.server:setting refused reason="..."` | `ModelHostConfig` is the class that names the level and rendering, so a refusal is written at INFO in `plain` |
| email | `setting refused: ...` | the sidecar imports nothing from the core and FastMCP installs its handler later, so the standard library's last-resort handler writes the message alone |

## Invariants

- One reader. No entry point constructs a settings class directly.
- A refused text value is not in the message, and not in the traceback, since the
  `ValidationError` is dropped from the chain. This holds for a validator that writes a text input
  only as `{value!r}` or inside a variable's name (`CORTEX_SUBAGENTS_ROSTER__<model>`), which every
  validator here does; a class whose input holds a credential raises a `ConfigError` subclass with
  fixed words instead. The validators that compare numeric settings (`SubagentsConfig`'s timeouts
  and budgets, `CORTEX_TOOLS_SALIENCE_LIMIT`) state the numbers they compared, so their reason
  changes with the value.
- Fully typed, pyright strict clean, and 100% line and branch: `tests/test_settings_reader.py`
  drives the reader over a class of its own, and each entry point's suite drives its own classes.

**Dependencies.** pydantic and pydantic-settings only, so the email sidecar can import it without
taking the brain's core. The decision is
[ADR-0051](../adr/ADR-0051-log-line-rendering.md) decision 17.
