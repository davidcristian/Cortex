//! The checks in `TRANSPORT_CHECKS`, and the brain state they start from.

use std::mem::{Discriminant, discriminant};

use body_core::{DueReminder, RpcHealth, SessionMessage, SessionSummary, TransportError};

use super::{Calls, Chat, Held, Pending, TransportSubject};

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

fn reminder(reminder_id: &str, fired_at_unix_ms: i64, tainted: bool) -> DueReminder {
    DueReminder {
        reminder_id: String::from(reminder_id),
        text: format!("{reminder_id} is due"),
        fired_at_unix_ms,
        recurring: !tainted,
        tainted,
        session_id: if tainted {
            String::new()
        } else {
            String::from("beta")
        },
    }
}

fn setting(key: &str, value: &str) -> (String, String) {
    (String::from(key), String::from(value))
}

/// A ready brain holding two chats, the newer one hoisted, two due reminders and two settings.
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
        reminders: vec![reminder("r1", 2000, false), reminder("r2", 3000, true)],
        preferences: vec![
            setting("overlay.mark", "foam"),
            setting("overlay.theme", "midnight"),
        ],
    }
}

/// The chat list a transport returns now, each row as `(session_id, title, hoisted)`.
async fn rows(transport: &dyn Calls) -> Vec<(String, String, bool)> {
    let listed = transport.list_sessions(10).await.unwrap_or_default();
    let row = |found: SessionSummary| (found.session_id, found.title, found.hoisted);
    listed.into_iter().map(row).collect()
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

pub(super) fn health_is_what_the_brain_holds(subject: &dyn TransportSubject) -> Pending<'_> {
    let starting = Held {
        health: RpcHealth {
            ready: false,
            detail: String::from("loading the cortex"),
            notes: Vec::new(),
        },
        ..two_chats()
    };
    Box::pin(async move {
        for held in [two_chats(), starting] {
            let transport = subject.serving(&held);
            assert_eq!(transport.health().await, Ok(held.health));
        }
    })
}

pub(super) fn a_listing_names_every_chat_newest_first(
    subject: &dyn TransportSubject,
) -> Pending<'_> {
    Box::pin(async move {
        let held = two_chats();
        let transport = subject.serving(&held);
        let listed = held.chats.into_iter().map(|chat| chat.summary).collect();
        assert_eq!(transport.list_sessions(10).await, Ok(listed));
    })
}

pub(super) fn a_listing_stops_at_its_limit(subject: &dyn TransportSubject) -> Pending<'_> {
    Box::pin(async move {
        let held = two_chats();
        let transport = subject.serving(&held);
        let newest = held.chats[0].summary.clone();
        assert_eq!(transport.list_sessions(1).await, Ok(vec![newest]));
    })
}

pub(super) fn a_history_is_the_asked_chat_s_in_order(
    subject: &dyn TransportSubject,
) -> Pending<'_> {
    Box::pin(async move {
        let held = two_chats();
        let transport = subject.serving(&held);
        for chat in held.chats {
            let found = transport.session_messages(&chat.summary.session_id).await;
            assert_eq!(found, Ok(chat.messages));
        }
    })
}

pub(super) fn a_rename_shows_in_the_next_listing(subject: &dyn TransportSubject) -> Pending<'_> {
    Box::pin(async move {
        let transport = subject.serving(&two_chats());
        assert_eq!(transport.rename_session("alpha", "groceries").await, Ok(()));
        let expected = vec![
            (String::from("beta"), String::from("about cats"), true),
            (String::from("alpha"), String::from("groceries"), false),
        ];
        assert_eq!(rows(transport.as_ref()).await, expected);
    })
}

pub(super) fn a_delete_drops_the_chat_from_the_listing(
    subject: &dyn TransportSubject,
) -> Pending<'_> {
    Box::pin(async move {
        let transport = subject.serving(&two_chats());
        assert_eq!(transport.delete_session("beta").await, Ok(()));
        let expected = vec![(String::from("alpha"), String::from("a reminder"), false)];
        assert_eq!(rows(transport.as_ref()).await, expected);
    })
}

pub(super) fn a_hoist_moves_the_chat_above_the_rest(subject: &dyn TransportSubject) -> Pending<'_> {
    Box::pin(async move {
        let transport = subject.serving(&two_chats());
        assert_eq!(transport.set_session_hoisted("beta", false).await, Ok(()));
        assert_eq!(transport.set_session_hoisted("alpha", true).await, Ok(()));
        let expected = vec![
            (String::from("alpha"), String::from("a reminder"), true),
            (String::from("beta"), String::from("about cats"), false),
        ];
        assert_eq!(rows(transport.as_ref()).await, expected);
    })
}

