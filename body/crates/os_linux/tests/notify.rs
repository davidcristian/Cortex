#![cfg(target_os = "linux")]

use std::sync::{Mutex, PoisonError};

use body_core::os::UNTRUSTED_ATTRIBUTION;
use body_core::{Notification, Notify, NotifyError};
use os_linux::{BusError, BusMessage, LinuxNotify, NotificationBus};

/// A fake bus: answers scripted capabilities or a failure, and records each `Notify` message.
struct FakeBus {
    capabilities: Result<Vec<String>, BusError>,
    notify: Result<u32, BusError>,
    sent: Mutex<Vec<BusMessage>>,
}

impl FakeBus {
    fn with_capabilities(capabilities: &[&str]) -> Self {
        Self {
            capabilities: Ok(capabilities
                .iter()
                .map(|name| String::from(*name))
                .collect()),
            notify: Ok(7),
            sent: Mutex::new(Vec::new()),
        }
    }

    fn sent(&self) -> Vec<BusMessage> {
        self.sent
            .lock()
            .unwrap_or_else(PoisonError::into_inner)
            .clone()
    }
}

impl NotificationBus for &FakeBus {
    fn capabilities(&self) -> Result<Vec<String>, BusError> {
        self.capabilities.clone()
    }

    fn notify(&self, message: &BusMessage) -> Result<u32, BusError> {
        self.sent
            .lock()
            .unwrap_or_else(PoisonError::into_inner)
            .push(message.clone());
        self.notify.clone()
    }
}

fn named(name: Option<&str>, message: &str) -> BusError {
    BusError {
        name: name.map(String::from),
        message: String::from(message),
    }
}

#[test]
fn an_accepted_call_reports_shown_with_the_title_as_summary() {
    let bus = FakeBus::with_capabilities(&["body"]);
    let notify = LinuxNotify::new("Cortex", &bus);

    let shown = notify.show(&Notification::new(
        "Stand up",
        "Walk <b>now</b> & then",
        "r1",
        false,
    ));

    assert_eq!(shown, Ok(true));
    assert_eq!(
        bus.sent(),
        vec![BusMessage {
            app_name: String::from("Cortex"),
            summary: String::from("Stand up"),
            body: String::from("Walk <b>now</b> & then"),
        }]
    );
}

#[test]
fn a_server_that_renders_markup_gets_an_escaped_body() {
    let bus = FakeBus::with_capabilities(&["body", "body-markup"]);
    let notify = LinuxNotify::new("Cortex", &bus);

    notify
        .show(&Notification::new(
            "<i>t</i>",
            "Walk <b>now</b> & then",
            "r1",
            false,
        ))
        .unwrap();

    let sent = bus.sent();
    assert_eq!(sent[0].body, "Walk &lt;b&gt;now&lt;/b&gt; &amp; then");
    assert_eq!(sent[0].summary, "<i>t</i>");
}

#[test]
fn an_untrusted_reminder_ends_with_the_provenance_line_on_its_own_line() {
    let bus = FakeBus::with_capabilities(&[]);
    let notify = LinuxNotify::new("Cortex", &bus);

    notify
        .show(&Notification::new("t", "line one\nline two", "r1", true))
        .unwrap();

    assert_eq!(
        bus.sent()[0].body,
        format!("line one line two\n{UNTRUSTED_ATTRIBUTION}")
    );
}

#[test]
fn the_provenance_line_is_escaped_with_the_body_under_markup() {
    let bus = FakeBus::with_capabilities(&["body-markup"]);
    let notify = LinuxNotify::new("Cortex", &bus);

    notify
        .show(&Notification::new("t", "a<b", "r1", true))
        .unwrap();

    assert_eq!(
        bus.sent()[0].body,
        format!("a&lt;b\n{UNTRUSTED_ATTRIBUTION}")
    );
}

#[test]
fn no_owner_for_the_service_name_is_unavailable() {
    for name in [
        "org.freedesktop.DBus.Error.ServiceUnknown",
        "org.freedesktop.DBus.Error.NameHasNoOwner",
    ] {
        let bus = FakeBus {
            capabilities: Err(named(Some(name), "nobody serves it")),
            ..FakeBus::with_capabilities(&[])
        };

        let result =
            LinuxNotify::new("Cortex", &bus).show(&Notification::new("t", "b", "r", false));

        assert_eq!(
            result,
            Err(NotifyError::Unavailable(String::from("nobody serves it")))
        );
        assert!(bus.sent().is_empty());
    }
}

#[test]
fn any_other_named_failure_is_a_backend_error() {
    let bus = FakeBus {
        notify: Err(named(Some("org.freedesktop.DBus.Error.Failed"), "refused")),
        ..FakeBus::with_capabilities(&[])
    };

    let result = LinuxNotify::new("Cortex", &bus).show(&Notification::new("t", "b", "r", false));

    assert_eq!(result, Err(NotifyError::Backend(String::from("refused"))));
}

#[test]
fn a_failure_with_no_error_name_is_a_backend_error() {
    let bus = FakeBus {
        capabilities: Err(named(None, "connection closed")),
        ..FakeBus::with_capabilities(&[])
    };

    let result = LinuxNotify::new("Cortex", &bus).show(&Notification::new("t", "b", "r", false));

    assert_eq!(
        result,
        Err(NotifyError::Backend(String::from("connection closed")))
    );
}
