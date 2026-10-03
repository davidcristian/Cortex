//! The `BrainTransport` check list for every call but the turn, run through a dyn-compatible view.

mod checks;

use std::future::Future;
use std::pin::Pin;

use body_core::{
    BrainTransport, DueReminder, RpcHealth, SessionMessage, SessionSummary, TransportError,
};

use checks::{
    a_delete_drops_the_chat_from_the_listing, a_history_is_the_asked_chat_s_in_order,
    a_hoist_moves_the_chat_above_the_rest, a_listing_names_every_chat_newest_first,
    a_listing_stops_at_its_limit, a_refusing_brain_fails_every_call_with_its_status,
    a_rename_shows_in_the_next_listing, a_written_setting_reads_back,
    an_ack_clears_only_the_fire_it_names, an_empty_value_clears_its_setting,
    an_unreachable_brain_fails_every_call_as_a_connection, due_reminders_are_what_the_brain_holds,
    health_is_what_the_brain_holds, the_settings_are_what_the_brain_holds,
};

/// A call's result as a boxed future, which lets [`Calls`] be a trait object.
pub type Reply<'a, T> = Pin<Box<dyn Future<Output = Result<T, TransportError>> + Send + 'a>>;

/// One check's run, which the driver awaits.
pub type Pending<'a> = Pin<Box<dyn Future<Output = ()> + 'a>>;

/// Every `BrainTransport` call but `converse`, each returning a boxed future, for every transport.
pub trait Calls: Send + Sync {
    fn health(&self) -> Reply<'_, RpcHealth>;

    fn list_sessions(&self, limit: i32) -> Reply<'_, Vec<SessionSummary>>;

    fn session_messages<'a>(&'a self, session_id: &'a str) -> Reply<'a, Vec<SessionMessage>>;

    fn list_due_reminders(&self) -> Reply<'_, Vec<DueReminder>>;

    fn ack_reminder<'a>(&'a self, reminder_id: &'a str, fired_at: i64) -> Reply<'a, bool>;

    fn rename_session<'a>(&'a self, session_id: &'a str, title: &'a str) -> Reply<'a, ()>;

    fn delete_session<'a>(&'a self, session_id: &'a str) -> Reply<'a, ()>;

    fn set_session_hoisted<'a>(&'a self, session_id: &'a str, hoisted: bool) -> Reply<'a, ()>;

    fn get_preferences(&self) -> Reply<'_, Vec<(String, String)>>;

    fn set_preference<'a>(&'a self, key: &'a str, value: &'a str) -> Reply<'a, ()>;
}

impl<T: BrainTransport> Calls for T {
    fn health(&self) -> Reply<'_, RpcHealth> {
        Box::pin(BrainTransport::health(self))
    }

    fn list_sessions(&self, limit: i32) -> Reply<'_, Vec<SessionSummary>> {
        Box::pin(BrainTransport::list_sessions(self, limit))
    }

    fn session_messages<'a>(&'a self, session_id: &'a str) -> Reply<'a, Vec<SessionMessage>> {
        Box::pin(BrainTransport::session_messages(self, session_id))
    }

    fn list_due_reminders(&self) -> Reply<'_, Vec<DueReminder>> {
        Box::pin(BrainTransport::list_due_reminders(self))
    }

    fn ack_reminder<'a>(&'a self, reminder_id: &'a str, fired_at: i64) -> Reply<'a, bool> {
        Box::pin(BrainTransport::ack_reminder(self, reminder_id, fired_at))
    }

    fn rename_session<'a>(&'a self, session_id: &'a str, title: &'a str) -> Reply<'a, ()> {
        Box::pin(BrainTransport::rename_session(self, session_id, title))
    }

    fn delete_session<'a>(&'a self, session_id: &'a str) -> Reply<'a, ()> {
        Box::pin(BrainTransport::delete_session(self, session_id))
    }

    fn set_session_hoisted<'a>(&'a self, session_id: &'a str, hoisted: bool) -> Reply<'a, ()> {
        Box::pin(BrainTransport::set_session_hoisted(
            self, session_id, hoisted,
        ))
    }

    fn get_preferences(&self) -> Reply<'_, Vec<(String, String)>> {
        Box::pin(BrainTransport::get_preferences(self))
    }

    fn set_preference<'a>(&'a self, key: &'a str, value: &'a str) -> Reply<'a, ()> {
        Box::pin(BrainTransport::set_preference(self, key, value))
    }
}

/// One chat a brain holds: its row in the chat list and its stored history in append order.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Chat {
    pub summary: SessionSummary,
    pub messages: Vec<SessionMessage>,
}

/// What a serving brain holds: hoisted chats first and then the rest newest first, the due
/// reminders, and the settings sorted by key.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Held {
    pub health: RpcHealth,
    pub chats: Vec<Chat>,
    pub reminders: Vec<DueReminder>,
    pub preferences: Vec<(String, String)>,
}

/// Builds the transport under test in each condition a check needs.
pub trait TransportSubject {
    /// A transport whose brain starts from `held`, reads from it, and applies each write to it.
    fn serving(&self, held: &Held) -> Box<dyn Calls>;

    /// A transport whose brain fails every call with the status `Unavailable`, `store down`.
    fn refusing(&self) -> Box<dyn Calls>;

    /// A transport with no brain to reach.
    fn unreachable(&self) -> Box<dyn Calls>;
}

/// One check and its name, run against a subject.
pub type TransportCheck = (&'static str, fn(&dyn TransportSubject) -> Pending<'_>);

/// Every check a transport's calls owe, in the order a driver runs them.
pub const TRANSPORT_CHECKS: [TransportCheck; 14] = named![fn(&dyn TransportSubject) -> Pending<'_>;
    health_is_what_the_brain_holds,
    a_listing_names_every_chat_newest_first,
    a_listing_stops_at_its_limit,
    a_history_is_the_asked_chat_s_in_order,
    a_rename_shows_in_the_next_listing,
    a_delete_drops_the_chat_from_the_listing,
    a_hoist_moves_the_chat_above_the_rest,
    due_reminders_are_what_the_brain_holds,
    an_ack_clears_only_the_fire_it_names,
    the_settings_are_what_the_brain_holds,
    a_written_setting_reads_back,
    an_empty_value_clears_its_setting,
    a_refusing_brain_fails_every_call_with_its_status,
    an_unreachable_brain_fails_every_call_as_a_connection,
];

/// Runs every check against `subject`, naming each on stderr first so a failure shows which.
pub async fn run(subject: &dyn TransportSubject) {
    for (name, check) in TRANSPORT_CHECKS {
        eprintln!("transport check: {name}");
        check(subject).await;
    }
}
