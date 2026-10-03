use body_core::os::{MAX_TEXT_CHARS, UNTRUSTED_ATTRIBUTION, escape_xml};
use body_core::{Notification, NotifyError};

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
fn a_tainted_notification_includes_the_body_authored_attribution() {
    let notification = Notification::new("Reminder", "click https://evil.example", "r2", true);
    assert!(notification.tainted());
    assert_eq!(notification.attribution(), Some(UNTRUSTED_ATTRIBUTION));
    assert!(!UNTRUSTED_ATTRIBUTION.contains("evil"));
}

#[test]
fn control_characters_become_spaces_in_both_lines() {
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
    assert_eq!(escape_xml("café ☕"), "café ☕");
    assert_eq!(escape_xml(""), "");
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
