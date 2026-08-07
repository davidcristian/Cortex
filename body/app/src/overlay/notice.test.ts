import { describe, expect, it } from "vitest";

import { NO_OTHER_CHATS, arrived, chatDeleted, reminderDismissed, speak } from "./notice";

describe("notice", () => {
  it("counts every announcement, so two with the same words are two things said", () => {
    // A live region reports a mutation and not a value, so identical text landing twice is
    // nothing landing twice. Two chats can carry one title and two deletes can leave the same
    // number of rows, which is why the count is the region's key. Reddens if it stops moving.
    const first = speak(null, [arrived("New chat")]);
    const second = speak(first, [arrived("New chat")]);
    expect(first).toEqual({ text: "Switched to New chat.", count: 1 });
    expect(second).toEqual({ text: "Switched to New chat.", count: 2 });
  });

  it("joins what it was given into one sentence, in the order it happened", () => {
    // A delete that also swaps the chat is one commit, so it is one announcement: the row that
    // left leads, and the conversation that took its place follows. Reddens if the parts are
    // reordered or run together without a gap.
    expect(speak(null, [chatDeleted(1), arrived("New chat")]).text).toBe(
      "Chat deleted. 1 chat left. Switched to New chat.",
    );
  });

  it("counts the rows a list has left, in the plural the number wants", () => {
    expect(chatDeleted(2)).toBe("Chat deleted. 2 chats left.");
    expect(chatDeleted(1)).toBe("Chat deleted. 1 chat left.");
    expect(reminderDismissed(3)).toBe("Reminder dismissed. 3 reminders left.");
    expect(reminderDismissed(1)).toBe("Reminder dismissed. 1 reminder left.");
  });

  it("says an emptied switcher in the switcher's own words", () => {
    // The line the list puts up and the sentence the region reads are one string, so a reader
    // who hears one and then reads the other is not told two different things about one empty
    // list. Reddens if either grows its own wording (`components/SessionList.tsx` renders the
    // same constant).
    expect(chatDeleted(0)).toBe(`Chat deleted. ${NO_OTHER_CHATS}.`);
    expect(NO_OTHER_CHATS).toBe("No other chats yet");
  });

  it("says an emptied reminder stack, which is also the surface leaving", () => {
    // The last ack takes the whole section with it, so this sentence is the only warning that
    // the thing the reader was working in is gone.
    expect(reminderDismissed(0)).toBe("Reminder dismissed. No reminders left.");
  });
});
