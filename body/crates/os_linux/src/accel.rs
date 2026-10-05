//! The KDE [`Hotkey`] backend's logic over `kglobalaccel`'s registration calls.

use std::sync::{Arc, Mutex, MutexGuard, Once, PoisonError};
use std::thread;
use std::time::{Duration, Instant};

use body_core::{Accelerator, Hotkey, HotkeyCallback, HotkeyChord, HotkeyError, Modifier};

use crate::shortcuts::{Hold, REPEAT_GAP};

/// The component every action of the backend belongs to, so a restart registers the same one.
pub const COMPONENT: &str = "cortex";

/// A failed `kglobalaccel` call or a bus that is gone, as the bus wrote it.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct AccelError(pub String);

/// One `globalShortcutPressed` or `globalShortcutReleased` signal of the component.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Press {
    /// The id of the action the signal names.
    pub action: String,
    /// True for a press or one auto-repeat of it, and false for the release.
    pub active: bool,
}

/// The calls the backend makes on `org.kde.kglobalaccel`.
pub trait GlobalAccel: Send + Sync {
    /// Registers `action` as `description` with only `key`, returning the keys given, 0 if taken.
    ///
    /// # Errors
    ///
    /// [`AccelError`] when there is no bus or a call fails.
    fn bind(&self, action: &str, description: &str, key: i32) -> Result<Vec<i32>, AccelError>;

    /// Removes `action` from [`COMPONENT`], so its key is free for any other program.
    ///
    /// # Errors
    ///
    /// [`AccelError`] when there is no bus or the call fails.
    fn unbind(&self, action: &str) -> Result<(), AccelError>;

    /// Blocks until the next press or release signal of [`COMPONENT`], in the order sent.
    ///
    /// # Errors
    ///
    /// [`AccelError`] when the connection closes or a message cannot be read from it.
    fn next_press(&self) -> Result<Press, AccelError>;
}

/// One bound action: its id, its callback and whether it is held.
struct Binding {
    action: String,
    on_activate: HotkeyCallback,
    hold: Hold,
}

/// The Linux global-hotkey backend for a KDE Plasma session, over any [`GlobalAccel`].
pub struct LinuxKdeHotkey {
    accel: Arc<dyn GlobalAccel>,
    description: String,
    bindings: Arc<Mutex<Vec<Binding>>>,
    listener: Once,
    gap: Duration,
}

impl LinuxKdeHotkey {
    /// Creates the backend over `accel`, naming each action to the user with `description`.
    #[must_use]
    pub fn new(accel: impl GlobalAccel + 'static, description: &str) -> Self {
        Self::with_gap(accel, description, REPEAT_GAP)
    }

    /// Creates the backend, ending a hold after `gap` with no signal for its action.
    #[must_use]
    pub fn with_gap(accel: impl GlobalAccel + 'static, description: &str, gap: Duration) -> Self {
        Self {
            accel: Arc::new(accel),
            description: String::from(description),
            bindings: Arc::new(Mutex::new(Vec::new())),
            listener: Once::new(),
            gap,
        }
    }
}

impl Hotkey for LinuxKdeHotkey {
    fn register(
        &self,
        chord: &HotkeyChord,
        on_activate: HotkeyCallback,
    ) -> Result<(), HotkeyError> {
        let key = qt_key(chord)?;
        let action = chord.to_string();
        let keys = self
            .accel
            .bind(&action, &self.description, key)
            .map_err(|error| HotkeyError::Registration(format!("{chord}: {}", error.0)))?;
        if !keys.contains(&key) {
            // A failed removal leaves an action with no key, which the next registration replaces.
            let _ = self.accel.unbind(&action);
            return Err(HotkeyError::Registration(format!(
                "{chord}: kglobalaccel gave the key to another action"
            )));
        }
        lock(&self.bindings).push(Binding {
            action,
            on_activate,
            hold: Hold::default(),
        });
        self.listener.call_once(|| {
            let accel = Arc::clone(&self.accel);
            let bindings = Arc::clone(&self.bindings);
            let gap = self.gap;
            thread::spawn(move || listen(accel.as_ref(), &bindings, gap));
        });
        Ok(())
    }
}

impl Drop for LinuxKdeHotkey {
    fn drop(&mut self) {
        for binding in lock(&self.bindings).iter() {
            // `kglobalaccel` keeps a key grabbed until its action is removed, even with no client.
            let _ = self.accel.unbind(&binding.action);
        }
    }
}

/// Reads signals until the connection fails, running each binding a new press names once.
fn listen(accel: &dyn GlobalAccel, bindings: &Mutex<Vec<Binding>>, gap: Duration) {
    while let Ok(signal) = accel.next_press() {
        let now = Instant::now();
        for binding in lock(bindings).iter_mut() {
            if binding.action == signal.action && binding.hold.pressed(signal.active, now, gap) {
                (binding.on_activate)();
            }
        }
    }
}

/// Locks the bindings; a callback that panicked leaves them usable.
fn lock(bindings: &Mutex<Vec<Binding>>) -> MutexGuard<'_, Vec<Binding>> {
    bindings.lock().unwrap_or_else(PoisonError::into_inner)
}

/// The chord as a Qt key code: the key's `Qt::Key` value with Qt's modifier bits.
///
/// # Errors
///
/// [`HotkeyError::UnsupportedKey`] when the chord's key has no code or no Qt code here.
pub fn qt_key(chord: &HotkeyChord) -> Result<i32, HotkeyError> {
    let code = Accelerator::from_chord(chord)?.code;
    let bits = chord
        .modifiers()
        .iter()
        .fold(0, |sum, &each| sum | modifier(each));
    qt_code(&code)
        .map(|key| key | bits)
        .ok_or(HotkeyError::UnsupportedKey(code))
}

/// The modifier's bit in a Qt key code.
const fn modifier(modifier: Modifier) -> i32 {
    match modifier {
        Modifier::Shift => 0x0200_0000,
        Modifier::Ctrl => 0x0400_0000,
        Modifier::Alt => 0x0800_0000,
        Modifier::Super => 0x1000_0000,
    }
}

/// The `Qt::Key` value of a `KeyboardEvent.code` name, or `None` for a code with none here.
#[must_use]
pub fn qt_code(code: &str) -> Option<i32> {
    let named = match code {
        "Space" => 0x20,
        "Escape" => 0x0100_0000,
        "Tab" => 0x0100_0001,
        "Backspace" => 0x0100_0003,
        "Enter" => 0x0100_0004,
        "ArrowLeft" => 0x0100_0012,
        "ArrowUp" => 0x0100_0013,
        "ArrowRight" => 0x0100_0014,
        "ArrowDown" => 0x0100_0015,
        _ => return printable(code),
    };
    Some(named)
}

/// The `Qt::Key` value of a letter, digit or function key code: `KeyA` is `0x41`, `F1` is
/// `0x0100_0030`.
fn printable(code: &str) -> Option<i32> {
    match code.as_bytes() {
        [b'K', b'e', b'y', letter @ b'A'..=b'Z'] => Some(i32::from(*letter)),
        [b'D', b'i', b'g', b'i', b't', digit @ b'0'..=b'9'] => Some(i32::from(*digit)),
        [b'F', ..] => code[1..]
            .parse::<i32>()
            .ok()
            .filter(|number| (1..=35).contains(number))
            .map(|number| 0x0100_002F + number),
        _ => None,
    }
}
