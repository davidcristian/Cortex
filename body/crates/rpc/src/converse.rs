//! `Converse` translation for `BrainSeamClient`, forming the streaming half of the
//! `body_core::BrainTransport` port.
//!
//! One turn per call (ADR-0011): send a `ClientEvent{session_id, user_turn}`
//! on a fresh stream, followed by one `confirm_response` per caller decision
//! (ADR-0022), and map each `ServerEvent` to a typed `TurnEvent`. The client
//! half-closes when the caller's decision stream ends (so a caller with no
//! confirm surface keeps the pre-confirm one-shot shape). The turn is terminal
//! on `TurnComplete` (→ [`TurnEvent::Complete`]) or `SeamError` (→
//! [`TurnEvent::Failed`] means the brain reported a turn error, the connection is
//! fine); a mid-turn `ConfirmRequest` (→ [`TurnEvent::ConfirmRequest`]) is
//! non-terminal. A stream that ends without a terminal event, or an empty
//! `ServerEvent`, is a [`TransportError::Protocol`]; a non-OK gRPC status maps
//! the same way `health` does (via [`crate::client::status_to_error`]).

use async_stream::stream;
use body_core::{ConfirmDecision, TransportError, TurnEvent};
use futures_core::Stream;
use tokio_stream::StreamExt;

use crate::client::{SeamChannel, status_to_error};
use crate::generated::brain_service_client::BrainServiceClient;
use crate::generated::{
    ClientEvent, ConfirmResponse, ServerEvent, UserTurn, client_event, server_event,
};

/// The one-turn client request: a single `UserTurn`, then one
/// `confirm_response` per decision, then end-of-stream when `decisions` ends
/// (ADR-0022 defines the caller's sender going away as the half-close). v1 sends
/// text only. `UserTurn.images` (vision) arrives in Slice 10 (ADR-0011).
fn turn_request(
    session_id: String,
    text: String,
    decisions: impl Stream<Item = ConfirmDecision> + Send + 'static,
) -> impl Stream<Item = ClientEvent> + Send {
    let user_turn = ClientEvent {
        session_id: session_id.clone(),
        event: Some(client_event::Event::UserTurn(UserTurn {
            text,
            images: Vec::new(),
        })),
    };
    tokio_stream::once(user_turn).chain(decisions.map(move |decision| ClientEvent {
        session_id: session_id.clone(),
        event: Some(client_event::Event::ConfirmResponse(ConfirmResponse {
            confirm_id: decision.confirm_id,
            approved: decision.approved,
        })),
    }))
}

/// Maps one `ServerEvent` to a `TurnEvent` (or a `Protocol` error for an empty
/// event) plus whether it is terminal for the turn (stop reading after it).
fn map_event(event: ServerEvent) -> (Result<TurnEvent, TransportError>, bool) {
    match event.event {
        Some(server_event::Event::TextDelta(delta)) => (Ok(TurnEvent::Delta(delta.text)), false),
        Some(server_event::Event::ToolActivity(activity)) => (
            Ok(TurnEvent::ToolActivity {
                tool_name: activity.tool_name,
                summary: activity.summary,
            }),
            false,
        ),
        Some(server_event::Event::Status(status)) => (
            Ok(TurnEvent::Status {
                state: status.state,
                detail: status.detail,
            }),
            false,
        ),
        Some(server_event::Event::ConfirmRequest(request)) => (
            Ok(TurnEvent::ConfirmRequest {
                confirm_id: request.confirm_id,
                tool_name: request.tool_name,
                arguments_json: request.arguments_json,
                reason: request.reason,
            }),
            false,
        ),
        Some(server_event::Event::TurnComplete(complete)) => (
            Ok(TurnEvent::Complete {
                turn_id: complete.turn_id,
            }),
            true,
        ),
        Some(server_event::Event::Error(error)) => (
            Ok(TurnEvent::Failed {
                code: error.code,
                message: error.message,
            }),
            true,
        ),
        None => (
            Err(TransportError::Protocol(String::from(
                "converse server event had no event set",
            ))),
            true,
        ),
    }
}

/// Runs one turn against the brain and yields typed `TurnEvent`s. See the
/// module docs and `BrainTransport::converse` for the contract.
pub(crate) fn converse_turn(
    mut client: BrainServiceClient<SeamChannel>,
    session_id: String,
    text: String,
    decisions: impl Stream<Item = ConfirmDecision> + Send + 'static,
) -> impl Stream<Item = Result<TurnEvent, TransportError>> + Send {
    stream! {
        let mut inbound = match client.converse(turn_request(session_id, text, decisions)).await {
            Ok(response) => response.into_inner(),
            Err(status) => {
                yield Err(status_to_error(&status));
                return;
            }
        };
        loop {
            match inbound.message().await {
                Ok(Some(event)) => {
                    let (mapped, terminal) = map_event(event);
                    yield mapped;
                    if terminal {
                        return;
                    }
                }
                Ok(None) => {
                    yield Err(TransportError::Protocol(String::from(
                        "converse stream ended before the turn completed",
                    )));
                    return;
                }
                Err(status) => {
                    yield Err(status_to_error(&status));
                    return;
                }
            }
        }
    }
}
