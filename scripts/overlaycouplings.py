"""The couplings inside the overlay: a name its TypeScript declares and its stylesheet uses."""

from couplings import Constant, Mention, Site

OVERLAY_CSS = "body/app/src/overlay.css"

OVERLAY_COUPLINGS: tuple[Constant, ...] = (
    Constant(
        label="the panel's ceiling custom property",
        why=(
            "the placement writes the panel's own max-height under this name and the stylesheet "
            "spends it as the budget every section is a share of, with a `100vh` fallback, so a "
            "rename silently restores the uncapped section the budget exists to stop (ADR-0035)"
        ),
        sites=(Site("body/app/src/overlay/panelBudget.ts", "CEILING_PROPERTY"),),
        mentions=(Mention(OVERLAY_CSS, "var({value},"),),
    ),
    Constant(
        label="the chat floor custom property",
        why=(
            "the probe publishes the measured empty state under this name and the log's "
            "min-height spends it, so a rename falls back to the frozen value on :root, which "
            "is exactly the constant the probe replaced (ADR-0035)"
        ),
        sites=(Site("body/app/src/overlay/measured.ts", "CHAT_FLOOR_PROPERTY"),),
        mentions=(Mention(OVERLAY_CSS, "var({value})"),),
    ),
    Constant(
        label="the trace row custom property",
        why=(
            "the probe publishes the closed Thoughts row's height under this name and the "
            "disclosure's min-height spends it, so a rename degrades it to the frozen value on "
            ":root with every test still green (ADR-0035)"
        ),
        sites=(Site("body/app/src/overlay/measured.ts", "TRACE_ROW_PROPERTY"),),
        mentions=(Mention(OVERLAY_CSS, "var({value})"),),
    ),
    Constant(
        label="the resizing attribute",
        why=(
            "the placement writes this attribute while it moves the panel and one rule reads it "
            "to hide the history's scrollbar thumb, so a rename leaves the thumb riding a resize "
            "and nothing else says so (ADR-0035)"
        ),
        sites=(Site("body/app/src/overlay/panelPlacement.ts", "RESIZING_ATTRIBUTE"),),
        mentions=(Mention(OVERLAY_CSS, "[{value}]"),),
    ),
    Constant(
        label="the morphing attribute",
        why=(
            "a roll publishes the height it is going to under this attribute and the stylesheet "
            "reads it with :has() to ease both section caps to that target, so a rename puts the "
            "room a closing section hands back into one frame again (ADR-0035)"
        ),
        sites=(Site("body/app/src/overlay/morph.ts", "MORPHING_ATTRIBUTE"),),
        mentions=(
            Mention(OVERLAY_CSS, "[{value}"),
            Mention(OVERLAY_CSS, ':not([{value}="0"])', occurrences=2),
        ),
    ),
    Constant(
        label="the shared easing curve",
        why=(
            "every scripted roll animates on this curve and the stylesheet restates it as the "
            "--ease custom property its own transitions spend, so a drift makes a CSS transition "
            "and the roll it accompanies move on two different clocks (ADR-0035/0037)"
        ),
        sites=(Site("body/app/src/overlay/morph.ts", "EASING"),),
        mentions=(
            Mention(OVERLAY_CSS, "{name}: {value};", name="--ease"),
            Mention(OVERLAY_CSS, "var({name})", name="--ease"),
        ),
    ),
    Constant(
        label="the shared roll duration",
        why=(
            "a section's roll animates for this many milliseconds and the stylesheet restates it "
            "as the --roll custom property the two rules that must move WITH a roll spend, so a "
            "drift lands the section caps' handover and the thoughts marker's turn on a different "
            "clock from the roll they accompany (ADR-0035/0037)"
        ),
        sites=(Site("body/app/src/overlay/morph.ts", "MORPH_ROLL_MS"),),
        mentions=(
            Mention(OVERLAY_CSS, "{name}: {value}ms;", name="--roll"),
            Mention(OVERLAY_CSS, "var({name})", name="--roll", occurrences=2),
        ),
    ),
)
