//! `FakeTransport`, the one stand-in `BrainTransport` the body's tests use.

use std::cmp::Reverse;
use std::future::poll_fn;
use std::sync::{Mutex, MutexGuard, PoisonError};

use async_stream::stream;

use body_core::{
    AttachedImage, BrainTransport, ConfirmDecision, DueReminder, RpcHealth, SessionMessage,
    SessionSummary, TransportError, TurnEvent,
};
use futures_core::Stream;

use crate::transport::Held;

/// A brain in memory: it answers from what it holds and applies each write to it, or fails every
/// call with one error.
pub struct FakeTransport {
    held: Mutex<Held>,
    failure: Option<TransportError>,
}

impl FakeTransport {
    #[must_use]
    pub fn holding(held: &Held) -> Self {
        Self {
            held: Mutex::new(held.clone()),
            failure: None,
        }
    }

    /// A brain that holds nothing and fails every call, a turn included, with `error`.
    #[must_use]
    pub fn failing(error: TransportError) -> Self {
        let nothing = Held {
            health: RpcHealth {
                ready: false,
                detail: String::new(),
                notes: Vec::new(),
            },
            chats: Vec::new(),
            reminders: Vec::new(),
            preferences: Vec::new(),
            reply: Vec::new(),
        };
        Self {
            failure: Some(error),
            ..Self::holding(&nothing)
        }
    }

    /// The held state, or the failure every call answers with.
    fn held(&self) -> Result<MutexGuard<'_, Held>, TransportError> {
        match &self.failure {
            None => Ok(self.held.lock().unwrap_or_else(PoisonError::into_inner)),
            Some(error) => Err(error.clone()),
        }
    }

    /// Appends the user's words to the asked chat, then the held reply up to its first terminal
    /// event, or a `Protocol` error when the reply has none.
    fn turn(&self, session_id: &str, text: &str) -> Vec<Result<TurnEvent, TransportError>> {
        let mut held = match self.held() {
            Ok(held) => held,
            Err(error) => return vec![Err(error)],
        };
        for chat in &mut held.chats {
            if chat.summary.session_id == session_id {
                chat.messages.push(SessionMessage {
                    role: String::from("user"),
                    text: String::from(text),
                    turn_id: String::new(),
                    at_unix_ms: 0,
                });
            }
        }
        let mut events = Vec::new();
        for event in held.reply.iter().cloned() {
            let terminal = matches!(event, TurnEvent::Complete { .. } | TurnEvent::Failed { .. });
            events.push(Ok(event));
            if terminal {
                return events;
            }
        }
        events.push(Err(TransportError::Protocol(String::from(
            "the reply ended before the turn completed",
        ))));
        events
    }
}

/// What the brain streams after asking `confirm_id`: the tool's outcome for a decision naming
/// it, and an unanswered ask's resolution for anything else.
fn answer(decision: Option<ConfirmDecision>, confirm_id: String, tool_name: String) -> TurnEvent {
    let named = decision.filter(|found| found.confirm_id == confirm_id);
    match named {
        Some(found) => TurnEvent::ToolOutcome {
            tool_name,
            ok: found.approved,
        },
        None => TurnEvent::ConfirmResolved {
            confirm_id,
            outcome: String::from("timeout"),
        },
    }
}

impl BrainTransport for FakeTransport {
    async fn health(&self) -> Result<RpcHealth, TransportError> {
        Ok(self.held()?.health.clone())
    }

    fn converse(
        &self,
        session_id: &str,
        text: &str,
        _images: Vec<AttachedImage>,
        decisions: impl Stream<Item = ConfirmDecision> + Send + 'static,
    ) -> impl Stream<Item = Result<TurnEvent, TransportError>> + Send {
        let planned = self.turn(session_id, text);
        let mut decisions = Box::pin(decisions);
        stream! {
            for item in planned {
                let asked = match &item {
                    Ok(TurnEvent::ConfirmRequest { confirm_id, tool_name, .. }) => {
                        Some((confirm_id.clone(), tool_name.clone()))
                    }
                    _ => None,
                };
                yield item;
                if let Some((confirm_id, tool_name)) = asked {
                    let decision = poll_fn(|cx| decisions.as_mut().poll_next(cx)).await;
                    yield Ok(answer(decision, confirm_id, tool_name));
                }
            }
        }
    }

    async fn list_sessions(&self, limit: i32) -> Result<Vec<SessionSummary>, TransportError> {
        let held = self.held()?;
        let limit = usize::try_from(limit).unwrap_or(0);
        let rows = held.chats.iter().take(limit);
        Ok(rows.map(|chat| chat.summary.clone()).collect())
    }

    async fn session_messages(
        &self,
        session_id: &str,
    ) -> Result<Vec<SessionMessage>, TransportError> {
        let held = self.held()?;
        let mut asked = held
            .chats
            .iter()
            .filter(|chat| chat.summary.session_id == session_id);
        Ok(asked
            .next()
            .map(|chat| chat.messages.clone())
            .unwrap_or_default())
    }

    async fn list_due_reminders(&self) -> Result<Vec<DueReminder>, TransportError> {
        Ok(self.held()?.reminders.clone())
    }

    async fn ack_reminder(
        &self,
        reminder_id: &str,
        fired_at_unix_ms: i64,
    ) -> Result<bool, TransportError> {
        let mut held = self.held()?;
        let before = held.reminders.len();
        held.reminders.retain(|due| {
            due.reminder_id != reminder_id || due.fired_at_unix_ms != fired_at_unix_ms
        });
        Ok(held.reminders.len() < before)
    }

    async fn rename_session(&self, session_id: &str, title: &str) -> Result<(), TransportError> {
        let mut held = self.held()?;
        for chat in &mut held.chats {
            if chat.summary.session_id == session_id {
                chat.summary.title = String::from(title);
            }
        }
        Ok(())
    }

    async fn delete_session(&self, session_id: &str) -> Result<(), TransportError> {
        let mut held = self.held()?;
        held.chats
            .retain(|chat| chat.summary.session_id != session_id);
        Ok(())
    }

    async fn set_session_hoisted(
        &self,
        session_id: &str,
        hoisted: bool,
    ) -> Result<(), TransportError> {
        let mut held = self.held()?;
        for chat in &mut held.chats {
            if chat.summary.session_id == session_id {
                chat.summary.hoisted = hoisted;
            }
        }
        held.chats.sort_by_key(|chat| {
            (
                !chat.summary.hoisted,
                Reverse(chat.summary.last_activity_unix_ms),
            )
        });
        Ok(())
    }

    async fn get_preferences(&self) -> Result<Vec<(String, String)>, TransportError> {
        Ok(self.held()?.preferences.clone())
    }

    async fn set_preference(&self, key: &str, value: &str) -> Result<(), TransportError> {
        let mut held = self.held()?;
        held.preferences.retain(|(held_key, _)| held_key != key);
        if !value.is_empty() {
            held.preferences
                .push((String::from(key), String::from(value)));
            held.preferences.sort();
        }
        Ok(())
    }
}
