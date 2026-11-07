# A reply takes the language of a recalled memory

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0008](../../adr/ADR-0008-memory-v1.md)
**Verified:** 2026-11-07

A question in English whose recalled memory was written in another language is answered in that
language. On 2026-11-07 the `cortexn15` stack (gemma-4-12B at context 16,384, llama-server build
`b12169-3ed7284f2`) stored four facts told in French, German, Spanish and Romanian, then asked for
each in a new English chat. Three of four replies were in the fact's language
(`What is my dog called?` was answered `Dein Hund heißt Bello.`), and the English
`Remind me at half past five to call mum.` was answered in French after a French reminder
exchange was recalled into its request
([readings](../../readings/overlay-language-and-locale-flows.md)).

The recall block (`MEMORY_HEADER` in `turn_context.py`) says what the memories are and which one
is current, and nothing about the language of the reply. Recall itself worked: the embedder found
every fact across languages.

Reproduction: send `Merk dir, dass mein Hund Bello heißt.` in one chat and
`What is my dog called?` in a new one.

## What to do

1. Write rows and a pass rule into the readings record before any draw: facts stored in four
   languages, each asked for in English, and English facts asked for in each of the four, three
   draws each. A draw passes when the reply is in the language of the person's message.
2. Draw base, then one candidate: a sentence in `MEMORY_HEADER` saying a memory may be in another
   language and the reply follows the person's message. A note the brain appends cannot fix the
   language of a reply, so the recall block is the first place to try.

## History

- 2026-11-07: filed from the language and locale flows on the shared stack.
