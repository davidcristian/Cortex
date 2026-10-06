//! The Linux `ClipboardPicture`: which picture type is read and when a read is refused, over a
//! [`SelectionRead`] that converts the clipboard selection.

use body_core::{ClipboardError, ClipboardPicture, MAX_PASTED_BYTES, PICTURE_TYPES, PastedPicture};

/// Why converting the clipboard selection to one type failed.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum SelectionError {
    /// The owner sent more bytes than the read was allowed.
    Over,
    /// The owner did not answer within the read's wait.
    Silent,
    /// The display could not be reached, refused a request or its owner did not answer.
    Failed(String),
}

/// The crate-local port: the `CLIPBOARD` selection's types, and the selection converted to one.
pub trait SelectionRead {
    /// The types the selection's owner lists, empty when nobody owns it.
    ///
    /// # Errors
    ///
    /// Why the list could not be read.
    fn offered(&self) -> Result<Vec<String>, SelectionError>;

    /// The selection's bytes as `target`, or `None` when nobody owns it or the owner refuses it.
    ///
    /// # Errors
    ///
    /// [`SelectionError::Over`] once more than `limit` bytes arrive, else why the read failed.
    fn convert(&self, target: &str, limit: usize) -> Result<Option<Vec<u8>>, SelectionError>;
}

/// Reads the clipboard's picture over a [`SelectionRead`].
pub struct LinuxClipboardPicture<S> {
    selection: S,
}

impl<S> LinuxClipboardPicture<S> {
    /// Reads through `selection`, an [`X11Selection`](crate::X11Selection) in the shell.
    #[must_use]
    pub const fn new(selection: S) -> Self {
        Self { selection }
    }
}

impl<S: SelectionRead> ClipboardPicture for LinuxClipboardPicture<S> {
    fn picture(&self) -> Result<Option<PastedPicture>, ClipboardError> {
        first_picture(&self.selection)
    }
}

/// Asks for each picture type the owner lists, in order, and keeps the first non-empty answer.
/// A request the owner was silent on is sent once more: `xclip` drops one that arrives while it
/// sends the webview its own copy of a large picture in `INCR` chunks.
fn first_picture(selection: &dyn SelectionRead) -> Result<Option<PastedPicture>, ClipboardError> {
    let offered = match selection.offered() {
        Err(SelectionError::Silent) => selection.offered(),
        listed => listed,
    };
    let offered = offered.map_err(refused)?;
    let listed = |wanted: &&str| offered.iter().any(|name| name == wanted);
    for mime_type in PICTURE_TYPES.iter().copied().filter(listed) {
        let read = match selection.convert(mime_type, MAX_PASTED_BYTES) {
            Err(SelectionError::Silent) => selection.convert(mime_type, MAX_PASTED_BYTES),
            read => read,
        };
        if let Some(data) = read.map_err(refused)?.filter(|data| !data.is_empty()) {
            return Ok(Some(PastedPicture { data, mime_type }));
        }
    }
    Ok(None)
}

/// The port's error for a read that failed.
fn refused(error: SelectionError) -> ClipboardError {
    match error {
        SelectionError::Over => ClipboardError::TooLarge,
        SelectionError::Silent => {
            ClipboardError::Failed(String::from("the clipboard's owner did not answer"))
        }
        SelectionError::Failed(reason) => ClipboardError::Failed(reason),
    }
}
