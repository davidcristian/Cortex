import type { PendingConfirm } from "../overlay/overlayState";
import { formatDraftValue } from "./draftValue";
import { ShieldIcon } from "./icons";

interface ConfirmCardProps {
  readonly confirm: PendingConfirm;
  readonly onRespond: (confirmId: string, approved: boolean) => void;
}

/**
 * The draft's fields as key and value rows, or `null` when `argumentsJson` is not a single JSON
 * object, in which case the card shows the raw string, since what the user approves is what runs
 * (ADR-0022).
 */
function parseDraft(argumentsJson: string): readonly (readonly [string, string])[] | null {
  try {
    const parsed: unknown = JSON.parse(argumentsJson);
    if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
      return null;
    }
    return Object.entries(parsed).map(([key, value]: [string, unknown]) => [
      key,
      formatDraftValue(value),
    ]);
  } catch {
    return null;
  }
}

/** The approval card (ADR-0022): a gated tool call paused mid-turn on the user's decision. It sits
 *  in the history's inline layer between bubbles, with neutral chrome and keys and values shown
 *  verbatim. The accent appears only on Approve, the one control that runs the action. */
export function ConfirmCard({ confirm, onRespond }: ConfirmCardProps) {
  const draft = parseDraft(confirm.argumentsJson);
  return (
    <div className="confirm" role="group" aria-label="Approval required">
      <div className="confirm-tool">
        <ShieldIcon />
        <span>{confirm.toolName}</span>
      </div>
      {draft === null ? (
        <div className="confirm-raw">{confirm.argumentsJson}</div>
      ) : (
        <dl className="confirm-draft">
          {draft.map(([key, value]) => (
            <div key={key} className="confirm-row">
              <dt>{key}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      )}
      <p className="confirm-reason">{confirm.reason}</p>
      <div className="confirm-actions">
        <button
          type="button"
          className="confirm-deny"
          onClick={() => onRespond(confirm.confirmId, false)}
        >
          Deny
        </button>
        <button
          type="button"
          className="confirm-approve"
          onClick={() => onRespond(confirm.confirmId, true)}
        >
          Approve
        </button>
      </div>
    </div>
  );
}
