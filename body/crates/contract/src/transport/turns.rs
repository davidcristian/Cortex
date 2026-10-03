//! The turn checks in `TRANSPORT_CHECKS`.

use std::future::poll_fn;
use std::pin::Pin;
use std::task::{Context, Poll};

use body_core::{ConfirmDecision, TransportError, TurnEvent};
use futures_core::Stream;

use super::checks::{kind, refused, two_chats};
use super::{Calls, Held, Pending, TransportSubject};

/// A caller with no confirm decisions to send, whose stream ends at once.
struct NoDecisions;

impl Stream for NoDecisions {
    type Item = ConfirmDecision;

    fn poll_next(self: Pin<&mut Self>, _cx: &mut Context<'_>) -> Poll<Option<ConfirmDecision>> {
        Poll::Ready(None)
    }
}

/// Runs one turn on `session_id` and collects every item the transport streams.
async fn turn(
    transport: &dyn Calls,
    session_id: &str,
    text: &str,
) -> Vec<Result<TurnEvent, TransportError>> {
    let mut events = transport.converse(session_id, text, Vec::new(), Box::pin(NoDecisions));
    let mut items = Vec::new();
    while let Some(item) = poll_fn(|cx| events.as_mut().poll_next(cx)).await {
        items.push(item);
    }
    items
}

fn replying(reply: Vec<TurnEvent>) -> Held {
    Held {
        reply,
        ..two_chats()
    }
}

fn delta(text: &str) -> TurnEvent {
    TurnEvent::Delta(String::from(text))
}

/// A turn the brain fails, with the code and message it reports.
fn overloaded() -> TurnEvent {
    TurnEvent::Failed {
        code: String::from("overloaded"),
        message: String::from("brain is busy"),
    }
}

/// One event of every kind, in the order a brain may send them, ending at the completion.
fn every_kind() -> Vec<TurnEvent> {
    vec![
        delta("checking your mail"),
        TurnEvent::ToolActivity {
            tool_name: String::from("read_email"),
            summary: String::from("reading inbox"),
        },
        TurnEvent::ToolOutcome {
            tool_name: String::from("read_email"),
            ok: false,
        },
        TurnEvent::Heartbeat {
            wait: String::from("calling"),
            detail: String::from("waiting for a tool to finish"),
        },
        TurnEvent::Status {
            state: String::from("model_loading"),
            detail: String::from("swapping"),
        },
        TurnEvent::ConfirmRequest {
            confirm_id: String::from("confirm-7"),
            tool_name: String::from("send_email"),
            arguments_json: String::from("{\"to\":\"x@y\"}"),
            reason: String::from("outbound and irreversible"),
        },
        TurnEvent::ConfirmResolved {
            confirm_id: String::from("confirm-7"),
            outcome: String::from("timeout"),
        },
        TurnEvent::Complete {
            turn_id: String::from("turn-1"),
        },
    ]
}

pub(super) fn a_turn_streams_the_held_reply_in_order(
    subject: &dyn TransportSubject,
) -> Pending<'_> {
    Box::pin(async move {
        let transport = subject.serving(&replying(every_kind()));
        let streamed = every_kind().into_iter().map(Ok).collect::<Vec<_>>();
        assert_eq!(
            turn(transport.as_ref(), "beta", "any mail?").await,
            streamed
        );
    })
}

pub(super) fn a_turn_adds_the_user_s_words_to_its_chat(
    subject: &dyn TransportSubject,
) -> Pending<'_> {
    Box::pin(async move {
        let held = replying(every_kind());
        let transport = subject.serving(&held);
        turn(transport.as_ref(), "alpha", "and lunch at one").await;
        let found = transport
            .session_messages("alpha")
            .await
            .unwrap_or_default();
        let words = found.into_iter().map(|said| (said.role, said.text));
        let expected = vec![
            (String::from("user"), String::from("remind me at noon")),
            (String::from("user"), String::from("and lunch at one")),
        ];
        assert_eq!(words.collect::<Vec<_>>(), expected);
        let other = transport.session_messages("beta").await;
        assert_eq!(other, Ok(held.chats[0].messages.clone()));
    })
}

pub(super) fn a_turn_ends_at_its_first_terminal_event(
    subject: &dyn TransportSubject,
) -> Pending<'_> {
    Box::pin(async move {
        let after = TurnEvent::Complete {
            turn_id: String::from("turn-2"),
        };
        let reply = vec![delta("partial"), overloaded(), delta("late"), after];
        let transport = subject.serving(&replying(reply));
        let expected = vec![Ok(delta("partial")), Ok(overloaded())];
        assert_eq!(turn(transport.as_ref(), "beta", "hi").await, expected);
    })
}

pub(super) fn a_reply_without_a_completion_fails_the_turn(
    subject: &dyn TransportSubject,
) -> Pending<'_> {
    Box::pin(async move {
        let transport = subject.serving(&replying(vec![delta("hi")]));
        let mut items = turn(transport.as_ref(), "beta", "hi").await;
        let last = items.pop().and_then(Result::err);
        let malformed = kind(Some(TransportError::Protocol(String::new())));
        assert_eq!(kind(last), malformed);
        assert_eq!(items, vec![Ok(delta("hi"))]);
    })
}

pub(super) fn a_refusing_brain_fails_the_turn_with_its_status(
    subject: &dyn TransportSubject,
) -> Pending<'_> {
    Box::pin(async move {
        let transport = subject.refusing();
        let expected = vec![Err(refused())];
        assert_eq!(turn(transport.as_ref(), "beta", "hi").await, expected);
    })
}

pub(super) fn an_unreachable_brain_fails_the_turn_as_a_connection(
    subject: &dyn TransportSubject,
) -> Pending<'_> {
    Box::pin(async move {
        let transport = subject.unreachable();
        let items = turn(transport.as_ref(), "beta", "hi").await;
        let kinds = items.into_iter().map(|item| kind(item.err()));
        let lost = kind(Some(TransportError::Connection(String::new())));
        assert_eq!(kinds.collect::<Vec<_>>(), vec![lost]);
    })
}
