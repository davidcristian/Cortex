use body_contract::FakeClipboard;
use body_contract::clipboard::{ClipboardSubject, Offer, run};
use body_core::{ClipboardError, ClipboardPicture};

struct Fake;

impl ClipboardSubject for Fake {
    fn offering(&self, offers: Vec<Offer>) -> Box<dyn ClipboardPicture> {
        Box::new(FakeClipboard::offering(offers))
    }

    fn broken(&self) -> Box<dyn ClipboardPicture> {
        Box::new(FakeClipboard::failing(ClipboardError::Failed(
            String::from("no display"),
        )))
    }
}

#[test]
fn the_fake_meets_every_clipboard_check() {
    run(&Fake);
}
