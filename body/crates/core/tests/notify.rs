//! Behavioral tests for `body_core::os::notify`: the inert-text rule `Notification` applies
//! at construction (control characters, the length bound, what it deliberately leaves alone),
//! the taint attribution, the XML escaper the toast backend renders through, the
//! `NotifyError` messages, and a contract-style check that `Notify` works as a generic bound
//! through a fake (shown, declined, and failed all reaching the caller distinctly).

use std::sync::{Mutex, PoisonError};

use body_core::os::{MAX_TEXT_CHARS, UNTRUSTED_ATTRIBUTION, escape_xml};
use body_core::{Notification, Notify, NotifyError};

/// A fake `Notify` backend: records what it was asked to show (the port is `Send + Sync`, so
/// the interior mutability is a `Mutex`) and answers a scripted verdict, or fails.
struct FakeNotify {
    shown: bool,
    fail: Option<NotifyError>,
    seen: Mutex<Vec<Notification>>,
}

impl FakeNotify {
    fn answering(shown: bool) -> Self {
        Self {
            shown,
            fail: None,
            seen: Mutex::new(Vec::new()),
        }
    }

    fn failing(error: NotifyError) -> Self {
        Self {
            shown: true,
            fail: Some(error),
            seen: Mutex::new(Vec::new()),
        }
    }

    fn seen(&self) -> Vec<Notification> {
        self.seen
            .lock()
            .unwrap_or_else(PoisonError::into_inner)
            .clone()
    }
}

impl Notify for FakeNotify {
    fn show(&self, notification: &Notification) -> Result<bool, NotifyError> {
        if let Some(error) = &self.fail {
            return Err(error.clone());
        }
        self.seen
            .lock()
            .unwrap_or_else(PoisonError::into_inner)
            .push(notification.clone());
        Ok(self.shown)
    }
}

/// Shows through a generic bound, the way the `BodyService` server does.
fn show_via<N: Notify>(backend: &N, notification: &Notification) -> Result<bool, NotifyError> {
    backend.show(notification)
}

#[test]
fn a_notification_keeps_its_wire_values() {
    let notification = Notification::new("Reminder", "stretch", "r1", false);
    assert_eq!(notification.title(), "Reminder");
    assert_eq!(notification.body(), "stretch");
    assert_eq!(notification.reminder_id(), "r1");
    assert!(!notification.tainted());
    assert_eq!(notification.attribution(), None);
}

#[test]
fn a_tainted_notification_carries_the_body_authored_attribution() {
    let notification = Notification::new("Reminder", "click https://evil.example", "r2", true);
    assert!(notification.tainted());
    assert_eq!(notification.attribution(), Some(UNTRUSTED_ATTRIBUTION));
    // The badge is fixed text, never built from the reminder it describes.
    assert!(!UNTRUSTED_ATTRIBUTION.contains("evil"));
}

#[test]
fn control_characters_become_spaces_in_both_lines() {
    // A newline, a tab, a NUL, and a DEL: none is expressible in an XML document, so a
    // backend templating one would produce an unparseable payload and show nothing.
    let notification = Notification::new("a\nb", "c\td\u{0}e\u{7f}f", "r3", false);
    assert_eq!(notification.title(), "a b");
    assert_eq!(notification.body(), "c d e f");
}

#[test]
fn ordinary_punctuation_and_non_ascii_text_survive_untouched() {
    let notification =
        Notification::new("Rappel", "acheter du café & du pain <maison>", "r4", false);
    assert_eq!(notification.title(), "Rappel");
    assert_eq!(notification.body(), "acheter du café & du pain <maison>");
}

#[test]
fn text_at_the_bound_is_kept_whole_and_longer_text_is_truncated() {
    let exact = "é".repeat(MAX_TEXT_CHARS);
    assert_eq!(Notification::new("t", &exact, "r5", false).body(), exact);

    let long = "é".repeat(MAX_TEXT_CHARS + 1);
    let truncated = Notification::new(&long, "b", "r6", false);
    assert_eq!(truncated.title().chars().count(), MAX_TEXT_CHARS + 1);
    assert!(truncated.title().starts_with(&exact));
    assert!(truncated.title().ends_with('…'));
}

#[test]
fn escape_xml_neutralizes_the_five_predefined_entities_only() {
    assert_eq!(
        escape_xml(r#"<toast launch="x" tag='y'>tea & cake</toast>"#),
        "&lt;toast launch=&quot;x&quot; tag=&apos;y&apos;&gt;tea &amp; cake&lt;/toast&gt;",
    );
    // Everything else passes through byte for byte, including non-ASCII.
    assert_eq!(escape_xml("café ☕"), "café ☕");
    assert_eq!(escape_xml(""), "");
}

#[test]
fn notify_backend_reports_a_shown_notification() {
    let backend = FakeNotify::answering(true);
    let notification = Notification::new("Reminder", "stretch", "r7", true);
    assert!(show_via(&backend, &notification).unwrap());
    assert_eq!(backend.seen(), vec![notification]);
}

#[test]
fn a_declined_notification_is_an_answer_not_an_error() {
    let backend = FakeNotify::answering(false);
    let notification = Notification::new("Reminder", "stretch", "r8", false);
    assert!(!show_via(&backend, &notification).unwrap());
    // It still reached the OS, which is what separates this from a failure.
    assert_eq!(backend.seen().len(), 1);
}

#[test]
fn notify_backend_surfaces_its_error_without_recording_the_call() {
    let backend = FakeNotify::failing(NotifyError::Unavailable(String::from("no notifier")));
    let error = show_via(&backend, &Notification::new("t", "b", "r9", false)).unwrap_err();
    assert_eq!(error, NotifyError::Unavailable(String::from("no notifier")));
    assert!(backend.seen().is_empty());
}

#[test]
fn notify_error_messages_and_debug() {
    assert_eq!(
        NotifyError::Unavailable(String::from("no notifier")).to_string(),
        "no notification service is available: no notifier",
    );
    assert_eq!(
        NotifyError::Backend(String::from("HRESULT 0x1")).to_string(),
        "the notification backend failed: HRESULT 0x1",
    );
    let error = NotifyError::Backend(String::from("x"));
    assert!(format!("{error:?}").contains("Backend"));
    assert_ne!(error, NotifyError::Unavailable(String::from("x")));
}

#[test]
fn a_notification_is_clone_eq_and_debug() {
    let notification = Notification::new("Reminder", "stretch", "r10", false);
    assert_eq!(notification.clone(), notification);
    assert_ne!(
        notification,
        Notification::new("Reminder", "stretch", "r10", true),
    );
    assert!(format!("{notification:?}").contains("Notification"));
}
