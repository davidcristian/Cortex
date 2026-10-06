//! The `ClipboardPicture` check list: what every clipboard backend owes, read through the port.

use std::mem::discriminant;

use body_core::{ClipboardError, ClipboardPicture, MAX_PASTED_BYTES, PICTURE_TYPES, PastedPicture};

/// One type a clipboard owner offers and the bytes it gives for it.
pub type Offer = (&'static str, Vec<u8>);

/// Builds the implementation under test in each condition a check needs.
pub trait ClipboardSubject {
    /// An implementation whose clipboard owner offers exactly `offers`, in that order.
    fn offering(&self, offers: Vec<Offer>) -> Box<dyn ClipboardPicture>;

    /// An implementation whose clipboard cannot be read at all.
    fn broken(&self) -> Box<dyn ClipboardPicture>;
}

/// One check and its name, run against a subject.
pub type ClipboardCheck = (&'static str, fn(&dyn ClipboardSubject));

/// Every check a clipboard backend owes, in the order a driver runs them.
pub const CLIPBOARD_CHECKS: [ClipboardCheck; 7] = named![fn(&dyn ClipboardSubject);
    each_picture_type_is_read_as_offered,
    the_first_type_in_order_is_read,
    a_clipboard_with_no_picture_type_answers_none,
    an_empty_offer_is_passed_over,
    a_picture_at_the_limit_is_read,
    a_picture_over_the_limit_is_refused,
    a_broken_clipboard_fails,
];

/// Runs every check against `subject`, naming each on stderr first so a failure shows which.
pub fn run(subject: &dyn ClipboardSubject) {
    for (name, check) in CLIPBOARD_CHECKS {
        eprintln!("clipboard check: {name}");
        check(subject);
    }
}

/// A picture offered as `mime_type` with `data`, as a read returns it.
fn picture(mime_type: &'static str, data: &[u8]) -> PastedPicture {
    let data = data.to_vec();
    PastedPicture { data, mime_type }
}

fn each_picture_type_is_read_as_offered(subject: &dyn ClipboardSubject) {
    for (index, mime_type) in PICTURE_TYPES.into_iter().enumerate() {
        let data = vec![0x89, 0x50, u8::try_from(index).unwrap_or(u8::MAX)];
        let clipboard = subject.offering(vec![(mime_type, data.clone())]);
        assert_eq!(clipboard.picture(), Ok(Some(picture(mime_type, &data))));
    }
}

fn the_first_type_in_order_is_read(subject: &dyn ClipboardSubject) {
    let webp_first = vec![("image/webp", vec![3]), ("image/png", vec![1])];
    assert_eq!(
        subject.offering(webp_first).picture(),
        Ok(Some(picture("image/png", &[1])))
    );
    let jpeg_last = vec![
        ("text/plain", vec![9]),
        ("image/webp", vec![3]),
        ("image/jpeg", vec![2]),
    ];
    assert_eq!(
        subject.offering(jpeg_last).picture(),
        Ok(Some(picture("image/jpeg", &[2])))
    );
}

fn a_clipboard_with_no_picture_type_answers_none(subject: &dyn ClipboardSubject) {
    assert_eq!(subject.offering(Vec::new()).picture(), Ok(None));
    let others = vec![("text/plain", b"tea".to_vec()), ("image/gif", vec![0x47])];
    assert_eq!(subject.offering(others).picture(), Ok(None));
}

fn an_empty_offer_is_passed_over(subject: &dyn ClipboardSubject) {
    let offers = vec![("image/png", Vec::new()), ("image/webp", vec![3])];
    assert_eq!(
        subject.offering(offers).picture(),
        Ok(Some(picture("image/webp", &[3])))
    );
    let only_empty = vec![("image/jpeg", Vec::new())];
    assert_eq!(subject.offering(only_empty).picture(), Ok(None));
}

fn a_picture_at_the_limit_is_read(subject: &dyn ClipboardSubject) {
    let full = vec![7; MAX_PASTED_BYTES];
    let read = subject.offering(vec![("image/png", full)]).picture();
    assert_eq!(
        read.map(|found| found.map(|found| found.data.len())),
        Ok(Some(MAX_PASTED_BYTES))
    );
}

fn a_picture_over_the_limit_is_refused(subject: &dyn ClipboardSubject) {
    let over = vec![7; MAX_PASTED_BYTES + 1];
    let offers = vec![("image/png", over), ("image/jpeg", vec![2])];
    assert_eq!(
        subject.offering(offers).picture(),
        Err(ClipboardError::TooLarge)
    );
}

fn a_broken_clipboard_fails(subject: &dyn ClipboardSubject) {
    let failed = discriminant(&ClipboardError::Failed(String::new()));
    let read = subject.broken().picture();
    assert_eq!(read.map_err(|error| discriminant(&error)), Err(failed));
}
