//! The Linux [`Hotkey`] backend's logic, over passive key grabs on an X server's root window.

use std::sync::{Arc, Mutex, Once, PoisonError};
use std::thread;

use body_core::{Accelerator, Hotkey, HotkeyCallback, HotkeyChord, HotkeyError, Modifier};

/// The core protocol's Shift, Lock and Control bits; Mod1 to Mod5 follow them.
const SHIFT: u16 = 1;
const LOCK: u16 = 1 << 1;
const CONTROL: u16 = 1 << 2;
/// The eight modifiers' bits in a key event's state, without the pointer buttons.
const MODIFIERS: u16 = 0xff;

const NUM_LOCK: u32 = 0xff7f;
const ALT: [u32; 2] = [0xffe9, 0xffea];
const SUPER: [u32; 2] = [0xffeb, 0xffec];

/// The server's keyboard: which keysyms each keycode types, and which keycodes each modifier has.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Keyboard {
    /// The keycode the first group of `keysyms` belongs to.
    pub min_keycode: u8,
    /// How many keysyms each keycode has in `keysyms`.
    pub keysyms_per_keycode: u8,
    /// The keysyms of each keycode from `min_keycode` up, `keysyms_per_keycode` at a time.
    pub keysyms: Vec<u32>,
    /// The keycodes of Shift, Lock, Control and Mod1 to Mod5, an equal count each, 0 for none.
    pub modifiers: Vec<u8>,
}

impl Keyboard {
    /// The lowest keycode that types `keysym` at any level.
    fn keycode(&self, keysym: u32) -> Option<u8> {
        let per = usize::from(self.keysyms_per_keycode).max(1);
        self.keysyms
            .chunks(per)
            .position(|keysyms| keysyms.contains(&keysym))
            .and_then(|index| u8::try_from(index + usize::from(self.min_keycode)).ok())
    }

    /// Whether `keycode` types any of `wanted` at any level.
    fn types(&self, keycode: u8, wanted: &[u32]) -> bool {
        let per = usize::from(self.keysyms_per_keycode);
        keycode
            .checked_sub(self.min_keycode)
            .and_then(|offset| self.keysyms.chunks(per.max(1)).nth(usize::from(offset)))
            .is_some_and(|keysyms| keysyms.iter().any(|keysym| wanted.contains(keysym)))
    }

    /// The bit of the first modifier holding a key that types any of `wanted`.
    fn modifier(&self, wanted: &[u32]) -> Option<u16> {
        let per = (self.modifiers.len() / 8).max(1);
        self.modifiers
            .chunks(per)
            .zip(0..8_u16)
            .find(|(keycodes, _)| keycodes.iter().any(|&keycode| self.types(keycode, wanted)))
            .map(|(_, row)| 1 << row)
    }
}

/// One press or release of a grabbed key, as the server reported it.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct KeyEvent {
    /// The key's keycode.
    pub keycode: u8,
    /// The modifier and button state before the event.
    pub state: u16,
    /// The server time of the event, in milliseconds.
    pub time: u32,
    /// Whether the key went down rather than up.
    pub pressed: bool,
}

/// Why a request to the X server failed, or why none could be made.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct KeyError(pub String);

/// Grabs keys on the root window of one X screen and reports their presses.
pub trait KeyGrab: Send + Sync {
    /// Reads the keyboard and modifier mappings.
    ///
    /// # Errors
    ///
    /// [`KeyError`] when there is no server or a request fails.
    fn keyboard(&self) -> Result<Keyboard, KeyError>;

    /// Grabs `keycode` with exactly the `modifiers` bits held, and waits for the server's answer.
    ///
    /// # Errors
    ///
    /// [`KeyError`] when there is no server or it refuses the grab, as when another client holds it.
    fn grab(&self, keycode: u8, modifiers: u16) -> Result<(), KeyError>;

    /// Blocks until the next press or release of a grabbed key.
    ///
    /// # Errors
    ///
    /// [`KeyError`] when there is no server or the connection fails.
    fn next_key(&self) -> Result<KeyEvent, KeyError>;
}

/// One registered chord: the key, the modifiers it needs and the ones it ignores.
struct Binding {
    keycode: u8,
    modifiers: u16,
    ignored: u16,
    on_activate: HotkeyCallback,
}

/// The Linux global-hotkey backend over any [`KeyGrab`].
pub struct LinuxHotkey {
    keys: Arc<dyn KeyGrab>,
    bindings: Arc<Mutex<Vec<Binding>>>,
    listener: Once,
}

impl LinuxHotkey {
    /// Creates the backend over `keys`; the first registration starts the thread that reads keys.
    #[must_use]
    pub fn new(keys: impl KeyGrab + 'static) -> Self {
        Self {
            keys: Arc::new(keys),
            bindings: Arc::new(Mutex::new(Vec::new())),
            listener: Once::new(),
        }
    }
}

