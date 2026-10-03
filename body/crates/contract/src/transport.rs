//! The `BrainTransport` check list for the read calls, run through a dyn-compatible view.

use std::future::Future;
use std::mem::{Discriminant, discriminant};
use std::pin::Pin;

use body_core::{BrainTransport, RpcHealth, SessionMessage, SessionSummary, TransportError};

/// A call's answer as a boxed future, which lets [`Reads`] be a trait object.
pub type Reply<'a, T> = Pin<Box<dyn Future<Output = Result<T, TransportError>> + Send + 'a>>;

/// One check's run, which the driver awaits.
pub type Pending<'a> = Pin<Box<dyn Future<Output = ()> + 'a>>;

/// The read calls of `BrainTransport` with boxed answers, which every transport has.
pub trait Reads: Send + Sync {
    fn health(&self) -> Reply<'_, RpcHealth>;

    fn list_sessions(&self, limit: i32) -> Reply<'_, Vec<SessionSummary>>;

    fn session_messages<'a>(&'a self, session_id: &'a str) -> Reply<'a, Vec<SessionMessage>>;
}

impl<T: BrainTransport> Reads for T {
    fn health(&self) -> Reply<'_, RpcHealth> {
        Box::pin(BrainTransport::health(self))
    }

    fn list_sessions(&self, limit: i32) -> Reply<'_, Vec<SessionSummary>> {
        Box::pin(BrainTransport::list_sessions(self, limit))
    }

    fn session_messages<'a>(&'a self, session_id: &'a str) -> Reply<'a, Vec<SessionMessage>> {
        Box::pin(BrainTransport::session_messages(self, session_id))
    }
}

/// One chat a brain holds: its row in the chat list and its stored history in append order.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Chat {
    pub summary: SessionSummary,
    pub messages: Vec<SessionMessage>,
}

/// What a serving brain holds: its health and its chats, most recently active first.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Held {
    pub health: RpcHealth,
    pub chats: Vec<Chat>,
}

/// Builds the transport under test in each condition a check needs.
pub trait TransportSubject {
    /// A transport whose brain holds `held` and answers every read from it.
    fn serving(&self, held: &Held) -> Box<dyn Reads>;

    /// A transport whose brain answers every read with the status `Unavailable`, `store down`.
    fn refusing(&self) -> Box<dyn Reads>;

    /// A transport with no brain to reach.
    fn unreachable(&self) -> Box<dyn Reads>;
}

/// One check and its name, run against a subject.
pub type TransportCheck = (&'static str, fn(&dyn TransportSubject) -> Pending<'_>);

/// Every check a transport's read calls owe, in the order a driver runs them.
pub const TRANSPORT_CHECKS: [TransportCheck; 6] = named![fn(&dyn TransportSubject) -> Pending<'_>;
    health_is_what_the_brain_holds,
    a_listing_names_every_chat_newest_first,
    a_listing_stops_at_its_limit,
    a_history_is_the_asked_chat_s_in_order,
    a_refusing_brain_fails_every_read_with_its_status,
    an_unreachable_brain_fails_every_read_as_a_connection,
];

/// Runs every check against `subject`, naming each on stderr first so a failure shows which.
pub async fn run(subject: &dyn TransportSubject) {
    for (name, check) in TRANSPORT_CHECKS {
        eprintln!("transport check: {name}");
        check(subject).await;
    }
}

fn summary(session_id: &str, title: &str, at_unix_ms: i64, hoisted: bool) -> SessionSummary {
    SessionSummary {
        session_id: String::from(session_id),
        title: String::from(title),
        preview: format!("the last words of {title}"),
        last_activity_unix_ms: at_unix_ms,
        hoisted,
    }
}

fn message(role: &str, text: &str, turn_id: &str, at_unix_ms: i64) -> SessionMessage {
    SessionMessage {
        role: String::from(role),
        text: String::from(text),
        turn_id: String::from(turn_id),
        at_unix_ms,
    }
}

/// A ready brain holding two chats, the newer one hoisted and two turns long.
fn two_chats() -> Held {
    Held {
        health: RpcHealth {
            ready: true,
            detail: String::from("cortex up; memory up"),
            notes: vec![String::from("cortex up"), String::from("memory up")],
        },
        chats: vec![
            Chat {
                summary: summary("beta", "about cats", 2000, true),
                messages: vec![
                    message("user", "tell me about cats", "t1", 1500),
                    message("assistant", "they sleep a lot", "t1", 1600),
                    message("user", "and dogs?", "t2", 2000),
                ],
            },
            Chat {
                summary: summary("alpha", "a reminder", 1000, false),
                messages: vec![message("user", "remind me at noon", "t0", 1000)],
            },
        ],
    }
}

/// The error a refusing brain's status becomes, code and message both.
fn refused() -> TransportError {
    TransportError::Rpc {
        code: String::from("Unavailable"),
        message: String::from("store down"),
    }
}

/// Which error a call failed with, without its text, which each transport writes its own way.
fn kind(error: Option<TransportError>) -> Option<Discriminant<TransportError>> {
    error.map(|found| discriminant(&found))
}

fn health_is_what_the_brain_holds(subject: &dyn TransportSubject) -> Pending<'_> {
    let starting = Held {
        health: RpcHealth {
            ready: false,
            detail: String::from("loading the cortex"),
            notes: Vec::new(),
        },
        chats: Vec::new(),
    };
    Box::pin(async move {
        for held in [two_chats(), starting] {
            let transport = subject.serving(&held);
            assert_eq!(transport.health().await, Ok(held.health));
        }
    })
}

fn a_listing_names_every_chat_newest_first(subject: &dyn TransportSubject) -> Pending<'_> {
    Box::pin(async move {
        let held = two_chats();
        let transport = subject.serving(&held);
        let rows = held.chats.into_iter().map(|chat| chat.summary).collect();
        assert_eq!(transport.list_sessions(10).await, Ok(rows));
    })
}

fn a_listing_stops_at_its_limit(subject: &dyn TransportSubject) -> Pending<'_> {
    Box::pin(async move {
        let held = two_chats();
        let transport = subject.serving(&held);
        let newest = held.chats[0].summary.clone();
        assert_eq!(transport.list_sessions(1).await, Ok(vec![newest]));
    })
}

fn a_history_is_the_asked_chat_s_in_order(subject: &dyn TransportSubject) -> Pending<'_> {
    Box::pin(async move {
        let held = two_chats();
        let transport = subject.serving(&held);
        for chat in held.chats {
            let found = transport.session_messages(&chat.summary.session_id).await;
            assert_eq!(found, Ok(chat.messages));
        }
    })
}

fn a_refusing_brain_fails_every_read_with_its_status(
    subject: &dyn TransportSubject,
) -> Pending<'_> {
    Box::pin(async move {
        let transport = subject.refusing();
        assert_eq!(transport.health().await.err(), Some(refused()));
        assert_eq!(transport.list_sessions(10).await.err(), Some(refused()));
        assert_eq!(
            transport.session_messages("beta").await.err(),
            Some(refused())
        );
    })
}

fn an_unreachable_brain_fails_every_read_as_a_connection(
    subject: &dyn TransportSubject,
) -> Pending<'_> {
    Box::pin(async move {
        let transport = subject.unreachable();
        let lost = kind(Some(TransportError::Connection(String::new())));
        assert_eq!(kind(transport.health().await.err()), lost);
        assert_eq!(kind(transport.list_sessions(10).await.err()), lost);
        assert_eq!(kind(transport.session_messages("beta").await.err()), lost);
    })
}
