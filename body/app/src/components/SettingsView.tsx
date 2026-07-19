import { MARKS, type MarkStyle } from "../mark/marks";
import { THEMES } from "../theme/themes";
import { BubbleMark } from "./BubbleMark";
import { PanelView } from "./PanelView";

interface SettingsViewProps {
  /** The chosen theme name, or `null` while the overlay follows the system scheme. */
  readonly themeName: string | null;
  readonly mark: MarkStyle;
  readonly animated: boolean;
  readonly onPickTheme: (name: string | null) => void;
  readonly onPickMark: (name: string) => void;
  readonly onClose: () => void;
}

/** One settings row: what it is on the left, what it can be on the right. */
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
    <div className="row">
      <span className="row-label">
        {label}
        <small>{hint}</small>
      </span>
      {children}
    </div>
  );
}

/** Where the overlay's appearance is chosen (ADR-0032), and the answer to the mark picker having
 *  lived only on the empty state. Every choice is persisted to the brain's own settings record, so
 *  it survives a restart.
 *
 *  A row is a label and its choices, nothing else: with two settings in it the view is barely
 *  taller than the header, and the panel shrinks to match rather than dressing the emptiness up.
 *  The theme row is the one place "follow the system" can be chosen, since the header's toggle
 *  names the opposite theme outright and can only ever land on one of the two. */
export function SettingsView({
  themeName,
  mark,
  animated,
  onPickTheme,
  onPickMark,
  onClose,
}: SettingsViewProps) {
  return (
    <PanelView title="Settings" onClose={onClose}>
      <div className="rows">
        <Row label="Theme" hint="Auto follows your system">
          <div className="seg" role="radiogroup" aria-label="Theme">
            <button
              className={`seg-opt${themeName === null ? " on" : ""}`}
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
                className={`seg-opt${themeName === theme.name ? " on" : ""}`}
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
        {/* Drawn live, not named: the styles differ by how they move, so the choice is made by
            watching them rather than by reading four labels. */}
        <Row label="Mark" hint="Shown while a turn runs">
          <div className="seg" role="radiogroup" aria-label="Mark style">
            {MARKS.map((choice) => (
              <button
                key={choice.name}
                className={`seg-mark${choice.name === mark.name ? " on" : ""}`}
                type="button"
                role="radio"
                aria-label={choice.label}
                aria-checked={choice.name === mark.name}
                title={choice.note}
                onClick={() => onPickMark(choice.name)}
              >
                <BubbleMark
                  style={choice}
                  size={26}
                  idPrefix={`set-${choice.name}`}
                  animated={animated}
                />
              </button>
            ))}
          </div>
        </Row>
      </div>
    </PanelView>
  );
}
