"""The share of the cortex's context one turn's recalled memories may fill, and how it is split."""

from collections.abc import Sequence

# About 1,590 cortex tokens at the dense ratio the history window is sized on (ADR-0008 decision 4).
RECALL_CHAR_BUDGET = 6000


def cut_marker(hidden: int) -> str:
    """The note that ends a memory shown only in part, naming how much of it is left out."""
    return f"\n[memory cut here: {hidden} more characters not shown]"


def recall_allowances(lengths: Sequence[int], budget: int) -> list[int]:
    """Split ``budget`` over texts of these lengths: a short text keeps its length, and the
    characters it leaves are shared evenly by the longer ones.
    """
    allowances = [0] * len(lengths)
    remaining = budget
    order = sorted(range(len(lengths)), key=lambda index: lengths[index])
    for position, index in enumerate(order):
        allowances[index] = min(lengths[index], remaining // (len(order) - position))
        remaining -= allowances[index]
    return allowances


def fit_recalled(texts: Sequence[str], budget: int = RECALL_CHAR_BUDGET) -> list[str]:
    """Each text as a turn shows it: whole within its allowance, else its start and a marker."""
    allowances = recall_allowances([len(text) for text in texts], budget)
    return [
        text if len(text) <= allowance else text[:allowance] + cut_marker(len(text) - allowance)
        for text, allowance in zip(texts, allowances, strict=True)
    ]
