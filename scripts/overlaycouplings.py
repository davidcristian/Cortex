"""The couplings inside the overlay: a name its TypeScript publishes and its stylesheet spends.

Half of the registry `crosscheck.py` reads, split off `couplings.py` when the one file outgrew the
300-line cap, along a seam that was already there: every entry here ties one tree's two languages
to each other, where every entry beside it ties the body to the brain. The far side is
always `overlay.css`, and it is always a **mention**, a stylesheet having no declaration a scan
could read. What a rename costs is written in each entry, because a custom property that resolves
to nothing does not fail loudly: it falls back to whatever `:root` froze, or to the fallback in the
`var()` itself, with every test still green.
"""

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
        # Three rules read the attribute and the bare mention stays a presence check over all
        # three, because three is the sum of two unrelated features: one hides a scrollbar thumb
        # mid-roll, and the two below cap the sections' shares. The pair IS a set, the handover
        # being symmetric or not at all, so it is pinned by a narrower template of its own.
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
        # Both halves of one name. The declaration renders the value beside it; the spends render
        # the name alone, which is the only thing that reaches a `var()` the value never appears
        # in. The spends stay a presence check because 52 transitions across unrelated features
        # ride this curve, and a count over them would fail on the next one added; what the
        # presence check holds is that the property the sheet declares is the one they ask for.
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
        # The sheet spells the number once, on :root, and the two rules that follow the roll spend
        # the name rather than the value, which is why the second mention renders the name and
        # nothing else. It is counted where the curve above is not: these two ARE the set the
        # reason above names, so losing one is the drift rather than a design change, and a third
        # rule joining them is a registry line to correct rather than a silent widening. What used
        # to stand in for that count was the browser, a var() that resolves to nothing being
        # invalid at computed-value time and taking the whole transition with it, which is a
        # defect found by looking. The four other 0.3s declarations in that file only coincide
        # with the roll (the panel's summon fade and three arrival animations) and stay literal on
        # purpose: pinning them would tie a retune of the roll to features it has nothing to do
        # with.
        mentions=(
            Mention(OVERLAY_CSS, "{name}: {value}ms;", name="--roll"),
            Mention(OVERLAY_CSS, "var({name})", name="--roll", occurrences=2),
        ),
    ),
)
