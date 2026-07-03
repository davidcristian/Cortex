interface PreviewProps {
  readonly reply: string;
  readonly onClick: () => void;
}

/** The completed-while-minimized preview card: the reply and the draining auto-fade bar,
 *  nothing else. The card appearing *is* the signal, and the bar says it will go. */
export function Preview({ reply, onClick }: PreviewProps) {
  return (
    <button className="preview" onClick={onClick} aria-label="Open reply" type="button">
      <div className="pv-b">{reply}</div>
      <div className="bar" aria-hidden="true" />
    </button>
  );
}
