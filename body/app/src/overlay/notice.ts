
/** One thing the overlay has to say. */
export interface Notice {
  /** The whole sentence, ready to read: what happened to the panel, in the order it happened. */
  readonly text: string;
  /** Which announcement this is, counted from the overlay's first. */
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

/** How many rows a list has left, in its own words: `2 chats left`, `1 chat left`. */
function tally(left: number, noun: string): string {
  return `${left} ${noun}${left === 1 ? "" : "s"} left.`;
}

/** A chat left the switcher, and what the list holds now. */
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
