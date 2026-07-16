//! The `converse` IPC command: run one brain turn and stream it to the webview.

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

/// Runs one conversational turn and streams it to `channel`.
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
    if let Err(error) = BrainSeamClient::connect_lazy_with_token(&addr, token.as_deref()) {
        let _ = channel.send(WireMessage::error(error));
        return Ok(());
    }
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
    route.clear(generation);
    Ok(())
}
