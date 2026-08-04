// WHAT THE OVERLAY SAYS OUT LOUD WHEN THE CONVERSATION ON SCREEN IS REPLACED.
//
// A chat swap changes everything in the panel and moves nothing. The header title, the history and
// the chat the composer is about to send into all become another conversation's, while focus stays
// exactly where the reader left it. On screen that reads at a glance, which is why it was silent
// for so long: nothing announced it, and the three regions the overlay already had are about
// other things entirely (the connection dot's health, the capture ring's screen read, and a
// failed reply's alert), none of them knowing a chat from another. This is the state behind the
// region that does announce it (`components/Announcer.tsx`).
//
// WHICH DOORS WRITE HERE, AND WHY THE REST DO NOT. A swap speaks when the gesture that fired it
// named no chat: `Ctrl+↑` and `Ctrl+↓`, `Ctrl+N`, a reminder card's open control, and the fresh
// chat that replaces a deleted one. It stays silent when the control that fired it carries the
// arriving chat's name as its own accessible name, which is the switcher row and the header's
// pencil: a reader who pressed one has already been read the title, and a live region would only
// hand it back. Cold-start adoption is silent for a third reason, having no gesture at all behind
// it. So the rule is about the gesture rather than about the transition, which is why the flag
// travels with the action instead of being decided in the reducer arm: one arm serves a row and a
// cycle key both.

/** One thing the overlay has to say: the chat that arrived, and which arrival it is. */
export interface Notice {
  /** The arriving chat's title, the same string the header takes in the same commit: a stored
   *  chat's is `headerTitle`'s answer, and a fresh one's is the new-chat name they share. */
  readonly title: string;
  /**
   * Which announcement this is, counted from the overlay's first.
   *
   * A live region reports a mutation, not a value, so text replaced by identical text is not an
   * announcement at all. Two chats can easily carry one title (the same question asked twice, or
   * two runs of the fresh-chat name), and without a counter the second of them would arrive in
   * silence. `Announcer` keys the region's child on this, so every notice replaces the node
   * instead of leaving it standing, whatever it says.
   */
  readonly count: number;
}

/** The notice after `previous`, naming `title`. */
export function speak(previous: Notice | null, title: string): Notice {
  return { title, count: (previous?.count ?? 0) + 1 };
}
