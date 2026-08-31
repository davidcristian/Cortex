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

// The mode router: the panel is always mounted, while the orb and preview mount only in their
// modes. It also owns the global keys, which stay live while the panel is off screen. A field with
// focus may take a press first, which the switcher's rename editor does and the composer does not.

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

/** Whether a key arrived in a field somebody is writing in, where `?` is a character rather than
 *  a shortcut. Both element types are tested rather than a list of selectors, so the next field
 *  added to the overlay is covered without a change here. */
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
      // because the fields that take keys before this listener ask the same question.
      const mod = chord(event);
      if (event.key === "Escape") {
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
        // Announced: a key has no label and moves no caret, so the opened list would otherwise
        // arrive silently.
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
        // Not announced: the chats button has `aria-expanded` and keeps the caret that pressed
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
