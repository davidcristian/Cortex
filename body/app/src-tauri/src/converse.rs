//! The `converse` IPC command: run one brain turn and stream it to the webview.
//!
//! Thin glue. It connects a `BrainSeamClient` (gated `body_rpc`), drives the
//! `TurnEvent` stream, and forwards each item to the frontend over a Tauri
//! `Channel` as a `WireMessage` mirroring `bridge/tauriBridge.ts`. All seam logic
//! lives in `body_rpc`; the mapping here is mechanical. The eager dial is wrapped
//! in `retry_with` (ADR-0024 addendum): retrying a *dial* is safe because the
//! non-idempotent turn has not begun, while a turn that fails after its first
//! event stays terminal (decision 2).

use body_core::{BrainTransport, ConfirmDecision, TransportError, TurnEvent, retry_with};
use body_rpc::BrainSeamClient;
use futures_util::{StreamExt, pin_mut};
use serde::Serialize;
use tauri::State;
use tauri::ipc::Channel;
use tokio_stream::wrappers::UnboundedReceiverStream;

use crate::confirm::ConfirmRoute;
use crate::seam::{ShellRandomness, TokioSleeper, policy_from_env};

/// Default brain seam address (matches `body_rpc`); override with `CORTEX_BRAIN_ADDR`.
const DEFAULT_ADDR: &str = "http://127.0.0.1:50051";

/// One streamed message to the overlay: exactly one field is set (serde skips the
/// `None`), so the wire is `{ "event": … }` or `{ "error": … }`, matching the `WireMessage`
/// union in `bridge/tauriBridge.ts`.
#[derive(Serialize)]
pub struct WireMessage {
    #[serde(skip_serializing_if = "Option::is_none")]
    event: Option<WireEvent>,
    #[serde(skip_serializing_if = "Option::is_none")]
    error: Option<WireError>,
}

/// The `TurnEvent` mirror sent to the overlay (matches `TurnEvent` in types.ts).
#[derive(Serialize)]
#[serde(
    tag = "kind",
    rename_all = "camelCase",
    rename_all_fields = "camelCase"
)]
enum WireEvent {
    Delta {
        text: String,
    },
    ToolActivity {
        tool_name: String,
        summary: String,
    },
    ToolOutcome {
        tool_name: String,
        ok: bool,
    },
    Status {
        state: String,
        detail: String,
    },
    ConfirmRequest {
        confirm_id: String,
        tool_name: String,
        arguments_json: String,
        reason: String,
    },
    ConfirmResolved {
        confirm_id: String,
        outcome: String,
    },
    Complete {
        turn_id: String,
    },
    Failed {
        code: String,
        message: String,
    },
}

/// The `TransportError` mirror (matches `TransportError` in types.ts).
#[derive(Serialize)]
struct WireError {
    kind: &'static str,
    message: String,
}

impl From<TurnEvent> for WireEvent {
    fn from(event: TurnEvent) -> Self {
        match event {
            TurnEvent::Delta(text) => Self::Delta { text },
            TurnEvent::ToolActivity { tool_name, summary } => {
                Self::ToolActivity { tool_name, summary }
            }
            TurnEvent::ToolOutcome { tool_name, ok } => Self::ToolOutcome { tool_name, ok },
            TurnEvent::Status { state, detail } => Self::Status { state, detail },
            TurnEvent::ConfirmRequest {
                confirm_id,
                tool_name,
                arguments_json,
                reason,
            } => Self::ConfirmRequest {
                confirm_id,
                tool_name,
                arguments_json,
                reason,
            },
            TurnEvent::ConfirmResolved {
                confirm_id,
                outcome,
            } => Self::ConfirmResolved {
                confirm_id,
                outcome,
            },
            TurnEvent::Complete { turn_id } => Self::Complete { turn_id },
            TurnEvent::Failed { code, message } => Self::Failed { code, message },
        }
    }
}

impl From<TransportError> for WireError {
    fn from(error: TransportError) -> Self {
        match error {
            TransportError::Connection(message) => Self {
                kind: "connection",
                message,
            },
            TransportError::Rpc { code, message } => Self {
                kind: "rpc",
                message: format!("{code}: {message}"),
            },
            TransportError::Protocol(message) => Self {
                kind: "protocol",
                message,
            },
        }
    }
}

impl WireMessage {
    fn event(event: TurnEvent) -> Self {
        Self {
            event: Some(event.into()),
            error: None,
        }
    }

    fn error(error: TransportError) -> Self {
        Self {
            event: None,
            error: Some(error.into()),
        }
    }
}

/// Runs one conversational turn and streams it to `channel`. Session continuity
/// is external (the brain persists it), so each call is independent and shares a
/// stable `session_id`. Returns `Ok(())` once the stream ends; connection and
/// turn failures are delivered on the channel, not as a command error.
///
/// Mid-turn confirm answers (ADR-0022) arrive out of band via the
/// `confirm_response` command: this command parks the turn's decision sender in
/// the managed [`ConfirmRoute`] for the duration of its event loop, and the
/// receiver is chained onto the open request stream by `body_rpc`.
#[tauri::command]
pub async fn converse(
    session_id: String,
    text: String,
    channel: Channel<WireMessage>,
    route: State<'_, ConfirmRoute>,
) -> Result<(), String> {
    let addr = std::env::var("CORTEX_BRAIN_ADDR").unwrap_or_else(|_| DEFAULT_ADDR.to_owned());
    // The shared seam secret (ADR-0016): same env var the brain reads; empty = auth off.
    let token = std::env::var("CORTEX_SEAM_TOKEN")
        .ok()
        .filter(|token| !token.is_empty());
    // Fail fast on a permanent misconfiguration (bad URI / non-ASCII token) before retrying:
    // the lazy constructor validates both synchronously without dialing (the same check the
    // read path fails fast on), so a config error no retry can fix surfaces at once instead
    // of burning the retry budget.
    if let Err(error) = BrainSeamClient::connect_lazy_with_token(&addr, token.as_deref()) {
        let _ = channel.send(WireMessage::error(error));
        return Ok(());
    }
    // The patient dial (ADR-0024 addendum): with config already validated, a brain mid-restart
    // refuses the first connect, so retry_with backs off and re-dials before the turn is
    // declared failed. The turn itself has not started, so nothing non-idempotent is repeated.
    // The effects are bound to locals because the retry future borrows them for its whole run.
    let sleeper = TokioSleeper;
    let randomness = ShellRandomness::from_env();
    let dial = retry_with(policy_from_env(), &sleeper, &randomness, || {
        BrainSeamClient::connect_with_token(&addr, token.as_deref())
    });
    let client = match dial.await {
        Ok(client) => client,
        Err(error) => {
            let _ = channel.send(WireMessage::error(error));
            return Ok(());
        }
    };
    let (sender, receiver) = tokio::sync::mpsc::unbounded_channel::<ConfirmDecision>();
    let generation = route.set(sender);
    let stream = client.converse(&session_id, &text, UnboundedReceiverStream::new(receiver));
    pin_mut!(stream);
    while let Some(item) = stream.next().await {
        let message = match item {
            Ok(event) => WireMessage::event(event),
            Err(error) => WireMessage::error(error),
        };
        if channel.send(message).is_err() {
            break;
        }
    }
    // The turn is over: drop the route so a late answer is a no-op (the brain
    // denies an unanswered confirm by timeout, so it is fail-closed). Compare-and-clear
    // by generation so a superseded turn ending late cannot wipe the live turn's
    // route (a newer turn already reclaimed the slot).
    route.clear(generation);
    Ok(())
}
