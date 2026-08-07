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

/**
 * Whether a key landed in a field somebody is writing in, which is where `?` is a character and
 * not a shortcut.
 */
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
      // What counts as a chord is asked of `overlay/fieldKeys.ts` rather than restated here,
      // because the fields that stand in front of this listener answer the same question and the
      // two must not drift into disagreeing about one key.
      const mod = chord(event);
      if (event.key === "Escape") {
        // One press out of the console, whichever tab is up: it is one view now, not a settings
        // sheet stacked on a shortcut sheet, so nothing is left behind to press Esc at again.
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
        // Announced, for the reason the fresh chat's own two doors differ by: a key names nothing
        // and moves nothing, so an opened list would arrive in silence (`overlay/notice.ts`).
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
        // Silent: the chats button carries `aria-expanded`, and the caret that pressed it is
        // standing on it, so the state is read back where the reader already is.
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
