use body_contract::FakeNotify;
use body_contract::notify::{NotifySubject, run};
use body_core::{Notify, NotifyError};

struct Fake;

impl NotifySubject for Fake {
    fn showing(&self) -> Box<dyn Notify> {
        Box::new(FakeNotify::answering(true))
    }

    fn declining(&self) -> Option<Box<dyn Notify>> {
        Some(Box::new(FakeNotify::answering(false)))
    }

    fn without_service(&self) -> Box<dyn Notify> {
        Box::new(FakeNotify::failing(NotifyError::Unavailable(String::from(
            "no notifier",
        ))))
    }

    fn broken(&self) -> Box<dyn Notify> {
        Box::new(FakeNotify::failing(NotifyError::Backend(String::from(
            "HRESULT 0x1",
        ))))
    }
}

#[test]
fn the_fake_meets_every_notify_check() {
    run(&Fake);
}
