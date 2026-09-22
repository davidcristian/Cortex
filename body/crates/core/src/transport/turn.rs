//! The typed turn protocol: what the brain streams during a turn, and what answers it.

/// The user's answer to a [`TurnEvent::ConfirmRequest`], sent back to the brain on the open
/// `Converse` stream.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ConfirmDecision {
    /// Echoes the `confirm_id` of the request being answered.
    pub confirm_id: String,
    /// `true` approves the call, `false` denies it.
    pub approved: bool,
}

/// One event from the brain during a `Converse` turn.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum TurnEvent {
    /// A chunk of streamed assistant text.
    Delta(String),
    /// Audit-visible tool use, for the overlay to surface.
    ToolActivity {
        /// The tool being invoked, e.g. `read_email`.
        tool_name: String,
        /// Human-readable summary of the activity.
        summary: String,
    },
    /// How an announced tool call ended, arriving after it resolves. Non-terminal.
    ToolOutcome {
        /// The tool that ran, under the same name the activity used.
        tool_name: String,
        /// Whether the call returned a usable result.
        ok: bool,
    },
    /// Progress for the overlay to show, e.g. a model swap.
    Status {
        /// Machine-readable state name, e.g. `model_loading`.
        state: String,
        /// Human-readable detail.
        detail: String,
    },
    /// An outbound or irreversible tool call is waiting for the user's approval. Non-terminal: the
    /// brain suspends the turn until a matching [`ConfirmDecision`] arrives, its own timeout denies
    /// the call, or the turn dies.
    ConfirmRequest {
        /// Correlation id minted by the brain; echo it in the decision.
        confirm_id: String,
        /// What would run, e.g. `send_email`.
        tool_name: String,
        /// The exact draft being approved, one JSON object; what is approved is what runs.
        arguments_json: String,
        /// Why confirmation is required; shown to the user verbatim.
        reason: String,
    },
    /// A [`TurnEvent::ConfirmRequest`] the brain stopped waiting on. Non-terminal.
    ConfirmResolved {
        /// Which [`TurnEvent::ConfirmRequest`] ended.
        confirm_id: String,
        /// Why the wait ended: `"timeout"` or `"unavailable"`.
        outcome: String,
    },
    /// The brain's turn is still running. Sent only while the stream is otherwise silent;
    /// [`crate::within_gaps`] counts it as a period of the turn's silence. Non-terminal.
    Heartbeat {
        /// What the turn waits on, one of the [`TurnEvent::Status`] states `thinking`, `queued`,
        /// `delegating`, `swapping`, `folding`, `calling` or `asking`; empty for none.
        wait: String,
        /// The sentence the overlay shows for `wait`.
        detail: String,
    },
    /// The turn finished successfully; terminal.
    Complete {
        /// Server-assigned turn id.
        turn_id: String,
    },
    /// The brain reported an error for this turn; terminal.
    Failed {
        /// Application error code reported by the brain.
        code: String,
        /// Human-readable error message.
        message: String,
    },
}
