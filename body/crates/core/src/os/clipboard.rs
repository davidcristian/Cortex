//! The port that reads a picture from the system clipboard as the encoded bytes its owner gave.

/// The media types a pasted picture is asked for, in order: the ones the overlay's reader decodes.
pub const PICTURE_TYPES: [&str; 3] = ["image/png", "image/jpeg", "image/webp"];

/// The most bytes a pasted picture may have, so a clipboard owner cannot make the shell hold an
/// unbounded buffer. The overlay shrinks a picture after this, so it bounds the read alone.
pub const MAX_PASTED_BYTES: usize = 32 * 1024 * 1024;

/// A picture read from the clipboard: its bytes, still encoded, and the type they were read as.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct PastedPicture {
    /// The encoded picture, never decoded here.
    pub data: Vec<u8>,
    /// One of [`PICTURE_TYPES`].
    pub mime_type: &'static str,
}

/// Why the clipboard's picture was not read.
#[derive(Clone, Debug, PartialEq, Eq, thiserror::Error)]
pub enum ClipboardError {
    /// The picture is over [`MAX_PASTED_BYTES`].
    #[error("the clipboard's picture is over the {MAX_PASTED_BYTES} byte limit")]
    TooLarge,
    /// The clipboard could not be reached or its owner did not answer.
    #[error("the clipboard could not be read: {0}")]
    Failed(String),
}

/// The port a clipboard backend implements: X11 on Linux, none where the webview reads a paste.
pub trait ClipboardPicture {
    /// The clipboard's picture as the first of [`PICTURE_TYPES`] its owner offers, or `None`.
    ///
    /// # Errors
    ///
    /// [`ClipboardError`] when the picture is too large or the clipboard cannot be read.
    fn picture(&self) -> Result<Option<PastedPicture>, ClipboardError>;
}

/// A clipboard that never holds a picture, for a platform whose webview gives the page a pasted
/// picture as a file.
pub struct NoClipboardPicture;

impl ClipboardPicture for NoClipboardPicture {
    fn picture(&self) -> Result<Option<PastedPicture>, ClipboardError> {
        Ok(None)
    }
}