pub(super) fn due_reminders_are_what_the_brain_holds(
    subject: &dyn TransportSubject,
) -> Pending<'_> {
    Box::pin(async move {
        let held = two_chats();
        let transport = subject.serving(&held);
        assert_eq!(transport.list_due_reminders().await, Ok(held.reminders));
    })
}

pub(super) fn an_ack_clears_only_the_fire_it_names(subject: &dyn TransportSubject) -> Pending<'_> {
    Box::pin(async move {
        let held = two_chats();
        let transport = subject.serving(&held);
        assert_eq!(transport.ack_reminder("r2", 2999).await, Ok(false));
        assert_eq!(transport.ack_reminder("r1", 2000).await, Ok(true));
        assert_eq!(transport.ack_reminder("r1", 2000).await, Ok(false));
        let left = vec![held.reminders[1].clone()];
        assert_eq!(transport.list_due_reminders().await, Ok(left));
    })
}

pub(super) fn the_settings_are_what_the_brain_holds(subject: &dyn TransportSubject) -> Pending<'_> {
    Box::pin(async move {
        let held = two_chats();
        let transport = subject.serving(&held);
        assert_eq!(transport.get_preferences().await, Ok(held.preferences));
    })
}

pub(super) fn a_written_setting_reads_back(subject: &dyn TransportSubject) -> Pending<'_> {
    Box::pin(async move {
        let transport = subject.serving(&two_chats());
        assert_eq!(
            transport.set_preference("overlay.edge", "lucid").await,
            Ok(())
        );
        assert_eq!(
            transport.set_preference("overlay.theme", "dawn").await,
            Ok(())
        );
        let expected = vec![
            setting("overlay.edge", "lucid"),
            setting("overlay.mark", "foam"),
            setting("overlay.theme", "dawn"),
        ];
        assert_eq!(transport.get_preferences().await, Ok(expected));
    })
}

pub(super) fn an_empty_value_clears_its_setting(subject: &dyn TransportSubject) -> Pending<'_> {
    Box::pin(async move {
        let transport = subject.serving(&two_chats());
        assert_eq!(transport.set_preference("overlay.mark", "").await, Ok(()));
        let left = vec![setting("overlay.theme", "midnight")];
        assert_eq!(transport.get_preferences().await, Ok(left));
    })
}

pub(super) fn a_refusing_brain_fails_every_call_with_its_status(
    subject: &dyn TransportSubject,
) -> Pending<'_> {
    Box::pin(async move {
        let transport = subject.refusing();
        let refused = Some(refused());
        assert_eq!(transport.health().await.err(), refused);
        assert_eq!(transport.list_sessions(10).await.err(), refused);
        assert_eq!(transport.session_messages("beta").await.err(), refused);
        assert_eq!(transport.list_due_reminders().await.err(), refused);
        assert_eq!(transport.ack_reminder("r1", 2000).await.err(), refused);
        assert_eq!(transport.rename_session("beta", "x").await.err(), refused);
        assert_eq!(transport.delete_session("beta").await.err(), refused);
        assert_eq!(
            transport.set_session_hoisted("beta", true).await.err(),
            refused
        );
        assert_eq!(transport.get_preferences().await.err(), refused);
        assert_eq!(transport.set_preference("k", "v").await.err(), refused);
    })
}

pub(super) fn an_unreachable_brain_fails_every_call_as_a_connection(
    subject: &dyn TransportSubject,
) -> Pending<'_> {
    Box::pin(async move {
        let transport = subject.unreachable();
        let lost = kind(Some(TransportError::Connection(String::new())));
        assert_eq!(kind(transport.health().await.err()), lost);
        assert_eq!(kind(transport.list_sessions(10).await.err()), lost);
        assert_eq!(kind(transport.session_messages("beta").await.err()), lost);
        assert_eq!(kind(transport.list_due_reminders().await.err()), lost);
        assert_eq!(kind(transport.ack_reminder("r1", 2000).await.err()), lost);
        assert_eq!(
            kind(transport.rename_session("beta", "x").await.err()),
            lost
        );
        assert_eq!(kind(transport.delete_session("beta").await.err()), lost);
        assert_eq!(
            kind(transport.set_session_hoisted("beta", true).await.err()),
            lost
        );
        assert_eq!(kind(transport.get_preferences().await.err()), lost);
        assert_eq!(kind(transport.set_preference("k", "v").await.err()), lost);
    })
}
