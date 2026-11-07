# A forget by phrase leaves the recalled value in other rows

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-07

On 2026-11-07 the `cortexn15` stack held three rows naming a locker code: the French request
`Souviens-toi que le code de mon casier à la piscine est 7731.` and two English recall exchanges
answered `Votre code de casier à la piscine est 7731.`. `Oublie le code de mon casier à la
piscine.` called `forget_memories` with the text `code de mon casier à la piscine`, whose card
listed one exchange; it was approved, and the reply said `C'est fait, j'ai oublié le code de votre
casier à la piscine.` A new English chat asking for the code was answered `7731` from the two
rows left ([readings](../../readings/overlay-language-and-locale-flows.md#5-forget-in-other-languages)).
The model's trace named the value, `7731`, and then chose the phrase.

The rows the phrase missed were written by the brain's own recall replies, which change the
wording (`mon` became `Votre`), so a phrase from the person's request does not reach them while
the value does.

Reproduction: store the fact in French, ask for it in two new English chats, then send the forget
above in a third and ask for the code in a fourth.

## What to do

1. Draw English and French forgets by description over the same three rows, three draws each,
   and count the draws that leave a row naming the value. Whether the language matters is not
   known from one row.
2. If rows are left, compare a result text that lists the remembered exchanges still naming a
   value from the deleted ones with a card that offers them; the card is the destructive step, so
   it fails toward deleting less.

## History

- 2026-11-07: filed from the language and locale flows on the shared stack.
