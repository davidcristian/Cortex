//! The typed turn protocol: what the brain streams during a turn, and what answers it.

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ConfirmDecision {
    /// Echoes the `confirm_id` of the request being answered.
    pub confirm_id: String,
    /// `true` approves the gated call; `false` denies it.
    pub approved: bool,
}

/// One event from the brain during a `Converse` turn. This is the typed core mirror
/// of the proto `ServerEvent`, decoupling the overlay from the wire types.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum TurnEvent {
    /// A chunk of streamed assistant text (proto `TextDelta`).
    Delta(String),
    /// Audit-visible tool use, for the overlay to surface (proto `ToolActivity`).
    ToolActivity {
        /// The tool being invoked, e.g. `read_email`.
        tool_name: String,
        /// Human-readable summary of the activity.
        summary: String,
    },
    /// How an announced dispatch ENDED, arriving after it resolves (proto `ToolOutcome`, ADR-0029
    /// outcome addendum).
    ToolOutcome {
        /// The tool that ran, the same registry-authored name the activity carried.
        tool_name: String,
        /// The audit trail's own verdict: the dispatch returned a usable result.
        ok: bool,
    },
    /// Progress for the overlay to show, e.g. a model swap (proto `StatusUpdate`).
    Status {
        /// Machine-readable state name, e.g. `model_loading`.
        state: String,
        /// Human-readable detail.
        detail: String,
    },
    /// A gated (outbound/irreversible) tool call awaits the user's approval
    /// (proto `ConfirmRequest`, ADR-0022); **non-terminal**, because the turn is
    /// suspended brain-side until a matching [`ConfirmDecision`] arrives on
    ConfirmRequest {
        /// Correlation id minted by the brain; echo it in the decision.
        confirm_id: String,
        /// What would run, e.g. `send_email`.
        tool_name: String,
        /// The exact draft being approved, one JSON object that is the executed
        /// contract (what you approve is what runs).
        arguments_json: String,
        /// Why confirmation is required; shown to the user verbatim.
        reason: String,
    },
    /// A [`TurnEvent::ConfirmRequest`] the brain stopped waiting on (proto `ConfirmResolved`,
    /// ADR-0022 resolution addendum); **non-terminal**.
    ConfirmResolved {
        /// Which [`TurnEvent::ConfirmRequest`] ended.
        confirm_id: String,
        /// Why the wait ended: `"timeout"` or `"unavailable"`. It explains, and
        /// never authorizes: every outcome here means the gated call did not run.
        outcome: String,
    },
    /// The turn finished successfully (proto `TurnComplete`); terminal.
    Complete {
        /// Server-assigned turn id.
        turn_id: String,
    },
    /// The brain reported an error for this turn (proto `SeamError`); terminal.
    /// The connection is healthy. Contrast [`crate::transport::TransportError`].
    Failed {
        /// Application error code reported by the brain.
        code: String,
        /// Human-readable error message.
        message: String,
    },
}
