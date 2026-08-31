import { describe, expect, it } from "vitest";

import {
  NO_OTHER_CHATS,
  RECENT_CHATS,
  arrived,
  chatDeleted,
  reminderDismissed,
  speak,
  switcherOpened,
} from "./notice";

describe("notice", () => {
  it("counts every announcement, so two with the same words are two things said", () => {
    const first = speak(null, [arrived("New chat")]);
    const second = speak(first, [arrived("New chat")]);
    expect(first).toEqual({ text: "Switched to New chat.", count: 1 });
    expect(second).toEqual({ text: "Switched to New chat.", count: 2 });
  });

  it("joins what it was given into one sentence, in the order it happened", () => {
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
    expect(chatDeleted(0)).toBe(`Chat deleted. ${NO_OTHER_CHATS}.`);
    expect(NO_OTHER_CHATS).toBe("No other chats yet");
  });

  it("says an emptied reminder stack, which is also the surface leaving", () => {
    expect(reminderDismissed(0)).toBe("Reminder dismissed. No reminders left.");
  });

  it("says an opened chat list by what it holds, counted and pluralised", () => {
    expect(switcherOpened(3)).toBe("Recent chats open. 3 chats.");
    expect(switcherOpened(1)).toBe("Recent chats open. 1 chat.");
  });

  it("says an opened EMPTY chat list in the list's own words", () => {
    expect(switcherOpened(0)).toBe(`Recent chats open. ${NO_OTHER_CHATS}.`);
  });

  it("names the chat list once, for the button, the list and the sentence alike", () => {
    expect(RECENT_CHATS).toBe("Recent chats");
    expect(switcherOpened(2).startsWith(`${RECENT_CHATS} `)).toBe(true);
  });
});
