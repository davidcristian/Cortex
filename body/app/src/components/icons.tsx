import type { ReactNode } from "react";

// The header's outline icon set (design/overlay-ux.md §3) is one vocabulary with the theme
// toggle: 1.7px round-cap strokes on a 24 grid, `currentColor`, hollow. Kept tiny and static
// so the buttons stay presentational; state and behavior live in the reducer/hook.
function Icon({ children }: { readonly children: ReactNode }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width="16"
      height="16"
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {children}
    </svg>
  );
}

/** Recent chats (the switcher): two overlapping speech bubbles for "your conversations". */
export function ChatsIcon() {
  return (
    <Icon>
      <path d="M21 13.5l-2.6 -2.5h-6.4a1 1 0 0 1 -1 -1v-4.5a1 1 0 0 1 1 -1h8a1 1 0 0 1 1 1z" />
      <path d="M13 14.5v1.5a1 1 0 0 1 -1 1h-6l-2.6 2.5v-8.5a1 1 0 0 1 1 -1h2" />
    </Icon>
  );
}

/** New chat: a pencil for "compose a new one". */
export function PencilIcon() {
  return (
    <Icon>
      <path d="M4 20h4l10.5 -10.5a2.83 2.83 0 0 0 -4 -4l-10.5 10.5v4" />
      <path d="M13.5 6.5l4 4" />
    </Icon>
  );
}

/** Settings: three sliders, not a gear. The console holds choices to set, not machinery to
 *  configure, and sliders read as taste while a gear reads as plumbing. */
export function SlidersIcon() {
  return (
    <Icon>
      <path d="M4 7h9" />
      <path d="M17 7h3" />
      <path d="M4 17h4" />
      <path d="M12 17h8" />
      <circle cx="15" cy="7" r="2" />
      <circle cx="10" cy="17" r="2" />
    </Icon>
  );
}

/** Dismiss: a downward chevron for "tuck it away" (the chat is saved; re-summon restores it). */
export function TuckIcon() {
  return (
    <Icon>
      <path d="M7 10l5 5l5 -5" />
    </Icon>
  );
}

/** Gated action: a hollow shield. This call runs only with the user's approval (ADR-0022). */
export function ShieldIcon() {
  return (
    <Icon>
      <path d="M12 3.5l7 2.6v5.4c0 4.3 -2.9 7.7 -7 9c-4.1 -1.3 -7 -4.7 -7 -9V6.1z" />
    </Icon>
  );
}

/** A due reminder: a hollow bell, the one thing on screen the user did not just ask for. */
export function BellIcon() {
  return (
    <Icon>
      <path d="M6 9a6 6 0 0 1 12 0c0 3.5 .8 5.2 1.5 6h-15c.7 -.8 1.5 -2.5 1.5 -6" />
      <path d="M10 18a2 2 0 0 0 4 0" />
    </Icon>
  );
}

/** Delete a chat: an outline trash can. The one destructive control, so it reads as removal, not
 *  the dismiss chevron (which tucks a saved chat away) or the check (which acks, never deletes). */
export function TrashIcon() {
  return (
    <Icon>
      <path d="M5 7h14" />
      <path d="M9 7V5.5a1 1 0 0 1 1 -1h4a1 1 0 0 1 1 1V7" />
      <path d="M6.5 7l.8 11a1 1 0 0 0 1 1h7.4a1 1 0 0 0 1 -1l.8 -11" />
    </Icon>
  );
}

/** Pin a chat: a pushpin that keeps a chat reachable above the recency window (ADR-0021 pinning
 *  addendum). `filled` inks the head solid for a currently-pinned row, so the one control both
 *  toggles the pin and shows its state, the way the rename pencil and delete trash read. */
export function PinIcon({ filled = false }: { readonly filled?: boolean }) {
  return (
    <Icon>
      <path d="M12 17v4" />
      <path
        d="M9 3.5h6l-.6 5.2 2.4 2.1a1 1 0 0 1 .3.75V13H6v-1.45a1 1 0 0 1 .3-.75l2.4-2.1z"
        fill={filled ? "currentColor" : "none"}
      />
    </Icon>
  );
}

/** Cancel an inline action (an X): back out of the delete confirmation without deleting. */
export function CloseIcon() {
  return (
    <Icon>
      <path d="M7 7l10 10" />
      <path d="M17 7l-10 10" />
    </Icon>
  );
}

/** Dismiss a reminder: a check for "got it", never an X. Acking is delivery, not cancellation:
 *  a recurring series re-arms afterwards, so the glyph must not read as "delete this". */
export function CheckIcon() {
  return (
    <Icon>
      <path d="M5 12.5l4.5 4.5l9.5 -10" />
    </Icon>
  );
}

/** Send: an up arrow to submit the prompt. */
export function SendIcon() {
  return (
    <Icon>
      <path d="M12 19V6" />
      <path d="M6.5 11.5L12 6l5.5 5.5" />
    </Icon>
  );
}

/** Stop: a filled rounded square to cancel the streaming turn. */
export function StopIcon() {
  return (
    <Icon>
      <rect x="7.5" y="7.5" width="9" height="9" rx="2.4" fill="currentColor" />
    </Icon>
  );
}

/** Keycap glyph: the return arrow (Enter). */
export function ReturnKey() {
  return (
    <Icon>
      <path d="M20 7v3a2.5 2.5 0 0 1 -2.5 2.5H6" />
      <path d="M9 9.5L5.5 12.5L9 15.5" />
    </Icon>
  );
}

/** Keycap glyph: the Shift key. */
export function ShiftKey() {
  return (
    <Icon>
      <path d="M12 4.5l6 6.5h-3.2v6h-5.6v-6H6z" />
    </Icon>
  );
}

/** Keycap glyph: the up-arrow key (cycle to a newer chat). */
export function UpArrowKey() {
  return (
    <Icon>
      <path d="M12 18V6.8" />
      <path d="M7.5 11L12 6.5L16.5 11" />
    </Icon>
  );
}

/** Keycap glyph: the down-arrow key (cycle to an older chat). */
export function DownArrowKey() {
  return (
    <Icon>
      <path d="M12 6v11.2" />
      <path d="M7.5 13L12 17.5L16.5 13" />
    </Icon>
  );
}
