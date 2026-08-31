//! The typed turn protocol: what the brain streams during a turn, and what answers it.
//!
//! [`TurnEvent`] is the typed core mirror of the proto `ServerEvent`, and [`ConfirmDecision`]
//! is the one client event a caller sends back mid turn. Both are re-exported from
//! `transport`, so `body_core::transport::TurnEvent` and the crate root still resolve; they
//! were split out of `transport.rs` for the 300-line cap.
//!
//! Pure data: no tonic, no network, no I/O. The wire translation lives in `body/crates/rpc`.

/// The user's answer to a [`TurnEvent::ConfirmRequest`] (ADR-0022): fed into
/// [`crate::transport::BrainTransport::converse`]'s `decisions` stream and delivered to the
/// brain as a `ConfirmResponse` client event on the open `Converse` stream.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ConfirmDecision {
    /// Echoes the `confirm_id` of the request being answered.
    pub confirm_id: String,
    /// `true` approves the gated call; `false` denies it.
    pub approved: bool,
}

/// One event from the brain during a `Converse` turn. This is the typed core mirror
/// of the proto `ServerEvent`, decoupling the overlay from the wire types.
///
/// Streamed by [`crate::transport::BrainTransport::converse`] as the `Ok` side of each item;
/// transport failures are the `Err` side ([`crate::transport::TransportError`]). A
/// brain-reported mid-turn error is [`TurnEvent::Failed`], meaning the connection is healthy
/// and this turn failed, which an `Err` cannot say: an `Err` means the brain could not be
/// reached or streamed data the adapter could not interpret.
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
    /// How an announced dispatch ended, arriving after it resolves (proto `ToolOutcome`,
    /// ADR-0029 outcome addendum); non-terminal. The brain emits one per activity the turn
    /// itself dispatched, on every path out of that dispatch.
    ///
    /// Two constraints bind consumers, argued in ADR-0029 (the outcome and delegated-pairing
    /// addenda) and restated in `docs/modules/body-core.md`. An activity that never receives
    /// an outcome is ordinary rather than an error, because a delegating turn also surfaces
    /// its subagents' tool steps as [`TurnEvent::ToolActivity`] over a side channel that
    /// carries no outcome, and those are indistinguishable here from the turn's own. And an
    /// outcome may only strengthen what a surface already claims: a capture that failed after
    /// the shutter fired looks the same here as one that never happened, so `ok: false` means
    /// the brain cannot say the screen was read, not that it was never read.
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
    /// A gated (outbound or irreversible) tool call awaits the user's approval
    /// (proto `ConfirmRequest`, ADR-0022); non-terminal, because the turn is
    /// suspended brain-side until a matching [`ConfirmDecision`] arrives on
    /// the `decisions` stream, the brain's timeout denies, or the turn dies.
    ConfirmRequest {
        /// Correlation id minted by the brain; echo it in the decision.
        confirm_id: String,
        /// What would run, e.g. `send_email`.
        tool_name: String,
        /// The exact draft being approved, one JSON object; what is approved is
        /// what runs.
        arguments_json: String,
        /// Why confirmation is required; shown to the user verbatim.
        reason: String,
    },
    /// A [`TurnEvent::ConfirmRequest`] the brain stopped waiting on (proto
    /// `ConfirmResolved`, ADR-0022 resolution addendum); non-terminal. It
    /// arrives only for endings the caller cannot already know, namely the
    /// brain's confirm timeout and its input stream half-closing, so a surface
    /// showing the question can close it rather than leave it answerable after
    /// the brain has stopped listening. The user's own answer is never echoed
    /// back, and a turn that dies is closed by its terminal event instead.
    ConfirmResolved {
        /// Which [`TurnEvent::ConfirmRequest`] ended.
        confirm_id: String,
        /// Why the wait ended: `"timeout"` or `"unavailable"`. Both mean the
        /// gated call did not run, so neither authorizes anything.
        outcome: String,
    },
    /// The turn finished successfully (proto `TurnComplete`); terminal.
    Complete {
        /// Server-assigned turn id.
        turn_id: String,
    },
    /// The brain reported an error for this turn (proto `SeamError`); terminal.
    /// The connection is healthy, unlike [`crate::transport::TransportError`].
    Failed {
        /// Application error code reported by the brain.
        code: String,
        /// Human-readable error message.
        message: String,
    },
}
