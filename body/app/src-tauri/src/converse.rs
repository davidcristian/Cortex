//! The `converse` IPC command: run one brain turn and stream it to the webview.

use base64::Engine;
use base64::engine::general_purpose::STANDARD;
use body_core::{
    AttachedImage, BrainTransport, ConfirmDecision, RetryingTransport, TransportError, TurnEvent,
    retry_with, within_deadline,
};
use body_rpc::BrainRpcClient;
use futures_util::{StreamExt, pin_mut};
use serde::{Deserialize, Serialize};
use tauri::State;
use tauri::ipc::Channel;
use tokio_stream::wrappers::UnboundedReceiverStream;

use crate::brain::{ShellRandomness, TokioSleeper, plan_from_env, policy_from_env};
use crate::confirm::ConfirmRoute;

/// The default brain address, the same one `body_rpc` uses; override with `CORTEX_BRAIN_ADDR`.
const DEFAULT_ADDR: &str = "http://127.0.0.1:50051";

/// One streamed message to the overlay: exactly one field is set (serde skips the `None`), so the
/// wire is `{ "event": … }` or `{ "error": … }`, matching the `WireMessage` union in
/// `bridge/tauriBridge.ts`.
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
    Heartbeat {
        wait: String,
        detail: String,
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

impl WireEvent {
    /// The overlay's copy of `event`.
    fn from_turn(event: TurnEvent) -> Self {
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
            TurnEvent::Heartbeat { wait, detail } => Self::Heartbeat { wait, detail },
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
            TransportError::Timeout { after } => Self {
                kind: "timeout",
                message: format!("no reply within {after:?}"),
            },
        }
    }
}

impl WireMessage {
    fn event(event: TurnEvent) -> Self {
        Self {
            event: Some(WireEvent::from_turn(event)),
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

/// One attached picture from the overlay (matches `AttachedImage` in types.ts), its bytes in
/// standard base64 because IPC arguments are JSON.
#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct WireImage {
    data_base64: String,
    mime_type: String,
    width: u32,
    height: u32,
}

/// Decodes every picture, or names the first one whose bytes are not base64 as the brain names a
/// refused attachment: by its 1-based position.
fn decode_images(images: Vec<WireImage>) -> Result<Vec<AttachedImage>, TurnEvent> {
    images
        .into_iter()
        .enumerate()
        .map(|(index, image)| match STANDARD.decode(&image.data_base64) {
            Ok(data) => Ok(AttachedImage {
                data,
                mime_type: image.mime_type,
                width: image.width,
                height: image.height,
            }),
            Err(error) => Err(TurnEvent::Failed {
                code: String::from("attachment_refused"),
                message: format!("Attachment {} could not be read: {error}.", index + 1),
            }),
        })
        .collect()
}

/// Runs one conversational turn and streams it to `channel`. Connection and turn failures are
/// delivered on the channel rather than as a command error.
#[tauri::command]
pub async fn converse(
    session_id: String,
    text: String,
    images: Vec<WireImage>,
    channel: Channel<WireMessage>,
    route: State<'_, ConfirmRoute>,
) -> Result<(), String> {
    let images = match decode_images(images) {
        Ok(images) => images,
        Err(refused) => {
            let _ = channel.send(WireMessage::event(refused));
            return Ok(());
        }
    };
    let addr = std::env::var("CORTEX_BRAIN_ADDR").unwrap_or_else(|_| DEFAULT_ADDR.to_owned());
    let token = std::env::var("CORTEX_SEAM_TOKEN")
        .ok()
        .filter(|token| !token.is_empty());
    // Fail fast on a bad address or token, which no retry can fix, before spending the budget.
    if let Err(error) = BrainRpcClient::connect_lazy_with_token(&addr, token.as_deref()) {
        let _ = channel.send(WireMessage::error(error));
        return Ok(());
    }
    // Retrying the dial is safe: the turn itself has not started, so nothing is repeated.
    let sleeper = TokioSleeper;
    let randomness = ShellRandomness::from_env();
    let plan = plan_from_env();
    let deadline = Some(plan.call_deadline);
    let dial = retry_with(policy_from_env(), &sleeper, &randomness, || {
        within_deadline(
            deadline,
            &sleeper,
            BrainRpcClient::connect_with_token(&addr, token.as_deref()),
        )
    });
    let client = match dial.await {
        Ok(client) => client,
        Err(error) => {
            let _ = channel.send(WireMessage::error(error));
            return Ok(());
        }
    };
    let transport = RetryingTransport::new(client, TokioSleeper, plan);
    let (sender, receiver) = tokio::sync::mpsc::unbounded_channel::<ConfirmDecision>();
    let generation = route.set(sender);
    let decisions = UnboundedReceiverStream::new(receiver);
    let stream = transport.converse(&session_id, &text, images, decisions);
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
