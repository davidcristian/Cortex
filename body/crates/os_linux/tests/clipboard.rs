#![cfg(target_os = "linux")]

use std::sync::{Arc, Mutex, PoisonError};

use body_contract::clipboard::{ClipboardSubject, Offer, run};
use body_core::{ClipboardError, ClipboardPicture, MAX_PASTED_BYTES};
use os_linux::{LinuxClipboardPicture, SelectionError, SelectionRead};

/// A stand-in selection owner that offers a fixed list, or fails every request, and records each
/// type and limit it was asked for. It is silent on the requests `silent` numbers from 1, and
/// with `any` set answers every type with its first offer, as `xclip` does.
struct Owner {
    offers: Result<Vec<Offer>, SelectionError>,
    asked: Arc<Mutex<Vec<(String, usize)>>>,
    silent: &'static [usize],
    any: bool,
}

impl Owner {
    fn new(offers: Result<Vec<Offer>, SelectionError>) -> Self {
        Self {
            offers,
            asked: Arc::default(),
            silent: &[],
            any: false,
        }
    }

    fn asked(&self) -> Arc<Mutex<Vec<(String, usize)>>> {
        Arc::clone(&self.asked)
    }
}

fn asked(record: &Mutex<Vec<(String, usize)>>) -> Vec<(String, usize)> {
    record
        .lock()
        .unwrap_or_else(PoisonError::into_inner)
        .clone()
}

impl Owner {
    /// Records one request, then answers it as silent or with the offers.
    fn answer(&self, target: &str, limit: usize) -> Result<&[Offer], SelectionError> {
        let mut asked = self.asked.lock().unwrap_or_else(PoisonError::into_inner);
        asked.push((String::from(target), limit));
        if self.silent.contains(&asked.len()) {
            return Err(SelectionError::Silent);
        }
        self.offers.as_deref().map_err(Clone::clone)
    }
}

impl SelectionRead for Owner {
    fn offered(&self) -> Result<Vec<String>, SelectionError> {
        let offers = self.answer("TARGETS", 0)?;
        Ok(offers
            .iter()
            .map(|(offered, _)| String::from(*offered))
            .collect())
    }

    fn convert(&self, target: &str, limit: usize) -> Result<Option<Vec<u8>>, SelectionError> {
        let offers = self.answer(target, limit)?;
        let found = offers
            .iter()
            .find(|(offered, _)| self.any || *offered == target);
        let Some((_, data)) = found else {
            return Ok(None);
        };
        if data.len() > limit {
            return Err(SelectionError::Over);
        }
        Ok(Some(data.clone()))
    }
}

struct Linux;

impl ClipboardSubject for Linux {
    fn offering(&self, offers: Vec<Offer>) -> Box<dyn ClipboardPicture> {
        Box::new(LinuxClipboardPicture::new(Owner::new(Ok(offers))))
    }

    fn broken(&self) -> Box<dyn ClipboardPicture> {
        let failed = SelectionError::Failed(String::from("no display"));
        Box::new(LinuxClipboardPicture::new(Owner::new(Err(failed))))
    }
}

#[test]
fn the_linux_clipboard_meets_every_clipboard_check() {
    run(&Linux);
}

#[test]
fn only_the_listed_picture_types_are_asked_for_with_the_byte_limit() {
    let owner = Owner::new(Ok(vec![("image/gif", vec![1]), ("image/webp", vec![3])]));
    let record = owner.asked();

    let read = LinuxClipboardPicture::new(owner).picture();

    assert!(matches!(read, Ok(Some(_))), "{read:?}");
    let limit = MAX_PASTED_BYTES;
    assert_eq!(
        asked(&record),
        [
            (String::from("TARGETS"), 0),
            (String::from("image/webp"), limit)
        ]
    );
}

#[test]
fn an_owner_that_answers_every_type_is_asked_only_for_what_it_lists() {
    let mut owner = Owner::new(Ok(vec![("UTF8_STRING", b"plain words".to_vec())]));
    owner.any = true;
    let record = owner.asked();

    let read = LinuxClipboardPicture::new(owner).picture();

    assert_eq!(read, Ok(None));
    assert_eq!(asked(&record), [(String::from("TARGETS"), 0)]);
}

#[test]
fn a_list_the_owner_was_silent_on_is_asked_for_once_more() {
    let mut owner = Owner::new(Ok(vec![("image/jpeg", vec![2])]));
    owner.silent = &[1];
    let record = owner.asked();

    let read = LinuxClipboardPicture::new(owner).picture();

    let found = read.map(|found| found.map(|found| found.mime_type));
    assert_eq!(found, Ok(Some("image/jpeg")));
    let types: Vec<String> = asked(&record)
        .into_iter()
        .map(|(target, _)| target)
        .collect();
    assert_eq!(types, ["TARGETS", "TARGETS", "image/jpeg"]);
}

#[test]
fn a_failed_conversion_stops_the_read_with_its_reason() {
    let failed = SelectionError::Failed(String::from("BadWindow"));
    let owner = Owner::new(Err(failed));
    let record = owner.asked();

    let read = LinuxClipboardPicture::new(owner).picture();

    assert_eq!(read, Err(ClipboardError::Failed(String::from("BadWindow"))));
    assert_eq!(asked(&record).len(), 1);
}

#[test]
fn a_type_the_owner_was_silent_on_is_asked_for_once_more() {
    let mut owner = Owner::new(Ok(vec![("image/png", vec![1])]));
    owner.silent = &[2];
    let record = owner.asked();

    let read = LinuxClipboardPicture::new(owner).picture();

    let found = read.map(|found| found.map(|found| (found.mime_type, found.data)));
    assert_eq!(found, Ok(Some(("image/png", vec![1]))));
    let types: Vec<String> = asked(&record)
        .into_iter()
        .map(|(target, _)| target)
        .collect();
    assert_eq!(types, ["TARGETS", "image/png", "image/png"]);
}

#[test]
fn an_owner_silent_twice_fails_the_read() {
    let mut owner = Owner::new(Ok(vec![("image/png", vec![1])]));
    owner.silent = &[2, 3];
    let record = owner.asked();

    let read = LinuxClipboardPicture::new(owner).picture();

    let silent = String::from("the clipboard's owner did not answer");
    assert_eq!(read, Err(ClipboardError::Failed(silent)));
    assert_eq!(asked(&record).len(), 3);
}
