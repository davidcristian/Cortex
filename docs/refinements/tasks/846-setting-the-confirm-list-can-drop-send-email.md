# Setting the confirm list can drop `send_email` from it

**Status:** open, actionable
**Area:** email-confirmer
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)
**Verified:** 2026-10-12

`CORTEX_TOOLS_GATED` (`ToolsConfig.confirm_names`) defaults to `escalate_to_brain` and
`send_email`, and a value replaces that default instead of adding to it. The
[body-volume runbook](../../runbooks/body-volume.md) says to "add `set_volume`" to it; written as
`["set_volume"]`, the setting drops both default names. `send_email` then needs no confirmation
anywhere: the cortex runs it on a tainted turn with no card, and `ConfirmFreeToolRegistry` no
longer removes it from a subagent's tools, so a task stored tainted reaches it when the task fires.
[ADR-0019](../../adr/ADR-0019-tainted-memory-recording.md) decision 8 lets a turn that recall
alone tainted store a task, and row I of
[recall-tainted-task.md](../../readings/recall-tainted-task.md) stored one that an injected note
asked for, to email bank details to an outside address. Under the default, three layers keep
that task from sending: the subagent registry removes `send_email`, the subagent dispatcher's
confirm set names it, and the run is tainted with no confirmer. All three read the one setting.

The comma form that the [vision runbook](../../runbooks/vision.md) and
[ADR-0029](../../adr/ADR-0029-vision-screen-capture.md) decision 5 write,
`CORTEX_TOOLS_GATED=escalate_to_brain,send_email,capture_screen`, fails at startup with
`SettingsError`, because the field decodes JSON. ADR-0029's form also leaves out
`escalate_to_brain`. [R-258](258-an-image-variant-of-the-injection-defence-tests.md) and a comment
in `test_screen_tool.py` repeat it.

Reproduction, 2026-10-12: a remote registry listing `read_text_file` and `send_email`, wrapped in
`ConfirmRequiredToolRegistry(names=ToolsConfig().confirm_names)` as `build_tool_registry` wraps it,
then in `ConfirmFreeToolRegistry` as `build_subagent_tools` does.

| `CORTEX_TOOLS_GATED` | `confirm_names` | A subagent's tools |
| --- | --- | --- |
| unset | `escalate_to_brain`, `send_email` | `read_text_file` |
| `["set_volume"]` | `set_volume` | `read_text_file`, `send_email` |
| `escalate_to_brain,send_email,capture_screen` | startup fails, `SettingsError` | no brain starts |

## What to do

1. Make `escalate_to_brain` and `send_email` always confirmed, merged under the setting as
   `cost_policy` merges the built-in prices, so the setting only adds names. Decide what `[]`
   (tested in `test_config.py` as emptying the set) means after that, and write the rule in
   ADR-0022 decision 4.
2. Accept the comma form the docs write, or rewrite every doc that shows it in JSON: the vision
   and body-volume runbooks, ADR-0029 decision 5, R-258 and the test comment.

## History

- 2026-10-12: filed from row I of the recall-tainted task rows, while checking whether a fired
  tainted task can reach an outward tool ([R-073](073-fence-without-block-recall.md)).
