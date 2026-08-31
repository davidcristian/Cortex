"""The wide recall corpus: notes, questions, and the category each question is testing.

Test-tree input data for `test_rerank_judge_wide_live.py`, kept out of the test file so the
corpus can be read as a corpus. It is the input to a measurement, not a module of the brain.

**Written by an interested party.** The same caveat the original ten-note corpus carries applies
here in full: the agent that recommended the judge wrote these notes and these questions, and no
sampling of real memories was involved. What is different is the *shape* of the bias. The original
corpus was built so that every gold note answered its question in words the question never used
while a distractor echoed the question's vocabulary, which is the case a cosine cannot see. A
corpus made only of those cases can produce one result and no other, so it demonstrates rather
than measures.

This corpus is therefore built to be adversarial to its author's own conclusion. It has six
categories, and only the first is the case the judge was adopted for. The other five are cases
where the cosine should win or tie, where a model reading the notes can reason its way past the
right answer, or where the correct result is nothing at all:

`TRAP`      the original corpus verbatim, so the wide run is a superset of the published one.
            The answer shares no vocabulary with the question; a distractor shares plenty.
`LEXICAL`   the answer *does* use the question's own words, so the embedding is already right
            and the only thing a judge can add is a mistake.
`TWIN`      two near-duplicate notes, both plausible, differing in the one detail the question
            pins. The embedding scores them almost equally, and only reading them separates the
            two.
`ABSENT`    nothing in the corpus answers the question. There is no gold note. The right result
            is no hit, and the measurement is whether the judge invents a pick instead.
`STALE`     two versions of the same fact, one superseded. The recency signal is in the prose
            ("since the move", "the migration finished"), never in the metadata, because the
            rank prompt does not carry timestamps and neither ranking may be credited for one.
`CLAUSE`    the answer is a subordinate clause of a note whose topic is something else, so the
            note as a whole sits away from the question even though the sentence inside it hits.

`UNRELATED` at the foot of the file is a third population outside `QUESTIONS` entirely, added by
the relevance-floor calibration: questions about subjects no note touches at all.
"""

from enum import Enum


class Category(Enum):
    """What a question is probing, and therefore which ranking ought to be favoured."""

    TRAP = "trap (answer shares no words; distractor does)"
    LEXICAL = "lexical (answer shares the question's words)"
    TWIN = "twin (two near-duplicates, one correct)"
    ABSENT = "absent (no note answers it)"
    STALE = "stale (a superseded version competes)"
    CLAUSE = "clause (the answer is buried in a longer note)"


# id -> remembered text. The pool every question is ranked against.
MEMORIES: dict[str, str] = {
    # TRAP: the original ten notes, verbatim from test_rerank_judge_live.py.
    "state": (
        "we settled on Redis for anything a turn is holding, and Postgres for what outlives it"
    ),
    "state-noise": "the Redis container kept restarting until the healthcheck interval was raised",
    "gpu": "only one model sits on the card at a time and the others are evicted before it loads",
    "gpu-noise": "the card arrived on Tuesday and the box was dented",
    "coffee": "she takes hers black, no sugar, and refuses anything from a pod machine",
    "coffee-noise": "the coffee machine in the kitchen was replaced in March",
    "flight": "the return leg is the red-eye that lands just after six in the morning",
    "flight-noise": "flights were cheaper the week before but the dates did not work",
    "deploy": (
        "nothing ships on a Friday, and the person who merges it is the person who watches it"
    ),
    "deploy-noise": "the deploy script lives in the scripts directory next to the linters",
    # LEXICAL: the gold note answers in the question's own words, with a topical neighbour
    # alongside it that shares the vocabulary and answers nothing.
    "wifi": "the wifi password for the guest network is written under the router",
    "wifi-noise": "the guest network drops out every time the microwave runs",
    "dentist": "the dentist appointment is on the fourteenth at half past nine in the morning",
    "dentist-noise": "the dentist moved to the new building behind the supermarket",
    "passport": "the passport expires in September next year and renewal takes six weeks",
    "passport-noise": "the passport photos came out too dark and had to be taken again",
    "standup": "the team standup is at quarter past nine every weekday morning",
    "standup-noise": "the standup ran long on Monday because of the incident review",
    # TWIN: two notes of the same shape, differing in the detail the question asks for.
    "hotel-lisbon": "the hotel booking in Lisbon is two nights starting on the third",
    "hotel-porto": "the hotel booking in Porto is four nights starting on the ninth",
    "tablets-blue": "the blue tablets are two in the morning, taken with food",
    "tablets-white": "the white tablets are one at night, on an empty stomach",
    "key-flat": "the spare key to the flat is with the neighbour on the second floor",
    "key-garage": "the spare key to the garage hangs inside the fuse cupboard",
    "budget-design": "the design budget was signed off at eight thousand for the quarter",
    "budget-research": "the research budget was signed off at three thousand for the quarter",
    # ABSENT: near misses only. These sit close to the unanswerable questions and answer none of
    # them, so a ranking that fills every slot it is offered has a plausible note to pick.
    "car": "the car needs a new set of tyres before the winter",
    "parking": "parking near the office is impossible after eight in the morning",
    # STALE: the superseded version and the current one, the difference stated in prose.
    "office-old": "the team sat on the fourth floor until the lease ran out",
    "office-new": (
        "since the move the team sits on the ninth floor and the old fourth floor rooms "
        "belong to someone else now"
    ),
    "db-old": "we were on MySQL for the first year of the project",
    "db-new": "the migration off MySQL finished in June and everything runs on Postgres now",
    "phone-old": "her old number ended in 4471 and it is no longer in service",
    "phone-new": "her number now ends in 8802",
    "gym-old": "the gym membership was monthly and renewed itself automatically",
    "gym-new": "the gym membership was cancelled in April so there is nothing left to renew",
    # CLAUSE: the answer is one clause of a note about something else.
    "wedding": (
        "the wedding is in the village where her parents met, which is a two hour drive north, "
        "and the reception runs until midnight"
    ),
    "onboarding": (
        "onboarding took most of the week, though the laptop arrived on the first morning and "
        "the badge only cleared on the Thursday"
    ),
    "incident": (
        "the incident review found the alert was fine and the pager rota was the problem, so "
        "the rota now hands over on Wednesdays"
    ),
    "recipe": (
        "the bread recipe is forgiving about the flour but the oven has to be at two hundred "
        "and thirty and the tin goes on the lower shelf"
    ),
    "coast": "the drive to the coast takes about four hours once the traffic starts",
}

