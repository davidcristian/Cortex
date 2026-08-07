// WHAT THE OVERLAY SAYS OUT LOUD, AND EVERYTHING IT IS ALLOWED TO SAY.
//
// The overlay keeps ONE polite live region (`components/Announcer.tsx`), and this module is the
// whole of what may go in it. Every sentence below is built here rather than at the arm that raises
// it, so "what the region can carry" is a question with one file for an answer instead of a habit
// spread over four reducer arms.
//
// IT STARTED AS THE CHAT THAT ARRIVED. A chat swap changes everything in the panel and moves
// nothing: the header title, the history and the chat the composer is about to send into all become
// another conversation's, while focus stays exactly where the reader left it. On screen that reads
// at a glance, which is why it was silent for so long; the three other regions the overlay has are
// about other things entirely (the connection dot's health, the capture ring's screen read, and a
// failed reply's alert), none of them knowing a chat from another.
//
// WHICH SWAPS SPEAK, AND WHY THE REST DO NOT. A swap speaks when the gesture that fired it named no
// chat: `Ctrl+↑` and `Ctrl+↓`, `Ctrl+N`, a reminder card's open control, and the fresh chat that
// replaces a deleted one. It stays silent when the control that fired it carries the arriving chat's
// name as its own accessible name, which is the switcher row and the header's pencil: a reader who
// pressed one has already been read the title, and a live region would only hand it back. Cold-start
// adoption is silent for a third reason, having no gesture at all behind it. So the rule is about the
// gesture rather than about the transition, which is why the flag travels with the action instead of
// being decided in the reducer arm: one arm serves a row and a cycle key both.
//
// AND IT NOW CARRIES A LIST THAT SHRANK, which is the widening (ADR-0035 addendum, 2026-08-07).
// Measured in Chromium at 900x900 before it: deleting a chat that was not the open one, deleting the
// last one so the list emptied, and acking a reminder each produced ZERO mutations in any live
// region on the page. The reader landed on a control whose name says what it is and heard nothing
// about the list they had just changed. The row is gone from the tree by then, so unlike a held key
// or an unmoved caret there is nothing left for them to re-read: the fact is destroyed rather than
// merely unspoken, which is the test a sentence has to pass to earn a place here.
//
// ONE REGION AND NOT TWO, deliberately. Deleting the chat that IS open shrinks the list and swaps
// the conversation in a single commit, so a second region would put two announcements in flight at
// once and leave whether both are spoken, and in which order, to the reader's own speech queue,
// which nothing here can observe. One region says one thing, and when a delete does both, it says
// both in one sentence in the order they happened (`chatDeleted` then `arrived`).
//
// AND IT NOW CARRIES A LIST THE READER ASKED FOR (ADR-0035 addendum, 2026-08-07). Measured in
// Chromium before it, over thirteen ways the switcher opens: not one of them produced a mutation in
// any live region on the page, and not one of them moved the caret. The only channel carrying the
// fact was `aria-expanded` on the header's chats button, which flipped false to true where the
// reader was not standing, so a reader who pressed `Ctrl+K` was handed silence. What the sentence
// carries is what the list HOLDS rather than that a section toggled: the row count is the one thing
// the tab order cannot hand back, and on an empty list it cannot hand back anything at all, the
// line saying so being text rather than a tab stop (measured: Tab from the chats button on an empty
// list walks the header's remaining three buttons and then leaves the list entirely).

/** One thing the overlay has to say. */
export interface Notice {
  /** The whole sentence, ready to read: what happened to the panel, in the order it happened. */
  readonly text: string;
  /**
   * Which announcement this is, counted from the overlay's first.
   *
   * A live region reports a mutation, not a value, so text replaced by identical text is not an
   * announcement at all. Two chats can easily carry one title (the same question asked twice, or
   * two runs of the fresh-chat name), and two deletes in a row leave sentences that differ only in
   * a number. Without a counter the second of them would arrive in silence. `Announcer` keys the
   * region's child on this, so every notice replaces the node instead of leaving it standing,
   * whatever it says.
   */
  readonly count: number;
}

/** The notice after `previous`, saying `said` in order as one sentence. */
export function speak(previous: Notice | null, said: readonly string[]): Notice {
  return { text: said.join(" "), count: (previous?.count ?? 0) + 1 };
}

/** The conversation that arrived. A sentence rather than a bare title, because a title read out of
 *  nowhere ("Reminders and recurrence") names a thing without saying what happened to it. */
export function arrived(title: string): string {
  return `Switched to ${title}.`;
}

/** What the switcher's list says when it holds nothing, and the words the region borrows for the
 *  same state, so the line on screen and the sentence in the region cannot drift apart. It is the
 *  header-and-switcher lesson one surface down: two renderings of one fact are one string. */
export const NO_OTHER_CHATS = "No other chats yet";

/** What the chat list is called, in the one place both renderings of the name read it from: the
 *  header control that opens it, the list element itself, and the sentence below that names it to a
 *  reader who cannot see either. Same rule as the empty line above. */
export const RECENT_CHATS = "Recent chats";

/** How many rows a list holds, in its own words: `2 chats`, `1 chat`. */
function count(rows: number, noun: string): string {
  return `${rows} ${noun}${rows === 1 ? "" : "s"}`;
}

/** How many rows a list has left, which is what a list that just shrank under the reader reports. */
function tally(left: number, noun: string): string {
  return `${count(left, noun)} left.`;
}

/**
 * The chat list, opened, and what it holds.
 *
 * WHAT IT SAYS IS THE CONTENTS AND NOT THE TOGGLE, which is why there is no mirror of this for the
 * list closing. A reader who opens the list is asking what chats there are, and the answer is the
 * one thing they cannot get by walking: the rows are nine Tab presses ahead of the composer and the
 * empty line is not a tab stop at all. A reader who closes it is asking for it to go, and is
 * answered by the caret landing on the control that says so (`overlay/sectionCaret.ts`).
 */
export function switcherOpened(chats: number): string {
  return chats === 0
    ? `${RECENT_CHATS} open. ${NO_OTHER_CHATS}.`
    : `${RECENT_CHATS} open. ${count(chats, "chat")}.`;
}

/**
 * A chat left the switcher, and what the list holds now.
 *
 * The title is deliberately not repeated: the control the reader pressed is labelled
 * "Confirm delete <title>", so they have already been read the name, and what is news is that the
 * write landed (a failed delete leaves the row where it was) and what the list has become.
 */
export function chatDeleted(left: number): string {
  return left === 0 ? `Chat deleted. ${NO_OTHER_CHATS}.` : `Chat deleted. ${tally(left, "chat")}`;
}

/** A reminder left the stack, and what the stack holds now. The last one takes the section with
 *  it, so "no reminders left" is also the only warning that the surface itself has gone. */
export function reminderDismissed(left: number): string {
  return left === 0
    ? "Reminder dismissed. No reminders left."
    : `Reminder dismissed. ${tally(left, "reminder")}`;
}
