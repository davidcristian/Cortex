# A reply keeping a fact for this chat in another language gets no note

**Status:** done 2026-11-08
**Area:** memory
**Origin:** [ADR-0019](../../adr/ADR-0019-tainted-memory-recording.md)

`claims_chat_only` in `chat_only_claim.py` reads English only, so `KEPT_BEYOND_CHAT_NOTE` closes an
English reply that keeps a stored fact "for our conversation" and no reply in the four other
languages the request readers read. Under the global memory scope the row is recalled in every
later chat, and the reply says it is not.

Reproduction, a real turn on the shared stack (global scope, 2026-11-07): "Je n'enregistre pas les
appels, mais le code de mon casier est 5819." was stored as one `memories` row and answered "C'est
bien noté, j'ai pris en compte que le code de votre casier est **5819** (même si vous
n'enregistrez pas les appels). Je m'en souviendrai pour la suite de notre conversation." with no
note. Unit level, `claims_chat_only` is `False` for that last sentence, for "Ich merke es mir für
den Rest unseres Gesprächs." and for "Lo recordaré durante esta conversación.", and `True` for
"I will remember it for the rest of our conversation."

## What to do

1. Count the recorded replies in the other four languages that keep a fact for the chat, from the
   turn records the language flows wrote (`docs/readings/overlay-language-and-locale-flows.md`).
2. Read `pour la suite de notre conversation`, `pendant cette conversation`, `für den Rest unseres
   Gesprächs`, `in diesem Gespräch`, `durante esta conversación` and `pe parcursul conversației`
   beside a keep verb, with near misses first (a reply about the conversation that keeps nothing).

## History

- 2026-11-07: filed by the third audit of the night's changes, from a real turn.
- 2026-11-08: done. `claims_chat_only` reads a keep verb and a chat phrase in either order in French,
  German, Spanish and Romanian; over 749 recorded replies it flags the two French chat-only replies
  the old reader missed and nothing else
  ([readings](../../readings/remember-request-tool-search.md#the-chat-only-form-in-four-more-languages-2026-11-08)).
