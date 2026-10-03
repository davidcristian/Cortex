//! The `Notify` check list: what every notification backend owes, read through the port alone.

use std::mem::{Discriminant, discriminant};

use body_core::{Notification, Notify, NotifyError};

/// Builds the implementation under test in each condition a check needs.
pub trait NotifySubject {
    /// An implementation whose notification service shows every notification.
    fn showing(&self) -> Box<dyn Notify>;

    /// An implementation whose service declines every notification, or `None` for a backend
    /// whose service has no way to decline one.
    fn declining(&self) -> Option<Box<dyn Notify>>;

    /// An implementation with no notification service to send to.
    fn without_service(&self) -> Box<dyn Notify>;

    /// An implementation whose backend fails every call for any other reason.
    fn broken(&self) -> Box<dyn Notify>;
}

/// One check and its name, run against a subject.
pub type NotifyCheck = (&'static str, fn(&dyn NotifySubject));

/// Every check a notification backend owes, in the order a driver runs them.
pub const NOTIFY_CHECKS: [NotifyCheck; 5] = named![fn(&dyn NotifySubject);
    a_shown_notification_answers_true,
    every_call_is_answered_on_its_own,
    a_declined_notification_answers_false,
    no_service_fails_as_unavailable,
    a_broken_backend_fails_as_a_backend_error,
];

/// Runs every check against `subject`, naming each on stderr first so a failure shows which.
pub fn run(subject: &dyn NotifySubject) {
    for (name, check) in NOTIFY_CHECKS {
        eprintln!("notify check: {name}");
        check(subject);
    }
}

/// Reminders that differ in every way the port lets one differ: taint, markup and length.
fn reminders() -> [Notification; 3] {
    [
        Notification::new("Reminder", "stretch", "r1", false),
        Notification::new("<b>Tea</b>", "milk & <i>sugar</i>", "r2", true),
        Notification::new("", &"é".repeat(400), "r3", true),
    ]
}

/// Which error a call failed with, without its text, which each backend writes its own way.
fn kind(result: Result<bool, NotifyError>) -> Result<bool, Discriminant<NotifyError>> {
    result.map_err(|error| discriminant(&error))
}

fn a_shown_notification_answers_true(subject: &dyn NotifySubject) {
    for reminder in reminders() {
        assert_eq!(subject.showing().show(&reminder), Ok(true));
    }
}

fn every_call_is_answered_on_its_own(subject: &dyn NotifySubject) {
    let notify = subject.showing();
    for reminder in reminders() {
        assert_eq!(notify.show(&reminder), Ok(true));
    }
}

fn a_declined_notification_answers_false(subject: &dyn NotifySubject) {
    let Some(notify) = subject.declining() else {
        return;
    };
    for reminder in reminders() {
        assert_eq!(notify.show(&reminder), Ok(false));
    }
}

fn no_service_fails_as_unavailable(subject: &dyn NotifySubject) {
    let notify = subject.without_service();
    let refused = kind(Err(NotifyError::Unavailable(String::new())));
    for reminder in reminders() {
        assert_eq!(kind(notify.show(&reminder)), refused);
    }
}

fn a_broken_backend_fails_as_a_backend_error(subject: &dyn NotifySubject) {
    let notify = subject.broken();
    let failed = kind(Err(NotifyError::Backend(String::new())));
    for reminder in reminders() {
        assert_eq!(kind(notify.show(&reminder)), failed);
    }
}