# question -> (the note that answers it or None when nothing does, the category it probes).
QUESTIONS: dict[str, tuple[str | None, Category]] = {
    # TRAP (6): the published corpus's own questions, unchanged.
    "where are we keeping things while a conversation is in progress?": ("state", Category.TRAP),
    "can two of them be loaded at once?": ("gpu", Category.TRAP),
    "how does she like her coffee?": ("coffee", Category.TRAP),
    "what time do we get back?": ("flight", Category.TRAP),
    "is it alright to release at the end of the week?": ("deploy", Category.TRAP),
    "who is on the hook after a release goes out?": ("deploy", Category.TRAP),
    # LEXICAL (4): the embedding is right on its own here.
    "what is the wifi password for the guest network?": ("wifi", Category.LEXICAL),
    "when is the dentist appointment?": ("dentist", Category.LEXICAL),
    "when does the passport expire?": ("passport", Category.LEXICAL),
    "what time is the team standup?": ("standup", Category.LEXICAL),
    # TWIN (4): both candidates are plausible; one detail separates them.
    "how many nights are we in Porto?": ("hotel-porto", Category.TWIN),
    "how many of the white ones do I take?": ("tablets-white", Category.TWIN),
    "where is the garage spare kept?": ("key-garage", Category.TWIN),
    "how much did research get?": ("budget-research", Category.TWIN),
    # ABSENT (4): no gold. Returning nothing is the correct answer.
    "what is the car insurance renewal date?": (None, Category.ABSENT),
    "which airline did we end up flying with?": (None, Category.ABSENT),
    "what did the dentist say about the x-ray?": (None, Category.ABSENT),
    "how much does the parking permit cost?": (None, Category.ABSENT),
    # STALE (4): the current version wins, and only the prose says which it is.
    "which floor is the team on?": ("office-new", Category.STALE),
    "what database is the project on?": ("db-new", Category.STALE),
    "what number should I ring her on?": ("phone-new", Category.STALE),
    "is the gym still being paid for?": ("gym-new", Category.STALE),
    # CLAUSE (4): the note's topic is not the answer; a clause inside it is.
    "how long is the drive to the wedding?": ("wedding", Category.CLAUSE),
    "when did the badge come through?": ("onboarding", Category.CLAUSE),
    "which day does the pager rota change hands?": ("incident", Category.CLAUSE),
    "what temperature does the bread go in at?": ("recipe", Category.CLAUSE),
}

# A third population, and deliberately NOT a `Category` in `QUESTIONS` above: adding it there
# would silently move every number every earlier run of this corpus published. `ABSENT` questions
# are unanswerable *and adjacent*, each sitting beside notes the corpus does hold, which is what
# makes them hard. These are unanswerable and unrelated: nothing here shares a subject with any
# note, so they are the easiest possible case for a policy that selects by distance alone. Used by
# `test_recall_floor_live.py` to ask what a similarity floor can catch at its very best.
UNRELATED: tuple[str, ...] = (
    "what is the atomic weight of tungsten?",
    "who won the world cup in 1998?",
    "how do I sharpen a chisel without a jig?",
    "what year did the Bronze Age end in northern Europe?",
    "is a tomato botanically a fruit?",
    "how deep is the Mariana Trench?",
    "what does a semicolon do in a for loop?",
    "why do cats knead blankets?",
)