impl Hotkey for LinuxHotkey {
    fn register(
        &self,
        chord: &HotkeyChord,
        on_activate: HotkeyCallback,
    ) -> Result<(), HotkeyError> {
        let keysym = resolve(chord)?;
        let refused = |error: KeyError| HotkeyError::Registration(format!("{chord}: {}", error.0));
        let keyboard = self.keys.keyboard().map_err(refused)?;
        let keycode = keyboard.keycode(keysym).ok_or_else(|| {
            HotkeyError::Registration(format!("no key on this keyboard types {chord}"))
        })?;
        let mut modifiers = 0;
        for modifier in chord.modifiers() {
            modifiers |= bit(*modifier, &keyboard)?;
        }
        let ignored = LOCK | keyboard.modifier(&[NUM_LOCK]).unwrap_or(0);
        for variant in variants(modifiers, ignored) {
            self.keys.grab(keycode, variant).map_err(refused)?;
        }
        let binding = Binding {
            keycode,
            modifiers,
            ignored,
            on_activate,
        };
        lock(&self.bindings).push(binding);
        self.listener.call_once(|| {
            let keys = Arc::clone(&self.keys);
            let bindings = Arc::clone(&self.bindings);
            thread::spawn(move || listen(keys.as_ref(), &bindings));
        });
        Ok(())
    }
}

/// The X keysym a chord's key types, or [`HotkeyError::UnsupportedKey`].
fn resolve(chord: &HotkeyChord) -> Result<u32, HotkeyError> {
    let code = Accelerator::from_chord(chord)?.code;
    keysym(&code).ok_or(HotkeyError::UnsupportedKey(code))
}

/// The X keysym of a `KeyboardEvent.code` name, or `None` for a code with no keysym here.
#[must_use]
pub fn keysym(code: &str) -> Option<u32> {
    let named = match code {
        "Space" => 0x0020,
        "Enter" => 0xff0d,
        "Escape" => 0xff1b,
        "Tab" => 0xff09,
        "Backspace" => 0xff08,
        "ArrowUp" => 0xff52,
        "ArrowDown" => 0xff54,
        "ArrowLeft" => 0xff51,
        "ArrowRight" => 0xff53,
        _ => return printable(code),
    };
    Some(named)
}

/// The keysym of a letter, digit or function key code: `KeyA` is `a`, `Digit1` is `1`, `F1` is F1.
fn printable(code: &str) -> Option<u32> {
    match code.as_bytes() {
        [b'K', b'e', b'y', letter @ b'A'..=b'Z'] => Some(u32::from(letter.to_ascii_lowercase())),
        [b'D', b'i', b'g', b'i', b't', digit @ b'0'..=b'9'] => Some(u32::from(*digit)),
        [b'F', ..] => code[1..]
            .parse::<u32>()
            .ok()
            .filter(|number| (1..=35).contains(number))
            .map(|number| 0xffbd + number),
        _ => None,
    }
}

/// The state bit of one chord modifier on this keyboard.
fn bit(modifier: Modifier, keyboard: &Keyboard) -> Result<u16, HotkeyError> {
    let (bit, name) = match modifier {
        Modifier::Ctrl => (Some(CONTROL), "Ctrl"),
        Modifier::Shift => (Some(SHIFT), "Shift"),
        Modifier::Alt => (keyboard.modifier(&ALT), "Alt"),
        Modifier::Super => (keyboard.modifier(&SUPER), "Super"),
    };
    bit.ok_or_else(|| HotkeyError::Registration(format!("no modifier on this keyboard is {name}")))
}

/// Every modifier set to grab: the chord's own with each combination of the ignored bits added.
fn variants(modifiers: u16, ignored: u16) -> Vec<u16> {
    let mut variants: Vec<u16> = [0, LOCK, ignored & !LOCK, ignored]
        .iter()
        .map(|extra| modifiers | extra)
        .collect();
    variants.sort_unstable();
    variants.dedup();
    variants
}

/// Reads key events until the connection fails, running each binding a new press matches.
fn listen(keys: &dyn KeyGrab, bindings: &Mutex<Vec<Binding>>) {
    let mut released = None;
    while let Ok(key) = keys.next_key() {
        // The server sends each auto-repeat as a release and a press with the same time.
        let repeat = released == Some((key.keycode, key.time));
        released = (!key.pressed).then_some((key.keycode, key.time));
        if key.pressed && !repeat {
            run(bindings, key);
        }
    }
}

/// Runs each binding whose key and modifiers `press` matches, ignoring its locks and buttons.
fn run(bindings: &Mutex<Vec<Binding>>, press: KeyEvent) {
    for binding in lock(bindings).iter() {
        let state = press.state & MODIFIERS & !binding.ignored;
        if press.keycode == binding.keycode && state == binding.modifiers {
            (binding.on_activate)();
        }
    }
}

/// Locks the bindings; a callback that panicked leaves them usable.
fn lock(bindings: &Mutex<Vec<Binding>>) -> std::sync::MutexGuard<'_, Vec<Binding>> {
    bindings.lock().unwrap_or_else(PoisonError::into_inner)
}
