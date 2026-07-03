import { RingMark } from "./RingMark";

interface PreviewProps {
  readonly reply: string;
  readonly onClick: () => void;
}

/** The completed-while-minimized preview card: the mark, the reply, and the draining auto-fade
 *  bar (no caption text); the card appearing *is* the signal, and the bar says it will go. */
export function Preview({ reply, onClick }: PreviewProps) {
  return (
    <button className="preview" onClick={onClick} aria-label="Open reply" type="button">
      <div className="pv-row">
        <RingMark size={14} idPrefix="pv" strokeWidth={5} animated={false} />
        <div className="pv-b">{reply}</div>
      </div>
      <div className="bar" aria-hidden="true" />
    </button>
  );
}
