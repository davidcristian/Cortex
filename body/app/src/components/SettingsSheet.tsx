import { MARKS, type MarkStyle } from "../mark/marks";
import { THEMES } from "../theme/themes";
import { BubbleMark } from "./BubbleMark";

interface SettingsSheetProps {
  /** The chosen theme name, or `null` while the overlay follows the system scheme. */
  readonly themeName: string | null;
  readonly mark: MarkStyle;
  readonly animated: boolean;
  readonly onPickTheme: (name: string | null) => void;
  readonly onPickMark: (name: string) => void;
  readonly onClose: () => void;
}

/** One labelled row of choices. */
function Row({
  label,
  hint,
  children,
}: {
  readonly label: string;
  readonly hint: string;
  readonly children: React.ReactNode;
}) {
  return (
    <div className="set-row">
      <div className="set-label">
        <span>{label}</span>
        <span className="set-hint">{hint}</span>
      </div>
      <div className="set-choices">{children}</div>
    </div>
  );
}

/** The settings sheet (ADR-0032): where the overlay's appearance is chosen, and the answer to the
 *  mark picker having lived only on the empty state. It covers the panel like the shortcut sheet,
 *  closes on a click outside its card or on Esc (wired in `Overlay`), and every choice here is
 *  persisted to the brain's own settings record, so it survives a restart.
 *
 *  The theme row is the one place "follow the system" can be chosen: the header's toggle names
 *  the opposite theme outright and can only ever land on one of the two, so `Auto` would be
 *  unreachable without this. */
export function SettingsSheet({
  themeName,
  mark,
  animated,
  onPickTheme,
  onPickMark,
  onClose,
}: SettingsSheetProps) {
  return (
    <div className="sheet set-sheet" role="dialog" aria-label="Settings" onClick={onClose}>
      <div className="set-card" onClick={(event) => event.stopPropagation()}>
        <p className="sheet-head">Settings</p>
        <Row label="Theme" hint="Auto follows your system">
          <div className="set-seg" role="radiogroup" aria-label="Theme">
            <button
              className={`set-opt${themeName === null ? " on" : ""}`}
              type="button"
              role="radio"
              aria-checked={themeName === null}
              onClick={() => onPickTheme(null)}
            >
              Auto
            </button>
            {THEMES.map((theme) => (
              <button
                key={theme.name}
                className={`set-opt${themeName === theme.name ? " on" : ""}`}
                type="button"
                role="radio"
                aria-checked={themeName === theme.name}
                onClick={() => onPickTheme(theme.name)}
              >
                {theme.name}
              </button>
            ))}
          </div>
        </Row>
        <Row label="Mark" hint="The bubble shown while a turn runs">
          <div className="markmenu" role="radiogroup" aria-label="Mark style">
            {MARKS.map((choice) => (
              <button
                key={choice.name}
                className={`markopt${choice.name === mark.name ? " on" : ""}`}
                type="button"
                role="radio"
                aria-checked={choice.name === mark.name}
                title={choice.note}
                onClick={() => onPickMark(choice.name)}
              >
                <BubbleMark
                  style={choice}
                  size={34}
                  idPrefix={`set-${choice.name}`}
                  animated={animated}
                />
                <span>{choice.label}</span>
              </button>
            ))}
          </div>
        </Row>
        <p className="sheet-foot">Click outside or press Esc to close</p>
      </div>
    </div>
  );
}
