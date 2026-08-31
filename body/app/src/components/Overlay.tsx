import { useEffect } from "react";

import type { EdgeStyle } from "../edge/edges";
import type { MarkStyle } from "../mark/marks";
import { chord } from "../overlay/fieldKeys";
import { latestReply } from "../overlay/overlayState";
import type { OverlayController } from "../overlay/useOverlay";
import { Announcer } from "./Announcer";
import { Orb } from "./Orb";
import { Panel } from "./Panel";
import { Preview } from "./Preview";

// The mode router: the panel is always mounted (its `open` class drives the enter and travel
// animations), while the orb and preview mount only in their modes. It also owns the global keys.
// Esc leaves the console in one press, whichever tab is up, and otherwise dismisses the panel (to
// the orb mid-stream); Ctrl/Cmd+N starts a new chat, Ctrl+↑/↓ cycle recent chats, Ctrl+K toggles
// the switcher (ADR-0021), and ? toggles the console's shortcuts tab outside any field, where it
// would just be a typed character. All six stay live while the panel is not on screen, and all six
// bring the surface they act on into view: the swap keys always did, and Ctrl+K and ? do since the
// rule that a key aimed at a surface summons that surface (`overlay/chromeState.ts`, ADR-0035
// addendum). A field with focus may swallow a press before this listener sees it, which the
// switcher's rename editor does; the composer does not, its text surviving every one of these keys
// (`overlay/fieldKeys.ts`).
//
// It also holds the overlay's live region, which is here rather than in the panel because the panel
// is out of the accessibility tree whenever it is shut and these keys stay live (`Announcer`). Both
// ways of starting a fresh chat appear in this file and they differ: the key announces, and the
// header's pencil is bound silent because its label already says where it goes (`overlay/notice.ts`
// carries the whole rule). The switcher's two entry points differ the same way and for the same
// reason, the chats button carrying the state the key would otherwise have to announce.
interface OverlayProps {
  readonly controller: OverlayController;
  readonly dark: boolean;
  readonly mark: MarkStyle;
  readonly edge: EdgeStyle;
  readonly themeName: string | null;
  readonly onPickTheme: (name: string | null) => void;
  readonly onPickMark: (name: string) => void;
  readonly onPickEdge: (name: string) => void;
  readonly onToggleTheme: () => void;
}

/** Whether a key landed in a field somebody is writing in, where `?` is a character rather than a
 *  shortcut. It named the composer's textarea alone for as long as that was the overlay's only
 *  field. The switcher's rename editor is an `<input>`, and the pencil now puts the caret in it
 *  (`overlay/rowCaret.ts`), so typing a question into it opened the console over the row being
 *  renamed (measured at 900x900: "why?" left `why` in the field and the settings pane up). This
 *  tests the two element types rather than a list of selectors, so the next field added to the
 *  overlay is covered on the day it is written. */
function typing(target: EventTarget | null): boolean {
  return target instanceof HTMLTextAreaElement || target instanceof HTMLInputElement;
}

export function Overlay({
  controller,
  dark,
  mark,
  edge,
  themeName,
  onPickTheme,
  onPickMark,
  onPickEdge,
  onToggleTheme,
}: OverlayProps) {
  const {
    state,
    submit,
    setDraft,
    stop,
    dismiss,
    open,
    newChat,
    openSession,
    renameSession,
    deleteSession,
    setSessionPinned,
    cyclePrev,
    cycleNext,
    toggleSwitcher,
    openConsole,
    toggleConsole,
    closeConsole,
    previewHover,
    respondConfirm,
    dismissReminder,
  } = controller;

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      // What counts as a chord comes from `overlay/fieldKeys.ts` rather than being restated here,
      // because the fields that intercept keys before this listener ask the same question and the
      // two must not disagree about one key.
      const mod = chord(event);
      if (event.key === "Escape") {
        // One press leaves the console, whichever tab is up, because it is one view rather than a
        // settings sheet stacked on a shortcut sheet, so no second surface is left underneath.
        if (state.consoleTab !== null) {
          closeConsole();
        } else if (state.mode !== "hidden") {
          dismiss();
        }
      } else if (event.key === "?" && !typing(event.target)) {
        event.preventDefault();
        toggleConsole("shortcuts");
      } else if (mod && event.key.toLowerCase() === "n") {
        event.preventDefault();
        newChat(true);
      } else if (mod && event.key.toLowerCase() === "k") {
        event.preventDefault();
        // Announced, for the same reason the two ways of starting a fresh chat differ: a key has no
        // label and moves no caret, so an opened list would arrive silently (`overlay/notice.ts`).
        toggleSwitcher(true);
      } else if (mod && event.key === "ArrowUp") {
        event.preventDefault();
        cyclePrev();
      } else if (mod && event.key === "ArrowDown") {
        event.preventDefault();
        cycleNext();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [
    state.mode,
    state.consoleTab,
    dismiss,
    newChat,
    toggleSwitcher,
    toggleConsole,
    closeConsole,
    cyclePrev,
    cycleNext,
  ]);

  return (
    <>
      <Announcer notice={state.notice} />
      <Panel
        state={state}
        open={state.mode === "panel"}
        dark={dark}
        mark={mark}
        edge={edge}
        themeName={themeName}
        onPickTheme={onPickTheme}
        onPickMark={onPickMark}
        onPickEdge={onPickEdge}
        onToggleConsole={toggleConsole}
        onOpenConsole={openConsole}
        onCloseConsole={closeConsole}
        onToggleTheme={onToggleTheme}
        onSubmit={submit}
        onDraft={setDraft}
        onStop={stop}
        onDismiss={dismiss}
        onNewChat={() => newChat(false)}
        // Not announced: the chats button carries `aria-expanded` and keeps the caret that pressed
        // it, so the state is read back where the reader already is.
        onToggleSwitcher={() => toggleSwitcher(false)}
        onSelectSession={openSession}
        onRenameSession={renameSession}
        onDeleteSession={deleteSession}
        onPinSession={setSessionPinned}
        onRespondConfirm={respondConfirm}
        onDismissReminder={dismissReminder}
      />
      {state.mode === "orb" ? <Orb style={mark} onClick={open} /> : null}
      {state.mode === "preview" ? (
        <Preview reply={latestReply(state)} onClick={open} onHover={previewHover} />
      ) : null}
    </>
  );
}
