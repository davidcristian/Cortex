import { useEffect } from "react";

import type { MarkStyle } from "../mark/marks";
import { latestReply } from "../overlay/overlayState";
import type { OverlayController } from "../overlay/useOverlay";
import { Orb } from "./Orb";
import { Panel } from "./Panel";
import { Preview } from "./Preview";

// The mode router: the panel is always mounted (its `open` class drives the enter/travel
// animation); the orb and preview mount only in their modes. Also owns the global keys. Esc
// leaves the console in ONE press, whichever tab is up, else dismisses (→ orb mid-stream);
// Ctrl/Cmd+N starts a new chat, Ctrl+↑/↓ cycle recent chats, Ctrl+K toggles the switcher
// (ADR-0021), and ? (outside the composer, where it is just typing) toggles the console's
// shortcuts tab.
interface OverlayProps {
  readonly controller: OverlayController;
  readonly dark: boolean;
  readonly mark: MarkStyle;
  readonly themeName: string | null;
  readonly onPickTheme: (name: string | null) => void;
  readonly onPickMark: (name: string) => void;
  readonly onToggleTheme: () => void;
}

export function Overlay({
  controller,
  dark,
  mark,
  themeName,
  onPickTheme,
  onPickMark,
  onToggleTheme,
}: OverlayProps) {
  const {
    state,
    submit,
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
      const mod = event.ctrlKey || event.metaKey;
      if (event.key === "Escape") {
        // One press out of the console, whichever tab is up: it is one view now, not a settings
        // sheet stacked on a shortcut sheet, so nothing is left behind to press Esc at again.
        if (state.consoleTab !== null) {
          closeConsole();
        } else if (state.mode !== "hidden") {
          dismiss();
        }
      } else if (event.key === "?" && !(event.target instanceof HTMLTextAreaElement)) {
        event.preventDefault();
        toggleConsole("shortcuts");
      } else if (mod && event.key.toLowerCase() === "n") {
        event.preventDefault();
        newChat();
      } else if (mod && event.key.toLowerCase() === "k") {
        event.preventDefault();
        toggleSwitcher();
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
      <Panel
        state={state}
        open={state.mode === "panel"}
        dark={dark}
        mark={mark}
        themeName={themeName}
        onPickTheme={onPickTheme}
        onPickMark={onPickMark}
        onToggleConsole={toggleConsole}
        onOpenConsole={openConsole}
        onCloseConsole={closeConsole}
        onToggleTheme={onToggleTheme}
        onSubmit={submit}
        onStop={stop}
        onDismiss={dismiss}
        onNewChat={newChat}
        onToggleSwitcher={toggleSwitcher}
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
