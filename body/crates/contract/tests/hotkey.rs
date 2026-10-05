use body_contract::FakeHotkey;
use body_contract::hotkey::{HotkeyRig, HotkeySubject, run};
use body_core::{Hotkey, HotkeyChord, HotkeyError};

struct FakeRig(FakeHotkey);

impl HotkeyRig for FakeRig {
    fn hotkey(&self) -> &dyn Hotkey {
        &self.0
    }

    fn press(&self, chord: &HotkeyChord) {
        self.0.press(chord);
    }

    fn hold(&self, chord: &HotkeyChord) {
        self.0.press(chord);
    }

    fn finish(self: Box<Self>) {}
}

struct Fake;

impl HotkeySubject for Fake {
    fn listening(&self) -> Box<dyn HotkeyRig> {
        Box::new(FakeRig(FakeHotkey::default()))
    }

    fn taken(&self) -> Box<dyn HotkeyRig> {
        let taken = HotkeyError::Registration(String::from("already registered"));
        Box::new(FakeRig(FakeHotkey::failing(taken)))
    }

    fn broken(&self) -> Box<dyn HotkeyRig> {
        let broken = HotkeyError::Registration(String::from("no hotkey manager"));
        Box::new(FakeRig(FakeHotkey::failing(broken)))
    }
}

#[test]
fn the_fake_meets_every_hotkey_check() {
    run(&Fake);
}
