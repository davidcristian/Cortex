
/** One thing the overlay has to say: the chat that arrived, and which arrival it is. */
export interface Notice {
  /** The arriving chat's title, the same string the header takes in the same commit: a stored
   *  chat's is `headerTitle`'s answer, and a fresh one's is the new-chat name they share. */
  readonly title: string;
  /** Which announcement this is, counted from the overlay's first. */
  readonly count: number;
}

/** The notice after `previous`, naming `title`. */
export function speak(previous: Notice | null, title: string): Notice {
  return { title, count: (previous?.count ?? 0) + 1 };
}
